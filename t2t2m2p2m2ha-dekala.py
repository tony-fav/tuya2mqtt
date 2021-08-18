import os
import json
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-dekala')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
HA_TOPIC = os.getenv('HA_TOPIC', 'tuya/dekala_table_lamp/')

verbose_logging = True

# Define Extra Topics
command_topic = 'cmnd/' + DEVICE_TOPIC + '/'
state_topic = 'stat/' + DEVICE_TOPIC + '/'
telemetry_topic = 'tele/' + DEVICE_TOPIC + '/'
result_topic = 'tele/' + DEVICE_TOPIC + '/RESULT'
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
alarm_1_state = False
alarm_1_settings = '08007F0000000F0100010000'
alarm_2_state = False
alarm_2_settings = '0C007F0000000F0100010000'
effect_light_brightness = 1000
night_light_brightness = 1000
alarms_status = 'OFF'

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

    # Quey Status
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
    global alarm_1_state            # DPID 108
    global alarm_1_settings         # DPID 109
    global alarm_2_state            # DPID 110
    global alarm_2_settings         # DPID 112
    global effect_light_brightness  # DPID 123
    global night_light_brightness   # DPID 124
    global alarms_status            # DPID 126

    payload_str = str(msg.payload.decode("utf-8"))

    # If we receive a "RESULT" from Tasmota
    if msg.topic == result_topic:
        payload_dict = json.loads(msg.payload) # load the payload into dictionary

        # If the RESULT is a TuyaReceived
        if 'TuyaReceived' in payload_dict:
            tuya_rec_dict = payload_dict['TuyaReceived']

            # Tuya MCU Sent Heartbeat
            if tuya_rec_dict['Cmnd'] == 0:
                if tuya_rec_dict['CmndData'] == 0:
                    publish(command_topic + 'TuyaSend0', payload='') # ask for state again
                    if verbose_logging: publog('Heart Beat 0: Detected MCU Reset')
                else:
                    if verbose_logging: publog('Heart Beat 1')
            
            # Tuya MCU Sent Product Information (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 1:
                if verbose_logging: publog('Got Product Info')

            # Tuya MCU Sent Working Mode (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 2:
                if verbose_logging: publog('Got Working Mode')

            # Tuya MCU Asked for Local Time (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 28:
                if verbose_logging: publog('Got Request for Local Time')

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
                            if verbose_logging: publog('Color Light: State %s' % str(color_light_state))

                        # Color Light Color Settings
                        elif DpId == 11 and DpIdType == 3:
                            color_str = bytearray.fromhex(DpIdData).decode()
                            color_light_hue = 1.0*int.from_bytes(bytearray.fromhex(color_str[0:4]), 'big')
                            color_light_saturation = int.from_bytes(bytearray.fromhex(color_str[4:8]), 'big')/10.0
                            publish(HA_TOPIC + 'color/hs', payload='%f,%f' % (color_light_hue, color_light_saturation))
                            if verbose_logging: publog('Color Light: Hue %s, Saturation %s' % (str(color_light_hue), str(color_light_saturation)))
                            
                        # Color Light Brightness
                        elif DpId == 101 and DpIdType == 2:
                            color_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'color/brightness', payload='%d' % color_light_brightness)
                            if verbose_logging: publog('Color Light: Brightness %s' % str(color_light_brightness))
                        
                        # Night Light State
                        elif DpId == 104 and DpIdType == 1:
                            night_light_state = bool(int(DpIdData))
                            if night_light_state:
                                publish(HA_TOPIC + 'night/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'night/state', payload='OFF')
                            if verbose_logging: publog('Night Light: State %s' % str(night_light_state))

                        # Night Light Brightness
                        elif DpId == 124 and DpIdType == 2:
                            night_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'night/brightness', payload='%d' % night_light_brightness)
                            if verbose_logging: publog('Night Light: Brightness %s' % str(night_light_brightness))

                        # Effect Light State
                        elif DpId == 102 and DpIdType == 1:
                            effect_light_state = bool(int(DpIdData))
                            if effect_light_state:
                                publish(HA_TOPIC + 'effect/state', payload='ON')
                            else:
                                publish(HA_TOPIC + 'effect/state', payload='OFF')
                            if verbose_logging: publog('Effect Light: State %s' % str(effect_light_state))

                        # Effect Light Brightness
                        elif DpId == 123 and DpIdType == 2:
                            effect_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'effect/brightness', payload='%d' % effect_light_brightness)
                            if verbose_logging: publog('Effect Light: Brightness %s' % str(effect_light_brightness))

                        # Effect Light Settings
                        elif DpId == 103 and DpIdType == 0:
                            effect_light_settings = DpIdData
                            temp1 = int(effect_light_settings[0:2], 16)
                            temp2 = int(effect_light_settings[88:90], 16)
                            effect_light_speed = int(effect_light_settings[86:88], 16)
                            effect_light_effect = effects_inv_dict[(temp1, temp2)]
                            publish(HA_TOPIC + 'effect/effect', payload=effect_light_effect)
                            publish(HA_TOPIC + 'effect/speed', payload=str(effect_light_speed))
                            if verbose_logging: 
                                publog('Effect Light: Effect %s' % effect_light_effect)
                                publog('Effect Light: Speed %s' % str(effect_light_speed))
                        
                        # Sleep Aid State
                        
                        # Sleep Aid Settings
                        
                        # Alarm 1 State
                        
                        # Alarm 1 Settings
                        
                        # Alarm 2 State
                        
                        # Alarm 2 Settings
                        
                        # Alarms Status

                        # Ignored
                        elif DpId == 114: # Local Time Report
                            pass
                        elif DpId == 115: # Network Time vs Manual Time
                            pass
                        elif DpId == 125: # 12 or 24 Hour Time
                            pass

                        else:
                            if verbose_logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)


    # HA's _set Topics

    # HA Setting DPID 2 - Color Light State (bool)
    elif msg.topic == HA_TOPIC + 'color/state_set':
        if payload_str == 'ON':
            if verbose_logging: publog('HA: Turn Color Light On')
            if not color_light_state: publish(command_topic + 'TuyaSend1', payload='2,1')
        else:
            if verbose_logging: publog('HA: Turn Color Light Off')
            if color_light_state: publish(command_topic + 'TuyaSend1', payload='2,0')

    # HA Setting DPID 11 - Color Light Settings (12-string, 4-HUE, 4-SAT, 4-BRI but unused)
    elif msg.topic == HA_TOPIC + 'color/hs_set':
        temp1, temp2 = (float(x) for x in payload_str.split(','))
        if verbose_logging: publog('HA: Set Color Light Hue %f and Saturation %f' % (temp1, temp2))
        dpid_str = ('%04x' % int(temp1)) + ('%04x' % int(10*temp2)) + ('%04x' % 1000)
        publish(command_topic + 'TuyaSend3', payload='11,'+dpid_str)

    # HA Setting DPID 101 - Color Light Brightness (valur)
    elif msg.topic == HA_TOPIC + 'color/brightness_set':
        publish(command_topic + 'TuyaSend2', payload='101,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 104 - Night Light State (bool)
    elif msg.topic == HA_TOPIC + 'night/state_set':
        if payload_str == 'ON':
            if verbose_logging: publog('HA: Turn Night Light On')
            if not night_light_state: publish(command_topic + 'TuyaSend1', payload='104,1')
        else:
            if verbose_logging: publog('HA: Turn Night Light Off')
            if night_light_state: publish(command_topic + 'TuyaSend1', payload='104,0')

    # HA Setting DPID 124 - Night Light Brightness (value)
    elif msg.topic == HA_TOPIC + 'night/brightness_set':
        publish(command_topic + 'TuyaSend2', payload='124,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 102 - Effect Light State (bool)
    elif msg.topic == HA_TOPIC + 'effect/state_set':
        if payload_str == 'ON':
            if verbose_logging: publog('HA: Turn Effect Light On')
            if not effect_light_state: publish(command_topic + 'TuyaSend1', payload='102,1')
        else:
            if verbose_logging: publog('HA: Turn Effect Light Off')
            if effect_light_state: publish(command_topic + 'TuyaSend1', payload='102,0')

    # HA Setting DPID 123 - Effect Light Brightness (value)
    elif msg.topic == HA_TOPIC + 'effect/brightness_set':
        publish(command_topic + 'TuyaSend2', payload='123,'+str(max(10, min(1000, int(payload_str)))))

    # HA Setting DPID 103 - Effect Light Settings (raw)
    elif msg.topic == HA_TOPIC + 'effect/effect_set':
        effect_mode, effect_variation = effects_dict[payload_str]
        raw_str = '%02X000000000000000000000000000000000000000000000000000000000000000000000000000000000000%02X%02X' % (effect_mode, effect_light_speed, effect_variation)
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(103, raw_str))
    elif msg.topic == HA_TOPIC + 'effect/speed_set':
        effect_mode, effect_variation = effects_dict[effect_light_effect]
        raw_str = '%02X000000000000000000000000000000000000000000000000000000000000000000000000000000000000%02X%02X' % (effect_mode, int(payload_str), effect_variation)
        publish(command_topic + 'SerialSend5', payload=tuya_payload_raw(103, raw_str))

    # HA Setting DPID 104 - Night Light State (bool)
    # HA Setting DPID 106 - Sleep Aid State (bool)
    # HA Setting DPID 107 - Sleep Aid Settings (raw)
    # HA Setting DPID 108 - Alarm 1 State (bool)
    # HA Setting DPID 109 - Alarm 1 Settings (raw)
    # HA Setting DPID 110 - Alarm 2 State (bool)
    # HA Setting DPID 111 - Alarm 2 Settings (raw)
    # HA Setting DPID 112 - Turn Off Alarm Command

client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD )
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

# Redefine Publish with The QOS Setting
def publish(topic, payload=None, qos=MQTT_QOS, retain=False, properties=None):
    client.publish(topic, payload=payload, qos=qos, retain=retain, properties=properties)

# Basic Logging
def publog(x):
    print(x)
    publish('tony_fav_dev/log', payload=x)

client.loop_forever()