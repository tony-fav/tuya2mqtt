import os
import json
import paho.mqtt.client as mqtt

# MQTT_HOST = os.getenv('MQTT_HOST')
# MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
# MQTT_USER = os.getenv('MQTT_USER')
# MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
# MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-fairy_light_controller')
# MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
# DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
# DEVICE_TYPE= os.getenv('DEVICE_TYPE')
# HA_TOPIC = os.getenv('HA_TOPIC', 't2t2m2p2m2ha/fairy_light_controller/')

from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'fairy_light_controller'

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
device_state = True
mode_selector = 0
fixed_light_state = True
scene_light_state = False
music_light_state = False
fixed_str = '000003e803e8' 
fixed_light_hue = 0.0
fixed_light_sat = 100.0
fixed_light_brightness = 1000
scene_str = '0103E8'
scene_selection = 1
scene_brightness = 1000
sleep_timer = 0
music_str = '16403E81000803E803E8'
music_mode_selector = 1
music_sensitivity = 100
music_brightness = 1000
music_auto_color = 1
music_hue = 0.0
music_sat = 100.0
music_val = 1000

scene_types = ['', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20']
inv_scene_types = {v: i for i, v in enumerate(scene_types)}

music_types = {(1,1): 'Energy - Auto', (2,0): 'Rhythm - Pick', (3,0): 'Spectrum - Pick', (4,0): 'Rolling - Pick', (2,1): 'Rhythm - Auto', (3,1): 'Spectrum - Auto', (4,1): 'Rolling - Auto'}
inv_music_types = {v: k for k, v in music_types.items()}

# Things I sometimes use if I'm smart in the moment
hex2bool = {'00': False, '01': True}
bool2payload = {False: 'OFF', True: 'ON'}
bool2hex = {False: '00', True: '01'}
payload2hex = {'OFF': '00', 'ON': '01'}
binary_payload = ['OFF', 'ON']
inv_binary_payload = {'OFF': 0, 'ON': 1}

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
    pubcom('TuyaSend0', payload='')

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global device_state
    global mode_selector
    global fixed_light_state
    global scene_light_state
    global music_light_state
    global fixed_str
    global fixed_light_hue
    global fixed_light_sat
    global fixed_light_brightness
    global scene_str
    global scene_selection
    global scene_brightness
    global sleep_timer
    global music_str
    global music_mode_selector
    global music_sensitivity
    global music_brightness
    global music_auto_color
    global music_hue
    global music_sat
    global music_val

    payload_str = str(msg.payload.decode("utf-8"))
    # if logging: publog('%s: %s' % (msg.topic, payload_str))

    if msg.topic == lwt_topic:
        if payload_str == 'Online':
            publish(HA_TOPIC + 'LWT', payload='online')

            # Query Status
            pubcom('TuyaSend0', payload='')
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

                        # print('-----\n', DpIdData, '\n', bytearray.fromhex(DpIdData).decode())

                        if DpId == 20 and DpIdType == 1:
                            device_state = hex2bool[DpIdData]

                            publish(HA_TOPIC + 'device/state', payload=bool2payload[device_state])
                            publish(HA_TOPIC + 'fixed/state', payload=bool2payload[device_state and fixed_light_state])
                            publish(HA_TOPIC + 'scene/state', payload=bool2payload[device_state and scene_light_state])
                            publish(HA_TOPIC + 'music/state', payload=bool2payload[device_state and music_light_state])

                            if logging: publog(' 20: Device On: %s' % device_state)

                        elif DpId == 21 and DpIdType == 4:
                            mode_selector = int(DpIdData, 16)
                            fixed_light_state = False
                            scene_light_state = False
                            music_light_state = False
                            if mode_selector == 0:
                                fixed_light_state = True
                            elif mode_selector == 1:
                                scene_light_state = True
                            elif mode_selector == 2:
                                music_light_state = True
                            else:
                                print('unknown light mode selection')

                            publish(HA_TOPIC + 'fixed/state', payload=bool2payload[device_state and fixed_light_state])
                            publish(HA_TOPIC + 'scene/state', payload=bool2payload[device_state and scene_light_state])
                            publish(HA_TOPIC + 'music/state', payload=bool2payload[device_state and music_light_state])

                            if logging: publog(' 21: Device Mode: Fixed = %s, Scene = %s, Music = %s' % (fixed_light_state, scene_light_state, music_light_state))

                        elif DpId == 24 and DpIdType == 3:
                            fixed_str = bytearray.fromhex(DpIdData).decode() # lowercase
                            fixed_light_hue = 1.0*int(fixed_str[0:4], 16)
                            fixed_light_sat = int(fixed_str[4:8], 16)/10.0
                            fixed_light_brightness = int(fixed_str[8:12], 16)

                            publish(HA_TOPIC + 'fixed/hs', payload='%f,%f' % (fixed_light_hue, fixed_light_sat))
                            publish(HA_TOPIC + 'fixed/brightness', payload='%d' % fixed_light_brightness)

                            if logging: publog(' 24: Fixed Light: Hue %s, Saturation (1-100) %s, Brightness (10-1000) %s' % (str(fixed_light_hue), str(fixed_light_sat), str(fixed_light_brightness)))

                        elif DpId == 25 and DpIdType == 3:
                            scene_str = bytearray.fromhex(DpIdData).decode() # uppercase
                            scene_selection = int(scene_str[0:2]) # for some reason this isn't hex, it's dec
                            scene_brightness = int(scene_str[2:6], 16)

                            publish(HA_TOPIC + 'scene/effect', payload='%s' % scene_types[scene_selection])
                            publish(HA_TOPIC + 'scene/brightness', payload='%d' % scene_brightness)

                            if logging: publog(' 25: Scene Light: Selection %s, Brightness (10-1000) %s' % (str(scene_selection), str(scene_brightness)))

                        elif DpId == 26 and DpIdType == 2:
                            sleep_timer = int(DpIdData, 16)

                            publish(HA_TOPIC + 'sleep_timer', payload='%d' % sleep_timer)

                            if logging: publog(' 26: Sleep Timer (sec) %s' % sleep_timer)

                        elif DpId == 101 and DpIdType == 3:
                            music_str = bytearray.fromhex(DpIdData).decode() # uppercase
                            music_mode_selector = int(music_str[0])
                            music_sensitivity = int(music_str[1:3], 16)
                            music_brightness = int(music_str[3:7], 16)
                            music_auto_color = int(music_str[7])
                            music_hue = 1.0*int(music_str[8:12], 16)
                            music_sat = int(music_str[12:16], 16)/10.0
                            music_val = int(music_str[16:20], 16) # unused, always 03E8

                            publish(HA_TOPIC + 'music/effect', payload='%s' % music_types[(music_mode_selector, music_auto_color)])
                            publish(HA_TOPIC + 'music/sensitivity', payload='%d' % music_sensitivity)
                            publish(HA_TOPIC + 'music/brightness', payload='%d' % music_brightness)
                            publish(HA_TOPIC + 'music/hs', payload='%f,%f' % (music_hue,music_sat))

                            print('101: ', music_mode_selector, music_sensitivity, music_brightness, music_auto_color, music_hue, music_sat, music_val)

                        else:
                            if logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)

    # HA's _set Topics
    elif msg.topic == HA_TOPIC + 'fixed/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not fixed_light_state: pubcom('TuyaSend4', payload='21,0')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'fixed/brightness' + '_set':
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(fixed_light_hue), int(10*fixed_light_sat), max(10, int(payload_str))))

    elif msg.topic == HA_TOPIC + 'fixed/hs' + '_set':
        temp1, temp2 = (float(x) for x in payload_str.split(','))
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(temp1), int(10*temp2), fixed_light_brightness))

    elif msg.topic == HA_TOPIC + 'fixed/VCT' + '_set':
        mired = float(payload_str)
        hue = interp(mired, VCT_mired, VCT_hue)
        sat = interp(mired, VCT_mired, VCT_sat)
        pubcom('TuyaSend3', payload='24,%04x%04x%04x' % (int(hue), int(10*sat), fixed_light_brightness))

    elif msg.topic == HA_TOPIC + 'scene/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not scene_light_state: pubcom('TuyaSend4', payload='21,1')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'scene/brightness' + '_set':
        pubcom('TuyaSend3', payload='25,%02d%04X' % (scene_selection, int(payload_str)))

    elif msg.topic == HA_TOPIC + 'scene/effect' + '_set':
        pubcom('TuyaSend3', payload='25,%02d%04X' % (inv_scene_types[payload_str], scene_brightness))

    elif msg.topic == HA_TOPIC + 'music/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not music_light_state: pubcom('TuyaSend4', payload='21,2')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'music/effect' + '_set':
        new_music_mode_selector, new_music_auto_color = inv_music_types[payload_str]
        new_music_str = '%01d%02X%04X%01d%04X%04X%04X' % (new_music_mode_selector, music_sensitivity, music_brightness, new_music_auto_color, int(music_hue), int(10*music_sat), 1000)
        pubcom('TuyaSend3', payload='101,%s' % new_music_str)

    elif msg.topic == HA_TOPIC + 'music/sensitivity' + '_set':
        new_music_str = '%01d%02X%04X%01d%04X%04X%04X' % (music_mode_selector, int(payload_str), music_brightness, music_auto_color, int(music_hue), int(10*music_sat), 1000)
        pubcom('TuyaSend3', payload='101,%s' % new_music_str)

    elif msg.topic == HA_TOPIC + 'music/brightness' + '_set':
        new_music_str = '%01d%02X%04X%01d%04X%04X%04X' % (music_mode_selector, music_sensitivity, int(payload_str), music_auto_color, int(music_hue), int(10*music_sat), 1000)
        pubcom('TuyaSend3', payload='101,%s' % new_music_str)

    elif msg.topic == HA_TOPIC + 'music/hs' + '_set':
        temp1, temp2 = (float(x) for x in payload_str.split(','))
        new_music_str = '%01d%02X%04X%01d%04X%04X%04X' % (music_mode_selector, music_sensitivity, music_brightness, music_auto_color, int(temp1), int(10*temp2), 1000)
        pubcom('TuyaSend3', payload='101,%s' % new_music_str)

    elif msg.topic == HA_TOPIC + 'music/VCT' + '_set':
        mired = float(payload_str)
        hue = interp(mired, VCT_mired, VCT_hue)
        sat = interp(mired, VCT_mired, VCT_sat)
        new_music_str = '%01d%02X%04X%01d%04X%04X%04X' % (music_mode_selector, music_sensitivity, music_brightness, music_auto_color, int(hue), int(10*sat), 1000)
        pubcom('TuyaSend3', payload='101,%s' % new_music_str)

client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD)
client.will_set(HA_TOPIC + 'LWT', payload='offline', qos=MQTT_QOS, retain=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

# Redefine Publish with The QOS Setting
def publish(topic, payload=None, qos=MQTT_QOS, retain=True, properties=None):
    client.publish(topic, payload=payload, qos=qos, retain=retain, properties=properties)

# Tasmota command is a different publish that we won't use retain for
def pubcom(command, payload=None):
    client.publish(command_topic + command, payload=payload, qos=MQTT_QOS, retain=False, properties=None)

# Basic Logging over MQTT
def publog(x):
    print(x)
    publish('tony_fav_dev/log', payload=x)

client.loop_forever()