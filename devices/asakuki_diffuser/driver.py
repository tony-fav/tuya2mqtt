import os
import json
import paho.mqtt.client as mqtt
import colorsys

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT = os.getenv('MQTT_CLIENT', 'tuya2mqtt-asakuki_diffuser')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
MQTT_LOGGING = os.getenv('MQTT_LOGGING', 0)
DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
DEVICE_TYPE= os.getenv('DEVICE_TYPE')
HA_TOPIC = os.getenv('HA_TOPIC', 'tuya2mqtt/asakuki_diffuser/')

# from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, MQTT_LOGGING, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'asakuki_diffuser'

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
light_state = True
effect_light_state = True
fixed_light_state = False
night_light_state = False
weak_mist_state = False
strong_mist_state = True
mist_timer_mode = 'On'
water_warning = False
mist_time_remaining = 0
fixed_light_str = 'ff000000006464'
fixed_light_hue = 0.
fixed_light_sat = 100.
fixed_light_bri = 100
night_light_bri = 255


mist_timer_types = ['On', '1 Hour', '3 Hours', '6 Hours']
inv_mist_timer_types = {v: i for i, v in enumerate(mist_timer_types)}

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
    global light_state
    global effect_light_state
    global fixed_light_state
    global night_light_state
    global weak_mist_state
    global strong_mist_state
    global mist_timer_mode
    global water_warning
    global mist_time_remaining
    global fixed_light_hue
    global fixed_light_sat
    global fixed_light_bri
    global night_light_bri

    try:
        payload_str = str(msg.payload.decode("utf-8"))
    except:
        # the color string can get fudged up for some reason sometimes
        msg.topic == ''

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
        try:
            payload_dict = json.loads(msg.payload) # load the payload into dictionary
        except:
            payload_dict = {}
            # the color string can get fudged up for some reason sometimes 

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


                        if DpId == 1 and DpIdType == 1:
                            device_state = hex2bool[DpIdData]

                            publish(HA_TOPIC + 'state', payload=bool2payload[device_state])
                            publish(HA_TOPIC + 'mist/weak_state', payload=bool2payload[device_state and weak_mist_state])
                            publish(HA_TOPIC + 'mist/strong_state', payload=bool2payload[device_state and strong_mist_state])
                            publish(HA_TOPIC + 'light/state', payload=bool2payload[device_state and light_state])
                            publish(HA_TOPIC + 'light/effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            publish(HA_TOPIC + 'light/fixed/state', payload=bool2payload[device_state and light_state and fixed_light_state])
                            publish(HA_TOPIC + 'light/night/state', payload=bool2payload[device_state and light_state and night_light_state])

                            if logging: publog('  1: Device DpId On: %s' % device_state)

                        elif DpId == 11 and DpIdType == 1:
                            light_state = hex2bool[DpIdData]

                            publish(HA_TOPIC + 'light/state', payload=bool2payload[device_state and light_state])
                            publish(HA_TOPIC + 'light/effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            publish(HA_TOPIC + 'light/fixed/state', payload=bool2payload[device_state and light_state and fixed_light_state])
                            publish(HA_TOPIC + 'light/night/state', payload=bool2payload[device_state and light_state and night_light_state])

                            if logging: publog(' 11: Light DpId On: %s' % light_state)

                        elif DpId == 12 and DpIdType == 5:
                            water_warning = hex2bool[DpIdData]

                            publish(HA_TOPIC + 'mist/warning', payload=bool2payload[water_warning])

                            if logging: publog(' 12: Water Warning: %s' % water_warning)

                        elif DpId == 13 and DpIdType == 4:
                            mist_timer_mode = mist_timer_types[int(DpIdData, 16)]

                            publish(HA_TOPIC + 'mist/timer_mode', payload='%s' % mist_timer_mode)

                            if logging: publog(' 13: Mist Timer: %s' % mist_timer_mode)

                        elif DpId == 14 and DpIdType == 2:
                            mist_time_remaining = int(DpIdData, 16)

                            publish(HA_TOPIC + 'mist/time_remaining', payload='%d' % mist_time_remaining)

                            if logging: publog(' 14: Mist Time Remaining: %d min' % mist_time_remaining)

                        elif DpId == 103 and DpIdType == 4:
                            weak_mist_state = False
                            strong_mist_state = False
                            if DpIdData == '00':
                                weak_mist_state = True
                            elif DpIdData == '01':
                                strong_mist_state = True
                            else: # '02' = off
                                pass
                            
                            publish(HA_TOPIC + 'mist/weak_state', payload=bool2payload[device_state and weak_mist_state])
                            publish(HA_TOPIC + 'mist/strong_state', payload=bool2payload[device_state and strong_mist_state])

                            if logging: publog('103: Weak DpId On: %s' % weak_mist_state)
                            if logging: publog('103: Strong DpId On: %s' % strong_mist_state)

                        elif DpId == 108 and DpIdType == 3:
                            fixed_light_str = bytearray.fromhex(DpIdData).decode() # lowercase

                            if len(fixed_light_str) != 14:
                                pass
                            else:
                                # here, we can use the R, G, B values or the Hue, Sat, Bri values.
                                # For this device, I'm choosing Hue and Bri bc Sat == 100 always.
                                # device reports R,G,B,Hue,Sat,Val but Sat = 100 always and Val doesn't seem to matter even though bri is adjustable.
                                # i prefer to deal with HS and Bri in home assistant so i'm going to convert
                                r = int(fixed_light_str[0:2], 16)/255
                                g = int(fixed_light_str[2:4], 16)/255
                                b = int(fixed_light_str[4:6], 16)/255
                                print(r, g, b)
                                # h = int(fixed_light_str[6:10], 16)
                                # s = int(fixed_light_str[10:12], 16)
                                # v = int(fixed_light_str[12:14], 16)
                                h, s, v = colorsys.rgb_to_hsv(r, g, b)
                                print(h, s, v)
                                fixed_light_hue = int(360*h)
                                fixed_light_sat = int(100*s)
                                fixed_light_bri = int(255*v)

                                publish(HA_TOPIC + 'light/fixed/hs', payload='%f,%f' % (fixed_light_hue, fixed_light_sat))
                                publish(HA_TOPIC + 'light/fixed/bri', payload='%d' % fixed_light_bri)

                                if logging: publog('108: Fixed Light: Hue, Sat, Bri = %d, %d' % (fixed_light_hue, fixed_light_sat, fixed_light_bri))

                        elif DpId == 110 and DpIdType == 4:
                            effect_light_state = False
                            fixed_light_state = False
                            night_light_state = False
                            if DpIdData == '00':
                                effect_light_state = True
                            elif DpIdData == '01':
                                fixed_light_state = True
                            elif DpIdData == '02':
                                night_light_state = True
                            else:
                                pass

                            publish(HA_TOPIC + 'light/effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            publish(HA_TOPIC + 'light/fixed/state', payload=bool2payload[device_state and light_state and fixed_light_state])
                            publish(HA_TOPIC + 'light/night/state', payload=bool2payload[device_state and light_state and night_light_state])

                            if logging: publog('110: Effect Light DpId On: %s' % effect_light_state)
                            if logging: publog('110:  Fixed Light DpId On: %s' % fixed_light_state)
                            if logging: publog('110:  Night Light DpId On: %s' % night_light_state)

                        elif DpId == 111 and DpIdType == 2:
                            night_light_bri = int(DpIdData, 16)

                            publish(HA_TOPIC + 'light/night/bri', payload='%d' % night_light_bri)

                            if logging: publog('111: Night Light Bri: %d' % night_light_bri)


                        # DPID 109 = UNKNOWN

                        else:
                            if logging: publog(str(datapoint))
            else:
                if logging: publog('unhandled: ' + str(tuya_rec_dict))
        else:
            if logging: publog(payload_dict)

    # HA's _set Topics
    elif msg.topic == HA_TOPIC + 'state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
        else:
            if device_state: pubcom('TuyaSend1', payload='1,0')

    elif msg.topic == HA_TOPIC + 'light/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not light_state: pubcom('TuyaSend1', payload='11,1')
        else:
            if light_state: pubcom('TuyaSend1', payload='11,0')

    elif msg.topic == HA_TOPIC + 'light/effect/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not light_state: pubcom('TuyaSend1', payload='11,1')
            pubcom('TuyaSend4', payload='110,0')
        else:
            if light_state: pubcom('TuyaSend1', payload='11,0')

    elif msg.topic == HA_TOPIC + 'light/fixed/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not light_state: pubcom('TuyaSend1', payload='11,1')
            pubcom('TuyaSend4', payload='110,1')
        else:
            if light_state: pubcom('TuyaSend1', payload='11,0')

    elif msg.topic == HA_TOPIC + 'light/night/state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not light_state: pubcom('TuyaSend1', payload='11,1')
            pubcom('TuyaSend4', payload='110,2')
        else:
            if light_state: pubcom('TuyaSend1', payload='11,0')

    elif msg.topic == HA_TOPIC + 'light/fixed/hs' + '_set':
        h, s = (float(x) for x in payload_str.split(','))
        r, g, b = colorsys.hsv_to_rgb(h/360.0, s/100.0, fixed_light_bri/255.0)
        r = int(255*r)
        g = int(255*g)
        b = int(255*b)
        new_fixed_light_str = '%02x%02x%02x%04x%02x%02x' % (r, g, b, int(h), int(s), fixed_light_bri)
        pubcom('TuyaSend3', payload='108,%s' % new_fixed_light_str)

    elif msg.topic == HA_TOPIC + 'light/fixed/VCT' + '_set':
        mired = float(payload_str)
        h = interp(mired, VCT_mired, VCT_hue)
        s = interp(mired, VCT_mired, VCT_sat)
        r, g, b = colorsys.hsv_to_rgb(h/360.0, s/100.0, fixed_light_bri/255.0)
        r = int(255*r)
        g = int(255*g)
        b = int(255*b)
        new_fixed_light_str = '%02x%02x%02x%04x%02x%02x' % (r, g, b, int(h), int(s), fixed_light_bri)
        pubcom('TuyaSend3', payload='108,%s' % new_fixed_light_str)

    elif msg.topic == HA_TOPIC + 'light/fixed/bri' + '_set':
        new_fixed_light_bri = int(payload_str)
        r, g, b = colorsys.hsv_to_rgb(fixed_light_hue/360.0, fixed_light_sat/100.0, new_fixed_light_bri/255.0)
        r = int(255*r)
        g = int(255*g)
        b = int(255*b)
        new_fixed_light_str = '%02x%02x%02x%04x%02x%02x' % (r, g, b, int(fixed_light_hue), int(fixed_light_sat), new_fixed_light_bri)
        pubcom('TuyaSend3', payload='108,%s' % new_fixed_light_str)

    elif msg.topic == HA_TOPIC + 'light/night/bri' + '_set':
        pubcom('TuyaSend2', payload='111,%d' % int(payload_str))

    elif msg.topic == HA_TOPIC + 'mist/weak_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not weak_mist_state: pubcom('TuyaSend4', payload='103,0')
        else:
            if weak_mist_state: pubcom('TuyaSend4', payload='103,2')

    elif msg.topic == HA_TOPIC + 'mist/strong_state' + '_set':
        if payload_str == 'ON':
            if not device_state: pubcom('TuyaSend1', payload='1,1')
            if not strong_mist_state: pubcom('TuyaSend4', payload='103,1')
        else:
            if strong_mist_state: pubcom('TuyaSend4', payload='103,2')

    elif msg.topic == HA_TOPIC + 'mist/timer_mode' + '_set':
        pubcom('TuyaSend4', '13,%d' % inv_mist_timer_types[payload_str])

client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD)
client.will_set(HA_TOPIC + 'LWT', payload='offline', qos=MQTT_QOS, retain=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

# Redefine Publish with The QOS Setting
def publish(topic, payload=None, qos=MQTT_QOS, retain=True, properties=None):
    if payload:
        payload2publish = payload
    else:
        payload2publish = None
    client.publish(topic, payload=payload2publish, qos=qos, retain=retain, properties=properties)

# Tasmota command is a different publish that we won't use retain for
def pubcom(command, payload=None):
    client.publish(command_topic + command, payload=payload, qos=MQTT_QOS, retain=False, properties=None)

# Basic Logging over MQTT
def publog(x):
    print(x)
    if MQTT_LOGGING: publish(HA_TOPIC + 'log', payload=x)

client.loop_forever()