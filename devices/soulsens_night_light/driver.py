import os
import json
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_CLIENT = os.getenv('MQTT_CLIENT', 't2t2m2p2m2ha-soulsens_night_light')
MQTT_QOS = int(os.getenv('MQTT_QOS', 1))
DEVICE_TOPIC = os.getenv('DEVICE_TOPIC', 'tasmota_XXXXXX')
DEVICE_TYPE= os.getenv('DEVICE_TYPE', 'soulsens_night_light')
HA_TOPIC = os.getenv('HA_TOPIC', 't2t2m2p2m2ha/soulsens_night_light/')

# from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

assert DEVICE_TYPE.lower() == 'soulsens_night_light'

logging = True

# Define Extra Topics
command_topic = 'cmnd/' + DEVICE_TOPIC + '/'
state_topic = 'stat/' + DEVICE_TOPIC + '/'
telemetry_topic = 'tele/' + DEVICE_TOPIC + '/'
result_topic = 'tele/' + DEVICE_TOPIC + '/RESULT'
lwt_topic = 'tele/' + DEVICE_TOPIC + '/LWT'
if HA_TOPIC[-1] != '/': HA_TOPIC += '/'

# Define Some Defaults
light_settings = '01000A32010A0000000404'
light_state = True
white_light_state = True
white_light_brightness = 8
white_light_temperature = 100
color_light_state = False
color_light_brightness = 8
color_light_hue = 0
effect_light_state = False
effect_light_brightness = 8
effect_light_effect = 'FlameOn'

hex2bool = {'00': False, '01': True}
bool2payload = {False: 'OFF', True: 'ON'}

light_effect_types = ['','Breathe','Leap','Sunset','Candle']
inv_light_effect_types = {v: i for i, v in enumerate(light_effect_types)}


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
    global light_settings # DPID 103
    global light_state
    global white_light_state
    global white_light_brightness
    global white_light_temperature
    global color_light_state
    global color_light_brightness
    global color_light_hue
    global effect_light_state
    global effect_light_brightness
    global effect_light_effect

    payload_str = str(msg.payload.decode("utf-8"))
    # if logging: publog('%s: %s' % (msg.topic, payload_str))

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

                        if DpId == 103 and DpIdType == 0:
                            light_settings = DpIdData
                            light_state = hex2bool[DpIdData[0:2]]
                            white_light_state = hex2bool[DpIdData[2:4]]
                            white_light_brightness = int(DpIdData[4:6], 16)
                            white_light_temperature = (50000 - 347*int(DpIdData[6:8], 16)) // 100
                            color_light_state = hex2bool[DpIdData[8:10]]
                            color_light_brightness = int(DpIdData[10:12],16)
                            color_light_hue = int(DpIdData[12:16],16)
                            effect_light_state = hex2bool[DpIdData[16:18]]
                            effect_light_brightness = int(DpIdData[18:20],16)
                            effect_light_effect = int(DpIdData[20:22],16)

                            publish(HA_TOPIC + 'white/state', payload=bool2payload[light_state and white_light_state])
                            publish(HA_TOPIC + 'white/brightness', payload='%d' % white_light_brightness)
                            publish(HA_TOPIC + 'white/color_temp', payload='%d' % white_light_temperature)
                            publish(HA_TOPIC + 'color/state', payload=bool2payload[light_state and color_light_state])
                            publish(HA_TOPIC + 'color/brightness', payload='%d' % color_light_brightness)
                            publish(HA_TOPIC + 'color/hs', payload='%d,100' % color_light_hue)
                            publish(HA_TOPIC + 'effect/state', payload=bool2payload[light_state and effect_light_state])
                            publish(HA_TOPIC + 'effect/brightness', payload='%d' % effect_light_brightness)
                            publish(HA_TOPIC + 'effect/effect', payload=light_effect_types[effect_light_effect])



                            print(light_state)
                            print(white_light_state)
                            print(white_light_brightness)
                            print(white_light_temperature)
                            print(color_light_state)
                            print(color_light_brightness)
                            print(color_light_hue)
                            print(effect_light_state)
                            print(effect_light_brightness)
                            print(effect_light_effect)

                        if logging: publog(str(datapoint))
            else:
                publog('unhandled: ' + str(tuya_rec_dict))
        else:
            publog(payload_dict)


    # HA's _set Topics

    # # HA Setting DPID 2 - Color Light State (bool)
    # elif msg.topic == HA_TOPIC + 'color/state_set':
    #     if payload_str == 'ON':
    #         if logging: publog('HA: Turn Color Light On')
    #         if not color_light_state: publish(command_topic + 'TuyaSend1', payload='2,1')
    #     else:
    #         if logging: publog('HA: Turn Color Light Off')
    #         if color_light_state: publish(command_topic + 'TuyaSend1', payload='2,0')


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