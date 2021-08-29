import os
import json
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-dekala_table_lamp')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
DEVICE_TYPE= os.getenv('DEVICE_TYPE')
HA_TOPIC = os.getenv('HA_TOPIC', 't2t2m2p2m2ha/dekala_table_lamp/')

# from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'dekala_table_lamp'

# Virtual Color Temperature
VCT_mired = [153.0, 222.2, 294.1, 357.1, 434.8, 500.0]
VCT_hue = [60, 27, 28, 28, 30, 31]
VCT_sat = [1.6, 26.7, 47.1, 62.7, 80.4, 94.5]
def interp(xq, x, y):
    if xq < x[0]:
        return y[0]
    elif xq > x[-1]:
        return y[-1]
    else:
        for n in range(len(x)-1):
            if x[n] <= xq <= x[n+1]:
                return y[n] + (xq-x[n])*(y[n+1]-y[n])/(x[n+1]-x[n])

logging = True

# Define Extra Topics
command_topic = 'cmnd/' + DEVICE_TOPIC + '/'
state_topic = 'stat/' + DEVICE_TOPIC + '/'
telemetry_topic = 'tele/' + DEVICE_TOPIC + '/'
result_topic = 'tele/' + DEVICE_TOPIC + '/RESULT'
lwt_topic = 'tele/' + DEVICE_TOPIC + '/LWT'
if HA_TOPIC[-1] != '/': HA_TOPIC += '/'

# Define Some Defaults
color_light_state = False
color_light_hue = 0
color_light_saturation = 100
color_light_brightness = 1000
effect_light_state = False
effect_light_settings = '02X000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
effect_light_effect = 'Aurora Left'
effect_light_speed = 4
night_light_state = False
sleep_aid_state = False
sleep_aid_settings = '161E7F0000001E0100010000'
sleep_aid_days = '1111111'
alarm_1_state = False
alarm_1_settings = '08007F0000000F0100010000'
alarm_1_days = '1111111'
alarm_2_state = False
alarm_2_settings = '0C007F0000000F0100010000'
alarm_2_days = '1111111'
effect_light_brightness = 1000
night_light_brightness = 1000
alarms_status = 'OFF'

binary_payload = ['OFF', 'ON']
inv_binary_payload = {'OFF': 0, 'ON': 1}

# Effect Lights List
effects_dict = {"Aurora Left": (0, 0),
            "Aurora Right": (0, 1),
            "Sunlight Sunset Orange": (1, 0),
            "Sunlight Sunrise Pink": (1, 1),
            "Night Red": (2, 0),
            "Night Blue": (2, 1),
            "Night Orange": (2, 2),
            "Neon Clockwise": (3, 0),
            "Neon Counterclockwise": (3, 1),
            "Grassland GreenYellow": (4, 0),
            "Grassland GreenWhite": (4, 1),
            "Breath Red": (5, 0),
            "Breath Purple": (5, 1),
            "Breath Orange": (5, 2),
            "Breath Yellow": (5, 3),
            "Rainbow Up": (6, 0),
            "Rainbow Down": (6, 1),
            "Deep Sea RedBlueRed": (7, 0),
            "Deep Sea WhiteBlueWhite": (7, 1),
            "Bonfire Orange": (8, 0),
            "Bonfire Red": (8, 1)}
effects_inv_dict = {v: k for k, v in effects_dict.items()}
effects_list = effects_dict.keys()


sleep_aid_light_types = ['None', 'Sleep Aid', 'Aurora', 'Sunlight', 'Night', 'Neon', 'Grassland', 'Breathing', 'Rainbow', 'Deep Sea', 'Bonfire']
inv_sleep_aid_light_types = {v: i for i, v in enumerate(sleep_aid_light_types)}
alarm_light_types = ['None', 'Wake Up', 'Aurora', 'Sunlight', 'Night', 'Neon', 'Grassland', 'Breathing', 'Rainbow', 'Deep Sea', 'Bonfire']
inv_alarm_light_types = {v: i for i, v in enumerate(alarm_light_types)}

# Helper Functions for Tuya Serial
def tuya_checksum(in_str):
    chk = 0
    for n in range(0, len(in_str), 2):
        chk += int(in_str[n:n+2], 16)
    chk = chk % 256
    return '%02X' % chk

def tuya_payload_raw(dpid, in_str):
    out_str = '55AA0006'
    # form SDU
    sdu_data = in_str
    sdu_type = '00'
    sdu_len = '%04X' % (len(sdu_data)//2)
    sdu_dpid = '%02X' % dpid
    sdu_str = sdu_dpid + sdu_type + sdu_len + sdu_data
    data_len = '%04X' % (len(sdu_str)//2)
    out_str += data_len
    out_str += sdu_str
    out_str += tuya_checksum(out_str)
    return out_str

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    publog('Connected with result code '+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(command_topic + '#')
    client.subscribe(state_topic + '#')
    client.subscribe(telemetry_topic + '#')
    client.subscribe(HA_TOPIC + '#')

    # Query Status
    publish(command_topic + 'TuyaSend0', payload='')

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global color_light_state        # DPID 2
    global color_light_hue          # DPID 11
    global color_light_saturation   # DPID 11
    global color_light_brightness   # DPID 101
    global effect_light_state       # DPID 102
    global effect_light_settings    # DPID 103
    global effect_light_effect
    global effect_light_speed
    global night_light_state        # DPID 104
    global sleep_aid_state          # DPID 106
    global sleep_aid_settings       # DPID 107
    global sleep_aid_days
    global alarm_1_state            # DPID 108
    global alarm_1_settings         # DPID 109
    global alarm_1_days
    global alarm_2_state            # DPID 110
    global alarm_2_settings         # DPID 112
    global alarm_2_days
    global effect_light_brightness  # DPID 123
    global night_light_brightness   # DPID 124
    global alarms_status            # DPID 126

    payload_str = str(msg.payload.decode("utf-8"))
    if logging: publog('%s: %s' % (msg.topic, payload_str))

    if msg.topic == lwt_topic:
        if payload_str == 'Online':
            publish(HA_TOPIC + 'LWT', payload='online')
        else:
            publish(HA_TOPIC + 'LWT', payload='offline')

    # If we receive a "RESULT" from Tasmota
    elif msg.topic == result_topic:
        payload_dict = json.loads(msg.payload) # load the payload into dictionary

        # If the RESULT is a TuyaReceived
        if 'TuyaReceived' in payload_dict:
            tuya_rec_dict = payload_dict['TuyaReceived']

            # Tuya MCU Sent Heartbeat
            if tuya_rec_dict['Cmnd'] == 0:
                if tuya_rec_dict['CmndData'] == 0:
                    publish(command_topic + 'TuyaSend0', payload='') # ask for state again
                    if logging: publog('Heart Beat 0: Detected MCU Reset')
                else:
                    if logging: publog('Heart Beat 1')
            
            # Tuya MCU Sent Product Information (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 1:
                if logging: publog('Got Product Info')

            # Tuya MCU Sent Working Mode (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 2:
                if logging: publog('Got Working Mode')

            # Tuya MCU Asked for Local Time (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 28:
                if logging: publog('Got Request for Local Time')

            # Tuya MCU Sends DPID State
            elif tuya_rec_dict['Cmnd'] == 7:

                # A single command 7 can contain multiple status data units
                for key in tuya_rec_dict:
                    datapoint = {}

                    # Check if the key can be interpreted as an integer
                    try:
                        int(key)
                        datapoint = tuya_rec_dict[key]
                    except:
                        pass
                    if datapoint:
                        DpId = datapoint['DpId']
                        DpIdType = datapoint['DpIdType']
                        DpIdData = datapoint['DpIdData']

                        # Color Light State
                        if DpId == 2 and DpIdType == 1:
                            color_light_state = bool(int(DpIdData))
                            if color_light_state:
                                publish(HA_TOPIC + 'color/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'color/state', payload='OFF')
                            if logging: publog('Color Light: State %s' % str(color_light_state))

                        # Color Light Color Settings
                        elif DpId == 11 and DpIdType == 3:
                            color_str = bytearray.fromhex(DpIdData).decode()
                            color_light_hue = 1.0*int.from_bytes(bytearray.fromhex(color_str[0:4]), 'big')
                            color_light_saturation = int.from_bytes(bytearray.fromhex(color_str[4:8]), 'big')/10.0
                            publish(HA_TOPIC + 'color/hs', payload='%f,%f' % (color_light_hue, color_light_saturation))
                            if logging: publog('Color Light: Hue %s, Saturation %s' % (str(color_light_hue), str(color_light_saturation)))
                            
                        # Color Light Brightness
                        elif DpId == 101 and DpIdType == 2:
                            color_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'color/brightness', payload='%d' % color_light_brightness)
                            if logging: publog('Color Light: Brightness %s' % str(color_light_brightness))
                        
                        # Night Light State
                        elif DpId == 104 and DpIdType == 1:
                            night_light_state = bool(int(DpIdData))
                            if night_light_state:
                                publish(HA_TOPIC + 'night/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'night/state', payload='OFF')
                            if logging: publog('Night Light: State %s' % str(night_light_state))

                        # Night Light Brightness
                        elif DpId == 124 and DpIdType == 2:
                            night_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'night/brightness', payload='%d' % night_light_brightness)
                            if logging: publog('Night Light: Brightness %s' % str(night_light_brightness))

                        # Effect Light State
                        elif DpId == 102 and DpIdType == 1:
                            effect_light_state = bool(int(DpIdData))
                            if effect_light_state:
                                publish(HA_TOPIC + 'effect/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'effect/state', payload='OFF')
                            if logging: publog('Effect Light: State %s' % str(effect_light_state))

                        # Effect Light Brightness
                        elif DpId == 123 and DpIdType == 2:
                            effect_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'effect/brightness', payload='%d' % effect_light_brightness)
                            if logging: publog('Effect Light: Brightness %s' % str(effect_light_brightness))

                        # Effect Light Settings
                        elif DpId == 103 and DpIdType == 0:
                            effect_light_settings = DpIdData
                            temp1 = int(effect_light_settings[0:2], 16)
                            temp2 = int(effect_light_settings[88:90], 16)
                            effect_light_speed = int(effect_light_settings[86:88], 16)
                            effect_light_effect = effects_inv_dict[(temp1, temp2)]
                            publish(HA_TOPIC + 'effect/effect', payload=effect_light_effect)
                            publish(HA_TOPIC + 'effect/speed', payload=str(effect_light_speed))
                            if logging: 
                                publog('Effect Light: Effect %s' % effect_light_effect)
                                publog('Effect Light: Speed %s' % str(effect_light_speed))

                        # DPID 126 - Alarms Status
                        elif DpId == 126 and DpIdType == 0:
                            if DpIdData == '0002':
                                publish(HA_TOPIC + 'alarms/status', payload='OFF')
                            elif DpIdData == '0000':
                                publish(HA_TOPIC + 'alarms/status', payload='Alarm 1')
                            elif DpIdData == '0100':
                                publish(HA_TOPIC + 'alarms/status', payload='Alarm 2')
                            elif DpIdData == '0200':
                                publish(HA_TOPIC + 'alarms/status', payload='Sleep Aid')
                            else:
                                publish(HA_TOPIC + 'alarms/status', payload='Unknown')
                        
                        # DPID 106 - Sleep Aid State
                        elif DpId == 106 and DpIdType == 1:
                            sleep_aid_state = bool(int(DpIdData))
                            if sleep_aid_state:
                                publish(HA_TOPIC + 'alarms/sleep_aid/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'alarms/sleep_aid/state', payload='OFF')
                            if logging: publog('Sleep Aid: State %s' % str(sleep_aid_state))
                        
                        # DPID 108 - Alarm 1 State
                        elif DpId == 108 and DpIdType == 1:
                            alarm_1_state = bool(int(DpIdData))
                            if alarm_1_state:
                                publish(HA_TOPIC + 'alarms/alarm_1/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'alarms/alarm_1/state', payload='OFF')
                            if logging: publog('Alarm 1: State %s' % str(alarm_1_state))

                        # DPID 110 - Alarm 2 State
                        elif DpId == 110 and DpIdType == 1:
                            alarm_2_state = bool(int(DpIdData))
                            if alarm_2_state:
                                publish(HA_TOPIC + 'alarms/alarm_2/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'alarms/alarm_2/state', payload='OFF')
                            if logging: publog('Alarm 2: State %s' % str(alarm_2_state))
                        
                        # DPID 107 - Sleep Aid Settings
                        elif DpId == 107 and DpIdType == 0:
                            sleep_aid_settings = DpIdData
                            publish(HA_TOPIC + 'alarms/sleep_aid/hours', payload=int(DpIdData[0:2], 16))
                            publish(HA_TOPIC + 'alarms/sleep_aid/minutes', payload=int(DpIdData[2:4], 16))
                            publish(HA_TOPIC + 'alarms/sleep_aid/duration', payload=int(DpIdData[12:14], 16))
                            publish(HA_TOPIC + 'alarms/sleep_aid/light_type', payload=sleep_aid_light_types[int(DpIdData[14:16], 16)])
                            publish(HA_TOPIC + 'alarms/sleep_aid/light_advance_duration', payload=int(DpIdData[16:18], 16))
                            publish(HA_TOPIC + 'alarms/sleep_aid/auto_close', payload=binary_payload[int(DpIdData[18:20], 16)])
                            
                            sleep_aid_days = str(bin(int(DpIdData[4:6],16)))[2:]
                            sleep_aid_days = '0'*(7 - len(sleep_aid_days)) + sleep_aid_days
                            publish(HA_TOPIC + 'alarms/sleep_aid/sun', payload=binary_payload[int(sleep_aid_days[0])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/sat', payload=binary_payload[int(sleep_aid_days[1])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/fri', payload=binary_payload[int(sleep_aid_days[2])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/thu', payload=binary_payload[int(sleep_aid_days[3])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/wed', payload=binary_payload[int(sleep_aid_days[4])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/tue', payload=binary_payload[int(sleep_aid_days[5])])
                            publish(HA_TOPIC + 'alarms/sleep_aid/mon', payload=binary_payload[int(sleep_aid_days[6])])

                        # DPID 109 - Alarm 1 Settings
                        elif DpId == 109 and DpIdType == 0:
                            alarm_1_settings = DpIdData
                            publish(HA_TOPIC + 'alarms/alarm_1/hours', payload=int(DpIdData[0:2], 16))
                            publish(HA_TOPIC + 'alarms/alarm_1/minutes', payload=int(DpIdData[2:4], 16))
                            publish(HA_TOPIC + 'alarms/alarm_1/duration', payload=int(DpIdData[12:14], 16))
                            publish(HA_TOPIC + 'alarms/alarm_1/light_type', payload=alarm_light_types[int(DpIdData[14:16], 16)])
                            
                            alarm_1_days = str(bin(int(DpIdData[4:6],16)))[2:]
                            alarm_1_days = '0'*(7 - len(alarm_1_days)) + alarm_1_days
                            publish(HA_TOPIC + 'alarms/alarm_1/sun', payload=binary_payload[int(alarm_1_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_1/sat', payload=binary_payload[int(alarm_1_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_1/fri', payload=binary_payload[int(alarm_1_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_1/thu', payload=binary_payload[int(alarm_1_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_1/wed', payload=binary_payload[int(alarm_1_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_1/tue', payload=binary_payload[int(alarm_1_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_1/mon', payload=binary_payload[int(alarm_1_days[6])])
                        
                        # DPID 111 - Alarm 2 Settings
                        elif DpId == 111 and DpIdType == 0:
                            alarm_2_settings = DpIdData
                            publish(HA_TOPIC + 'alarms/alarm_2/hours', payload=int(DpIdData[0:2], 16))
                            publish(HA_TOPIC + 'alarms/alarm_2/minutes', payload=int(DpIdData[2:4], 16))
                            publish(HA_TOPIC + 'alarms/alarm_2/duration', payload=int(DpIdData[12:14], 16))
                            publish(HA_TOPIC + 'alarms/alarm_2/light_type', payload=alarm_light_types[int(DpIdData[14:16], 16)])
                            
                            alarm_2_days = str(bin(int(DpIdData[4:6],16)))[2:]
                            alarm_2_days = '0'*(7 - len(alarm_2_days)) + alarm_2_days
                            publish(HA_TOPIC + 'alarms/alarm_2/sun', payload=binary_payload[int(alarm_2_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_2/sat', payload=binary_payload[int(alarm_2_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_2/fri', payload=binary_payload[int(alarm_2_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_2/thu', payload=binary_payload[int(alarm_2_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_2/wed', payload=binary_payload[int(alarm_2_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_2/tue', payload=binary_payload[int(alarm_2_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_2/mon', payload=binary_payload[int(alarm_2_days[6])])
                        

                        # Ignored
                        elif DpId == 114: # Local Time Report
                            pass
                        elif DpId == 115: # Network Time vs Manual Time
                            pass
                        elif DpId == 125: # 12 or 24 Hour Time
                            pass

                        else:
                            if logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)


    # HA's _set Topics

    # HA Setting DPID 2 - Color Light State (bool)
    elif msg.topic == HA_TOPIC + 'color/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Color Light On')
            if not color_light_state: publish(command_topic + 'TuyaSend1', payload='2,1')
        else:
            if logging: publog('HA: Turn Color Light Off')
            if color_light_state: publish(command_topic + 'TuyaSend1', payload='2,0')

    # HA Setting DPID 11 - Color Light Settings (12-string, 4-HUE, 4-SAT, 4-BRI but unused)
    elif msg.topic == HA_TOPIC + 'color/hs_set':
        temp1, temp2 = (float(x) for x in payload_str.split(','))
        if logging: publog('HA: Set Color Light Hue %f and Saturation %f' % (temp1, temp2))
        dpid_str = ('%04x' % int(temp1)) + ('%04x' % int(10*temp2)) + ('%04x' % 1000)
        publish(command_topic + 'TuyaSend3', payload='11,'+dpid_str)

    elif msg.topic == HA_TOPIC + 'color/VCT' + '_set':
        mired = float(payload_str)
        hue = interp(mired, VCT_mired, VCT_hue)
        sat = interp(mired, VCT_mired, VCT_sat)
        publish(command_topic + 'TuyaSend3', payload='11,%04x%04x%04x' % (int(hue), int(10*sat), 1000))

    # HA Setting DPID 101 - Color Light Brightness (value)
    elif msg.topic == HA_TOPIC + 'color/brightness_set':
        if logging: publog('HA: Set Color Light Brightness %f' % float(payload_str))
        publish(command_topic + 'TuyaSend2', payload='101,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 104 - Night Light State (bool)
    elif msg.topic == HA_TOPIC + 'night/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Night Light On')
            if not night_light_state: publish(command_topic + 'TuyaSend1', payload='104,1')
        else:
            if logging: publog('HA: Turn Night Light Off')
            if night_light_state: publish(command_topic + 'TuyaSend1', payload='104,0')

    # HA Setting DPID 124 - Night Light Brightness (value)
    elif msg.topic == HA_TOPIC + 'night/brightness_set':
        if logging: publog('HA: Set Night Light Brightness %f' % float(payload_str))
        publish(command_topic + 'TuyaSend2', payload='124,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 102 - Effect Light State (bool)
    elif msg.topic == HA_TOPIC + 'effect/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Effect Light On')
            if not effect_light_state: publish(command_topic + 'TuyaSend1', payload='102,1')
        else:
            if logging: publog('HA: Turn Effect Light Off')
            if effect_light_state: publish(command_topic + 'TuyaSend1', payload='102,0')

    # HA Setting DPID 123 - Effect Light Brightness (value)
    elif msg.topic == HA_TOPIC + 'effect/brightness_set':
        if logging: publog('HA: Set Effect Light Brightness %f' % float(payload_str))
        publish(command_topic + 'TuyaSend2', payload='123,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 103 - Effect Light Settings (raw)
    elif msg.topic == HA_TOPIC + 'effect/effect_set':
        effect_mode, effect_variation = effects_dict[payload_str]
        if logging: publog('HA: Set Effect Light Effect (name,mode,variation) (%s, %d, %d)' % (payload_str,effect_mode,effect_variation))
        raw_str = '%02X000000000000000000000000000000000000000000000000000000000000000000000000000000000000%02X%02X' % (effect_mode, effect_light_speed, effect_variation)
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(103, raw_str))
    elif msg.topic == HA_TOPIC + 'effect/speed_set':
        if logging: publog('HA: Set Effect Light Speed %f' % float(payload_str))
        effect_mode, effect_variation = effects_dict[effect_light_effect]
        raw_str = '%02X000000000000000000000000000000000000000000000000000000000000000000000000000000000000%02X%02X' % (effect_mode, int(payload_str), effect_variation)
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(103, raw_str))

    # HA Setting DPID 112 - Turn Off Alarm Command
    elif msg.topic == HA_TOPIC + 'alarms/status_set':
        # any message published here turns alarms off
        if logging: publog('HA: Stop Active Alarm')
        publish(command_topic + 'TuyaSend1', payload='112,1')
        publish(HA_TOPIC + 'alarms/status', payload='OFF') # put switch back in HA

    # HA Setting DPID 106 - Sleep Aid State (bool)
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Sleep Aid On')
            if not sleep_aid_state: publish(command_topic + 'TuyaSend1', payload='106,1')
        else:
            if logging: publog('HA: Turn Sleep Aid Off')
            if sleep_aid_state: publish(command_topic + 'TuyaSend1', payload='106,0')

    # HA Setting DPID 108 - Alarm 1 State (bool)
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Alarm 1 On')
            if not alarm_1_state: publish(command_topic + 'TuyaSend1', payload='108,1')
        else:
            if logging: publog('HA: Turn Alarm 1 Off')
            if alarm_1_state: publish(command_topic + 'TuyaSend1', payload='108,0')

    # HA Setting DPID 110 - Alarm 2 State (bool)
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/state_set':
        if payload_str == 'ON':
            if logging: publog('HA: Turn Alarm 2 On')
            if not alarm_2_state: publish(command_topic + 'TuyaSend1', payload='110,1')
        else:
            if logging: publog('HA: Turn Alarm 2 Off')
            if alarm_2_state: publish(command_topic + 'TuyaSend1', payload='110,0')

    # HA Setting DPID 107 - Sleep Aid Settings (raw)
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/hours_set':
        raw_str = ('%02X' % int(payload_str)) + sleep_aid_settings[2:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/minutes_set':
        raw_str = sleep_aid_settings[0:2] + ('%02X' % int(payload_str)) + sleep_aid_settings[4:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/duration_set':
        raw_str = sleep_aid_settings[0:12] + ('%02X' % int(payload_str)) + sleep_aid_settings[14:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/light_type_set':
        raw_str = sleep_aid_settings[0:14] + ('%02X' % inv_sleep_aid_light_types[payload_str]) + sleep_aid_settings[16:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/light_advance_duration_set':
        raw_str = sleep_aid_settings[0:16] + ('%02X' % int(payload_str)) + sleep_aid_settings[18:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/auto_close_set':
        raw_str = sleep_aid_settings[0:18] + ('%02X' % inv_binary_payload[payload_str]) + sleep_aid_settings[20:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/sun_set':
        temp = str(inv_binary_payload[payload_str]) + sleep_aid_days[1:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/sat_set':
        temp = sleep_aid_days[0:1] + str(inv_binary_payload[payload_str]) + sleep_aid_days[2:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/fri_set':
        temp = sleep_aid_days[0:2] + str(inv_binary_payload[payload_str]) + sleep_aid_days[3:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/thu_set':
        temp = sleep_aid_days[0:3] + str(inv_binary_payload[payload_str]) + sleep_aid_days[4:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/wed_set':
        temp = sleep_aid_days[0:4] + str(inv_binary_payload[payload_str]) + sleep_aid_days[5:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/tue_set':
        temp = sleep_aid_days[0:5] + str(inv_binary_payload[payload_str]) + sleep_aid_days[6:]
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/sleep_aid/mon_set':
        temp = sleep_aid_days[0:6] + str(inv_binary_payload[payload_str])
        raw_str = sleep_aid_settings[0:4] + ('%02X' % int(temp, 2)) + sleep_aid_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(107, raw_str))

    # HA Setting DPID 109 - Alarm 1 Settings (raw)
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/hours_set':
        raw_str = ('%02X' % int(payload_str)) + alarm_1_settings[2:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/minutes_set':
        raw_str = alarm_1_settings[0:2] + ('%02X' % int(payload_str)) + alarm_1_settings[4:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/duration_set':
        raw_str = alarm_1_settings[0:12] + ('%02X' % int(payload_str)) + alarm_1_settings[14:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/light_type_set':
        raw_str = alarm_1_settings[0:14] + ('%02X' % inv_alarm_light_types[payload_str]) + alarm_1_settings[16:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/sun_set':
        temp = str(inv_binary_payload[payload_str]) + alarm_1_days[1:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/sat_set':
        temp = alarm_1_days[0:1] + str(inv_binary_payload[payload_str]) + alarm_1_days[2:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/fri_set':
        temp = alarm_1_days[0:2] + str(inv_binary_payload[payload_str]) + alarm_1_days[3:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/thu_set':
        temp = alarm_1_days[0:3] + str(inv_binary_payload[payload_str]) + alarm_1_days[4:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/wed_set':
        temp = alarm_1_days[0:4] + str(inv_binary_payload[payload_str]) + alarm_1_days[5:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/tue_set':
        temp = alarm_1_days[0:5] + str(inv_binary_payload[payload_str]) + alarm_1_days[6:]
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_1/mon_set':
        temp = alarm_1_days[0:6] + str(inv_binary_payload[payload_str])
        raw_str = alarm_1_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_1_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(109, raw_str))

    # HA Setting DPID 111 - Alarm 2 Settings (raw)
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/hours_set':
        raw_str = ('%02X' % int(payload_str)) + alarm_2_settings[2:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/minutes_set':
        raw_str = alarm_2_settings[0:2] + ('%02X' % int(payload_str)) + alarm_2_settings[4:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/duration_set':
        raw_str = alarm_2_settings[0:12] + ('%02X' % int(payload_str)) + alarm_2_settings[14:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/light_type_set':
        raw_str = alarm_2_settings[0:14] + ('%02X' % inv_alarm_light_types[payload_str]) + alarm_2_settings[16:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/sun_set':
        temp = str(inv_binary_payload[payload_str]) + alarm_2_days[1:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/sat_set':
        temp = alarm_2_days[0:1] + str(inv_binary_payload[payload_str]) + alarm_2_days[2:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/fri_set':
        temp = alarm_2_days[0:2] + str(inv_binary_payload[payload_str]) + alarm_2_days[3:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/thu_set':
        temp = alarm_2_days[0:3] + str(inv_binary_payload[payload_str]) + alarm_2_days[4:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/wed_set':
        temp = alarm_2_days[0:4] + str(inv_binary_payload[payload_str]) + alarm_2_days[5:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/tue_set':
        temp = alarm_2_days[0:5] + str(inv_binary_payload[payload_str]) + alarm_2_days[6:]
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))
    elif msg.topic == HA_TOPIC + 'alarms/alarm_2/mon_set':
        temp = alarm_2_days[0:6] + str(inv_binary_payload[payload_str])
        raw_str = alarm_2_settings[0:4] + ('%02X' % int(temp, 2)) + alarm_2_settings[6:]
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(111, raw_str))

client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD)
client.will_set(HA_TOPIC + 'LWT', payload='offline', qos=MQTT_QOS, retain=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

# Redefine Publish with The QOS Setting
def publish(topic, payload=None, qos=MQTT_QOS, retain=True, properties=None):
    client.publish(topic, payload=payload, qos=qos, retain=retain, properties=properties)

# Basic Logging over MQTT
def publog(x):
    print(x)
    publish('tony_fav_dev/log', payload=x)

client.loop_forever()