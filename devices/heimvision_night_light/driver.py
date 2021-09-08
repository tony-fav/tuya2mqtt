import os
import json
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-heimvision_night_light')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
DEVICE_TYPE= os.getenv('DEVICE_TYPE')
HA_TOPIC = os.getenv('HA_TOPIC', 't2t2m2p2m2ha/heimvision_night_light/')

# from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'heimvision_night_light'

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
light_state = False
white_light_state = False
color_light_state = False
effect_light_state = False
white_light_brightness = 100
color_light_hue = 0
color_light_saturation = 100
color_light_brightness = 1000
device_state = False
breath_state = False
timer_state = False
timer_hours = 0
timer_minutes = 0
timer_seconds = 0
sound_state = False
sound_volume = 0
sound_choice = 0
unknown_state = 0

hex2bool = {'00': False, '01': True}
bool2payload = {False: 'OFF', True: 'ON'}

# light_effect_types = ['','Breathe','Leap','Sunset','Candle']
# inv_light_effect_types = {v: i for i, v in enumerate(light_effect_types)}

sound_types = [
    'Soothe 1', 'Soothe 2', 'Soothe 3', 'Soothe 4', 'Soothe 5', 'Soothe 6', 'Soothe 7', 'Soothe 8', 'Soothe 9', 
    'Sleep 1', 'Sleep 2', 'Sleep 3', 'Sleep 4', 'Sleep 5', 'Sleep 6', 'Sleep 7', 'Sleep 8', 'Sleep 9', 
    'Focus 1', 'Focus 2', 'Focus 3', 'Focus 4', 'Focus 5', 'Focus 6', 'Focus 7', 'Focus 8', 'Focus 9'
    ]
inv_sound_types = {v: i for i, v in enumerate(sound_types)}



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

    # Query Status (by saying "i have no cloud access, wait i do")
    pubcom('SerialSend5', payload='55aa000300010306')
    pubcom('SerialSend5', payload='55aa000300010407')

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global light_state
    global white_light_state
    global color_light_state
    global effect_light_state
    global white_light_brightness
    global color_light_hue
    global color_light_saturation
    global color_light_brightness
    global device_state
    global breath_state
    global timer_state
    global timer_hours
    global timer_minutes
    global timer_seconds
    global sound_state
    global sound_volume
    global sound_choice
    global unknown_state

    try:
        payload_str = str(msg.payload.decode("utf-8"))
    except:
        return
    # if logging: publog('%s: %s' % (msg.topic, payload_str))

    if msg.topic == lwt_topic:
        if payload_str == 'Online':
            publish(HA_TOPIC + 'LWT', payload='online')
            
            # Query Status (by saying "i have no cloud access, wait i do")
            pubcom('SerialSend5', payload='55aa000300010306')
            pubcom('SerialSend5', payload='55aa000300010407')
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
                    pubcom('TuyaSend0', payload='') # ask for state again
                    if logging: publog('Heart Beat 0: Detected MCU Reset')
                else:
                    pass
                    # if logging: publog('Heart Beat 1')
            
            # Tuya MCU Sent Product Information (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 1:
                if logging: publog('Got Product Info')

            # Tuya MCU Sent Working Mode (Tasmota handles this)
            elif tuya_rec_dict['Cmnd'] == 2:
                if logging: publog('Got Working Mode')

            elif tuya_rec_dict['Cmnd'] == 3:
                if logging: publog('MCU Ack Network Status')

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

                        if DpId == 20 and DpIdType == 1:
                            light_state = hex2bool[DpIdData]
                            publish(HA_TOPIC + 'white/state', payload=bool2payload[device_state and light_state and white_light_state])
                            publish(HA_TOPIC + 'color/state', payload=bool2payload[device_state and light_state and color_light_state])
                            publish(HA_TOPIC + 'effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            if logging: publog(' 20: Light On: %s' % light_state)

                        elif DpId == 21 and DpIdType == 4:
                            if DpIdData == '00':
                                white_light_state = True
                                color_light_state = False
                                effect_light_state = False
                                if logging: publog(' 21: White Light On: %s' % white_light_state)
                            elif DpIdData == '01':
                                white_light_state = False
                                color_light_state = True
                                effect_light_state = False
                                if logging: publog(' 21: Color Light On: %s' % color_light_state)
                            elif DpIdData == '02':
                                white_light_state = False
                                color_light_state = False
                                effect_light_state = True
                                if logging: publog(' 21: Effect Light On: %s' % effect_light_state)
                            else:
                                if logging: publog(' 21: UNKNOWN VALUE %s' % DpIdData)
                            publish(HA_TOPIC + 'white/state', payload=bool2payload[device_state and light_state and white_light_state])
                            publish(HA_TOPIC + 'color/state', payload=bool2payload[device_state and light_state and color_light_state])
                            publish(HA_TOPIC + 'effect/state', payload=bool2payload[device_state and light_state and effect_light_state])

                        elif DpId == 22 and DpIdType == 2:
                            white_light_brightness = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'white/brightness', payload='%d' % white_light_brightness)
                            if logging: publog(' 22: White Brightness (10-1000) %s' % white_light_brightness)

                        elif DpId == 24 and DpIdType == 3:
                            color_str = bytearray.fromhex(DpIdData).decode()
                            color_light_hue = 1.0*int.from_bytes(bytearray.fromhex(color_str[0:4]), 'big')
                            color_light_saturation = int.from_bytes(bytearray.fromhex(color_str[4:8]), 'big')/10.0
                            color_light_brightness = int.from_bytes(bytearray.fromhex(color_str[8:12]), 'big')
                            publish(HA_TOPIC + 'color/hs', payload='%f,%f' % (color_light_hue, color_light_saturation))
                            publish(HA_TOPIC + 'color/brightness', payload='%d' % color_light_brightness)
                            if logging: publog(' 24: Color Light: Hue %s, Saturation (1-100) %s, Brightness (10-1000) %s' % (str(color_light_hue), str(color_light_saturation), str(color_light_brightness)))

                        elif DpId == 101 and DpIdType == 1:
                            device_state = hex2bool[DpIdData]
                            publish(HA_TOPIC + 'device/state', payload=bool2payload[device_state])
                            publish(HA_TOPIC + 'white/state', payload=bool2payload[device_state and light_state and white_light_state])
                            publish(HA_TOPIC + 'color/state', payload=bool2payload[device_state and light_state and color_light_state])
                            publish(HA_TOPIC + 'effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            publish(HA_TOPIC + 'sound/state', payload=bool2payload[device_state and sound_state])
                            if logging: publog('101: Device On: %s' % device_state)

                        elif DpId == 104 and DpIdType == 1:
                            breath_state = hex2bool[DpIdData]
                            if breath_state:
                                publish(HA_TOPIC + 'color/effect', payload='Breath')
                            else:
                                publish(HA_TOPIC + 'color/effect', payload='None')
                            if logging: publog('104: Breath the Light (White and Color; not Effect): %s' % breath_state)

                        elif DpId == 105 and DpIdType == 0:
                            timer_state = hex2bool[DpIdData[0:2]]
                            timer_hours = int.from_bytes(bytearray.fromhex(DpIdData[2:4]), 'big')
                            timer_minutes = int.from_bytes(bytearray.fromhex(DpIdData[4:6]), 'big')
                            timer_seconds = int.from_bytes(bytearray.fromhex(DpIdData[6:8]), 'big')
                            publish(HA_TOPIC + 'timer/state', payload=bool2payload[timer_state])
                            publish(HA_TOPIC + 'timer/hours', payload='%d' % timer_hours)
                            publish(HA_TOPIC + 'timer/minutes', payload='%d' % timer_minutes)
                            publish(HA_TOPIC + 'timer/seconds', payload='%d' % timer_seconds)
                            publish(HA_TOPIC + 'timer/total_seconds', payload='%d' % (3600*timer_hours + 60*timer_minutes + timer_seconds))
                            if logging: publog('105: Timer: State %s, %d:%02d:%02d' % (timer_state, timer_hours, timer_minutes, timer_seconds))

                        elif DpId == 106 and DpIdType == 4:
                            sound_state = hex2bool[DpIdData]
                            publish(HA_TOPIC + 'sound/state', payload=bool2payload[device_state and sound_state])
                            if logging: publog('106: Sound On: %s' % sound_state)

                        elif DpId == 108 and DpIdType == 2:
                            sound_volume = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'sound/volume', payload='%d' % sound_volume)
                            if logging: publog('108: Sound Volume (5 to 95): %s' % sound_volume)

                        elif DpId == 109 and DpIdType == 2:
                            sound_choice = int.from_bytes(bytearray.fromhex(DpIdData), 'big')
                            publish(HA_TOPIC + 'sound/choice', payload=sound_types[sound_choice])
                            if logging: publog('109: Sound Choice (0 to 26): %s' % sound_choice)
                            
                        elif DpId == 112 and DpIdType == 1:
                            unknown_state = hex2bool[DpIdData]
                            publish(HA_TOPIC + 'unknown/state', payload=bool2payload[unknown_state])
                            if logging: publog('112: Unknown: %s' % unknown_state)

                        else:
                            if logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)


    # HA's _set Topics
    elif msg.topic == HA_TOPIC + 'white/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='101,1')
            if not white_light_state: pubcom('TuyaSend4', payload='21,0')
            if not light_state: pubcom('TuyaSend1', payload='20,1')
        else:
            if light_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'color/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='101,1')
            if not color_light_state: pubcom('TuyaSend4', payload='21,1')
            if not color_light_state: pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(color_light_hue), int(10*color_light_saturation), color_light_brightness))
            if not light_state: pubcom('TuyaSend1', payload='20,1')
        else:
            if light_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'effect/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='101,1')
            if not effect_light_state: pubcom('TuyaSend4', payload='21,2')
            if not light_state: pubcom('TuyaSend1', payload='20,1')
        else:
            if light_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'white/brightness' + '_set':
        pubcom('TuyaSend2', payload='22,%d' % max(10, int(payload_str)))

    elif msg.topic == HA_TOPIC + 'color/brightness' + '_set':
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(color_light_hue), int(10*color_light_saturation), max(10, int(payload_str))))

    elif msg.topic == HA_TOPIC + 'color/hs' + '_set':
        temp1, temp2 = (float(x) for x in payload_str.split(','))
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(temp1), int(10*temp2), color_light_brightness))

    elif msg.topic == HA_TOPIC + 'color/effect' + '_set':
        if payload_str == 'None':
            pubcom('TuyaSend1', payload='104,0')
        elif payload_str == 'Breath':
            pubcom('TuyaSend1', payload='104,1')
        else:
            publog('unknown color/effect_set %s' % payload_str)

    elif msg.topic == HA_TOPIC + 'sound/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='101,1')
            if not sound_state: pubcom('TuyaSend4', payload='106,1')
        else:
            if sound_state: pubcom('TuyaSend4', payload='106,0')

    elif msg.topic == HA_TOPIC + 'sound/volume' + '_set':
        pubcom('TuyaSend2', payload='108,%d' % max(5, int(payload_str)))

    elif msg.topic == HA_TOPIC + 'sound/choice' + '_set':
        pubcom('TuyaSend2', payload='109,%d' % inv_sound_types[payload_str])

    elif msg.topic == HA_TOPIC + 'timer/state' + '_set':
        if payload_str == 'ON':
            if sound_state and (timer_hours+timer_minutes+timer_seconds > 0): 
                raw_str = '01'
            else:
                raw_str = '00'
        else:
            raw_str = '00'
        raw_str = raw_str + '%02x%02x%02x' % (timer_hours, timer_minutes, timer_seconds)
        pubcom('SerialSend5', payload=tuya_payload_raw(105, raw_str))

    elif msg.topic == HA_TOPIC + 'timer/hours' + '_set':
        if timer_state:
            raw_str = '01'
        else:
            raw_str = '00'
        raw_str = raw_str + '%02x%02x%02x' % (int(payload_str), timer_minutes, timer_seconds)
        pubcom('SerialSend5', payload=tuya_payload_raw(105, raw_str))

    elif msg.topic == HA_TOPIC + 'timer/minutes' + '_set':
        if timer_state:
            raw_str = '01'
        else:
            raw_str = '00'
        raw_str = raw_str + '%02x%02x%02x' % (timer_hours, int(payload_str), timer_seconds)
        pubcom('SerialSend5', payload=tuya_payload_raw(105, raw_str))

    elif msg.topic == HA_TOPIC + 'timer/seconds' + '_set':
        if timer_state:
            raw_str = '01'
        else:
            raw_str = '00'
        raw_str = raw_str + '%02x%02x%02x' % (timer_hours, timer_minutes, int(payload_str))
        pubcom('SerialSend5', payload=tuya_payload_raw(105, raw_str))
        
    elif msg.topic == HA_TOPIC + 'unknown/state' + '_set':
        if payload_str == 'ON':
            if not unknown_state: pubcom('TuyaSend1', payload='112,1')
        else:
            if unknown_state: pubcom('TuyaSend1', payload='112,0')

    elif msg.topic == HA_TOPIC + 'device/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='101,1')
        else:
            if device_state: pubcom('TuyaSend1', payload='101,0')

    elif msg.topic == HA_TOPIC + 'color/VCT' + '_set':
        mired = float(payload_str)
        hue = interp(mired, VCT_mired, VCT_hue)
        sat = interp(mired, VCT_mired, VCT_sat)
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(hue), int(10*sat), color_light_brightness))





client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD)
client.will_set(HA_TOPIC + 'LWT', payload='offline', qos=MQTT_QOS, retain=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

# Redefine Publish with The QOS Setting
def publish(topic, payload=None, qos=MQTT_QOS, retain=True, properties=None):
    client.publish(topic, payload=payload, qos=qos, retain=retain, properties=properties)

def pubcom(command, payload=None):
    client.publish(command_topic + command, payload=payload, qos=MQTT_QOS, retain=False, properties=None)

# Basic Logging over MQTT
def publog(x):
    print(x)
    publish('tony_fav_dev/log', payload=x)

client.loop_forever()