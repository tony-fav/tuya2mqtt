import os
import json
import paho.mqtt.client as mqtt
import colorsys

# MQTT_HOST = os.getenv('MQTT_HOST')
# MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
# MQTT_USER = os.getenv('MQTT_USER')
# MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
# MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-mlambert_string_light_controller')
# MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
# DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
# DEVICE_TYPE= os.getenv('DEVICE_TYPE')
# HA_TOPIC = os.getenv('HA_TOPIC', 't2t2m2p2m2ha/mlambert_string_light_controller/')

from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'mlambert_string_light_controller'

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
last_scene = 2
white_state = True
color_state = False
scene_state = False
pick2_state = False
white_brightness = 255
white_temp = 153
color_r = 255
color_g = 0
color_b = 0
color_bri = 255
pick2_str = 'ffff0502c400ffff0000'
pick2_color1_r = 255
pick2_color1_g = 0
pick2_color1_b = 0
pick2_color1_bri = 255
pick2_color2_r = 0
pick2_color2_g = 255
pick2_color2_b = 0
pick2_color2_bri = 255


scene_types = ['White', 'Color', 'Strobe', 'Fade', 'Pulse', 'Blink', 'Chase', 'Christmas', 'America', 'Pick 2', 'Multi']
inv_scene_types = {v: i for i, v in enumerate(scene_types)}


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
    global last_scene
    global white_state
    global color_state
    global scene_state
    global pick2_state
    global white_brightness
    global white_temp
    global color_r
    global color_g
    global color_b
    global color_bri
    global pick2_str
    global pick2_color1_r
    global pick2_color1_g
    global pick2_color1_b
    global pick2_color1_bri
    global pick2_color2_r
    global pick2_color2_g
    global pick2_color2_b
    global pick2_color2_bri

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

                            publish(HA_TOPIC + 'white_state', payload=bool2payload[device_state and white_state])
                            publish(HA_TOPIC + 'color_state', payload=bool2payload[device_state and color_state])
                            publish(HA_TOPIC + 'pick2_state', payload=bool2payload[device_state and pick2_state])
                            publish(HA_TOPIC + 'scene_state', payload=bool2payload[device_state and scene_state])

                            if logging: publog(' 20: Device On: %s' % device_state)

                        elif DpId == 21 and DpIdType == 4:
                            mode_selector = int(DpIdData, 16)
                            mode_name = scene_types[mode_selector]
                            white_state = False
                            color_state = False
                            scene_state = False
                            pick2_state = False
                            if mode_name == 'White':
                                white_state = True
                            elif mode_name == 'Color':
                                color_state = True
                            elif mode_name == 'Pick 2':
                                pick2_state = True
                            else:
                                scene_state = True
                                last_scene = mode_selector
                                publish(HA_TOPIC + 'scene', payload=mode_name)
                            
                            publish(HA_TOPIC + 'white_state', payload=bool2payload[device_state and white_state])
                            publish(HA_TOPIC + 'color_state', payload=bool2payload[device_state and color_state])
                            publish(HA_TOPIC + 'pick2_state', payload=bool2payload[device_state and pick2_state])
                            publish(HA_TOPIC + 'scene_state', payload=bool2payload[device_state and scene_state])



                            if logging: publog(' 21: Device Mode: %s' % mode_name)

                        elif DpId == 22 and DpIdType == 2:
                            white_brightness = int(DpIdData, 16)

                            publish(HA_TOPIC + 'white_bri', payload='%d' % white_brightness)

                            if logging: publog(' 22: White Light Brightness: %d' % white_brightness)

                        elif DpId == 23 and DpIdType == 2:
                            white_temp = int(500 + (153-500)/255*int(DpIdData, 16))

                            publish(HA_TOPIC + 'white_ct', payload='%d' % white_temp)
                            # 153, cold. 500 warm in HA
                            # 0 warm, 255 cold here

                            if logging: publog(' 23: White Light Temp: %d' % white_temp)

                        elif DpId == 24 and DpIdType == 3:
                            color_str = bytearray.fromhex(DpIdData).decode() # lowercase
                            color_r = int(color_str[0:2], 16)
                            color_g = int(color_str[2:4], 16)
                            color_b = int(color_str[4:6], 16)
                            color_bri = max(color_r, color_g, color_b)
                            color_r = int(color_r*255/color_bri)
                            color_g = int(color_g*255/color_bri)
                            color_b = int(color_b*255/color_bri)
                            # color_hue = int(color_str[6:10], 16)
                            # color_sat = int(color_str[10:12], 16)
                            # color_bri = int(color_str[12:14], 16)

                            publish(HA_TOPIC + 'color_rgb', payload='%d,%d,%d' % (color_r, color_g, color_b))
                            publish(HA_TOPIC + 'color_bri', payload='%d' % color_bri)

                            if logging: publog(' 24: Fixed Light: R,G,B = %s,%s,%s' % (str(color_r), str(color_g), str(color_b)))

                        elif DpId == 101 and DpIdType == 3:
                            pick2_str = bytearray.fromhex(DpIdData).decode() # lowercase
                            pick2_color1_r = int(pick2_str[8:10], 16)
                            pick2_color1_g = int(pick2_str[10:12], 16)
                            pick2_color1_b = int(pick2_str[12:14], 16)
                            pick2_color1_bri = max(pick2_color1_r, pick2_color1_g, pick2_color1_b)
                            pick2_color1_r = int(pick2_color1_r*255/pick2_color1_bri)
                            pick2_color1_g = int(pick2_color1_g*255/pick2_color1_bri)
                            pick2_color1_b = int(pick2_color1_b*255/pick2_color1_bri)

                            pick2_color2_r = int(pick2_str[14:16], 16)
                            pick2_color2_g = int(pick2_str[16:18], 16)
                            pick2_color2_b = int(pick2_str[18:20], 16)
                            pick2_color2_bri = max(pick2_color2_r, pick2_color2_g, pick2_color2_b)
                            pick2_color2_r = int(pick2_color2_r*255/pick2_color2_bri)
                            pick2_color2_g = int(pick2_color2_g*255/pick2_color2_bri)
                            pick2_color2_b = int(pick2_color2_b*255/pick2_color2_bri)

                            publish(HA_TOPIC + 'pick2_color1_rgb', payload='%d,%d,%d' % (pick2_color1_r, pick2_color1_g, pick2_color1_b))
                            publish(HA_TOPIC + 'pick2_color2_rgb', payload='%d,%d,%d' % (pick2_color2_r, pick2_color2_g, pick2_color2_b))
                            publish(HA_TOPIC + 'pick2_color1_bri', payload='%d' % pick2_color1_bri)
                            publish(HA_TOPIC + 'pick2_color2_bri', payload='%d' % pick2_color2_bri)

                            print('101: ', pick2_color1_r, pick2_color1_g, pick2_color1_b, pick2_color1_bri, pick2_color2_r, pick2_color2_g, pick2_color2_b, pick2_color2_bri)

                        else:
                            if logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)

    # HA's _set Topics
    elif msg.topic == HA_TOPIC + 'white_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not white_state: pubcom('TuyaSend4', payload='21,0')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'color_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not color_state: pubcom('TuyaSend4', payload='21,1')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'pick2_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not pick2_state: pubcom('TuyaSend4', payload='21,9')
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'scene_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='20,1')
            if not scene_state: pubcom('TuyaSend4', payload='21,%d' % last_scene)
        else:
            if device_state: pubcom('TuyaSend1', payload='20,0')

    elif msg.topic == HA_TOPIC + 'white_bri' + '_set':
        pubcom('TuyaSend2', payload='22,%d' % int(payload_str))

    elif msg.topic == HA_TOPIC + 'white_ct' + '_set':
        pubcom('TuyaSend2', payload='23,%d' % int((int(payload_str)-500)*255/(153-500)))

    elif msg.topic == HA_TOPIC + 'color_rgb' + '_set':
        r,g,b = (int(x) for x in payload_str.split(','))
        bri = max(r,g,b)
        r = int(r/bri*color_bri)
        g = int(g/bri*color_bri)
        b = int(b/bri*color_bri)
        h,s,v = colorsys.rgb_to_hsv(r/255,g/255,b/255)
        new_color_str = '%02x%02x%02x%04x%02x%02x' % (r, g, b, int(h), int(255*s), int(255*v))
        pubcom('TuyaSend3', payload='24,%s' % new_color_str)
    
    elif msg.topic == HA_TOPIC + 'color_bri' + '_set':
        new_color_bri = int(payload_str)
        bri = max(color_r, color_g, color_b)
        r = int(color_r/bri*new_color_bri)
        g = int(color_g/bri*new_color_bri)
        b = int(color_b/bri*new_color_bri)
        h,s,v = colorsys.rgb_to_hsv(r/255,g/255,b/255)
        new_color_str = '%02x%02x%02x%04x%02x%02x' % (r, g, b, int(h), int(255*s), int(255*v))
        pubcom('TuyaSend3', payload='24,%s' % new_color_str)
        
    elif msg.topic == HA_TOPIC + 'pick2_color1_rgb' + '_set':
        r,g,b = (int(x) for x in payload_str.split(','))
        bri = max(r,g,b)
        r = int(r/bri*pick2_color1_bri)
        g = int(g/bri*pick2_color1_bri)
        b = int(b/bri*pick2_color1_bri)
        new_color_str = pick2_str[0:8] + ('%02x%02x%02x' % (r, g, b)) + pick2_str[14:20]
        pubcom('TuyaSend3', payload='101,%s' % new_color_str)
    
    elif msg.topic == HA_TOPIC + 'pick2_color1_bri' + '_set':
        new_pick2_color1_bri = int(payload_str)
        bri = max(pick2_color1_r, pick2_color1_g, pick2_color1_b)
        r = int(pick2_color1_r/bri*new_pick2_color1_bri)
        g = int(pick2_color1_g/bri*new_pick2_color1_bri)
        b = int(pick2_color1_b/bri*new_pick2_color1_bri)
        new_color_str = pick2_str[0:8] + ('%02x%02x%02x' % (r, g, b)) + pick2_str[14:20]

        pubcom('TuyaSend3', payload='101,%s' % new_color_str)
    elif msg.topic == HA_TOPIC + 'pick2_color2_rgb' + '_set':
        r,g,b = (int(x) for x in payload_str.split(','))
        bri = max(r,g,b)
        r = int(r/bri*pick2_color2_bri)
        g = int(g/bri*pick2_color2_bri)
        b = int(b/bri*pick2_color2_bri)
        new_color_str = pick2_str[0:14] + ('%02x%02x%02x' % (r, g, b))
        pubcom('TuyaSend3', payload='101,%s' % new_color_str)
    
    elif msg.topic == HA_TOPIC + 'pick2_color2_bri' + '_set':
        new_pick2_color2_bri = int(payload_str)
        bri = max(pick2_color2_r, pick2_color2_g, pick2_color2_b)
        r = int(pick2_color2_r/bri*new_pick2_color2_bri)
        g = int(pick2_color2_g/bri*new_pick2_color2_bri)
        b = int(pick2_color2_b/bri*new_pick2_color2_bri)
        new_color_str = pick2_str[0:14] + ('%02x%02x%02x' % (r, g, b))
        pubcom('TuyaSend3', payload='101,%s' % new_color_str)



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