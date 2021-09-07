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

from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT, MQTT_QOS, DEVICE_TOPIC, DEVICE_TYPE, HA_TOPIC

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
device_state = True
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
sound_settings = '00010100'
sound_state = False
sound_effect = 1
sound_volume = 1
sound_timer = 0

alarm_settings = '000000647F080F0A000000647F080F0A000000647F080F0A000000647F080F0A'

alarm_1_settings = '000000647F080F0A'
alarm_1_state = False
alarm_1_time = 480
alarm_1_brightness = 1
alarm_1_days = '0000000'
alarm_1_sound = 0
alarm_1_volume = 1
alarm_1_snooze = 5

alarm_2_settings = '000000647F080F0A'
alarm_2_state = False
alarm_2_time = 480
alarm_2_brightness = 1
alarm_2_days = '0000000'
alarm_2_sound = 0
alarm_2_volume = 1
alarm_2_snooze = 5

alarm_3_settings = '000000647F080F0A'
alarm_3_state = False
alarm_3_time = 480
alarm_3_brightness = 1
alarm_3_days = '0000000'
alarm_3_sound = 0
alarm_3_volume = 1
alarm_3_snooze = 5

alarm_4_settings = '000000647F080F0A'
alarm_4_state = False
alarm_4_time = 480
alarm_4_brightness = 1
alarm_4_days = '0000000'
alarm_4_sound = 0
alarm_4_volume = 1
alarm_4_snooze = 5


sleep_settings = '1E000001010F01010A64000A0000000A01'
sleep_time_settings = '1E00'
sleep_state = False
sleep_sound_settings = '01010F'
sleep_light_settings = '01010A64000A0000000A01'


hex2bool = {'00': False, '01': True}
bool2payload = {False: 'OFF', True: 'ON'}
binary_payload = ['OFF', 'ON']
inv_binary_payload = {'OFF': 0, 'ON': 1}

light_effect_types = ['','Breathe','Leap','Sunset','Candle']
inv_light_effect_types = {v: i for i, v in enumerate(light_effect_types)}

sound_effect_types = ['None', 'Ocean', 'Thunder', 'Rain', 'Stream', 'Rainforest', 'Wind', 'Deep space', 'Bird', 'Cricket', 'Whale', 'White Noise', 'Pink Noise', 'Fan', 'Hairdryer', 'Lullaby', 'Piano', 'Wind Chimes']
inv_sound_effect_types = {v: i for i, v in enumerate(sound_effect_types)}

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
    global device_state # DPID 20

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

    global sound_settings # DPID 104
    global sound_state
    global sound_effect
    global sound_volume
    global sound_timer

    global alarm_settings # DPID 101

    global alarm_1_settings
    global alarm_1_state
    global alarm_1_time
    global alarm_1_brightness
    global alarm_1_days
    global alarm_1_sound
    global alarm_1_volume
    global alarm_1_snooze
    
    global alarm_2_settings
    global alarm_2_state
    global alarm_2_time
    global alarm_2_brightness
    global alarm_2_days
    global alarm_2_sound
    global alarm_2_volume
    global alarm_2_snooze
    
    global alarm_3_settings
    global alarm_3_state
    global alarm_3_time
    global alarm_3_brightness
    global alarm_3_days
    global alarm_3_sound
    global alarm_3_volume
    global alarm_3_snooze
    
    global alarm_4_settings
    global alarm_4_state
    global alarm_4_time
    global alarm_4_brightness
    global alarm_4_days
    global alarm_4_sound
    global alarm_4_volume
    global alarm_4_snooze

    global sleep_settings
    global sleep_time_settings
    global sleep_state
    global sleep_sound_settings
    global sleep_light_settings
    global sleep_time_minutes
    global sleep_time_seconds
    global sleep_sound_state
    global sleep_sound_effect
    global sleep_sound_volume
    global sleep_light_state 
    global sleep_white_light_state
    global sleep_white_light_brightness
    global sleep_white_light_temperature
    global sleep_color_light_state
    global sleep_color_light_brightness
    global sleep_color_light_hue
    global sleep_effect_light_state
    global sleep_effect_light_brightness
    global sleep_effect_light_effect

    global sleep_remaining_time_minutes
    global sleep_remaining_time_seconds

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
                    pubcom('TuyaSend0', payload='') # ask for state again
                    if logging: publog('Heart Beat 0: Detected MCU Reset')
                else:
                    # if logging: publog('Heart Beat 1')
                    pass
            
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
                pass
                # if logging: publog('Got Request for Local Time')

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

                        #  20  1 bool Device On/Off
                        if DpId == 20 and DpIdType == 1:
                            device_state = hex2bool[DpIdData]
                            publish(HA_TOPIC + 'device/state', payload=bool2payload[device_state])

                        # 103 11  raw Light Settings
                        elif DpId == 103 and DpIdType == 0:
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
                            publish(HA_TOPIC + 'white/state', payload=bool2payload[device_state and light_state and white_light_state])
                            publish(HA_TOPIC + 'white/brightness', payload='%d' % white_light_brightness) # scale 20
                            publish(HA_TOPIC + 'white/color_temp', payload='%d' % white_light_temperature) # mireds, already adjusted calculation
                            publish(HA_TOPIC + 'color/state', payload=bool2payload[device_state and light_state and color_light_state])
                            publish(HA_TOPIC + 'color/brightness', payload='%d' % color_light_brightness) # scale 20
                            publish(HA_TOPIC + 'color/hs', payload='%d,100' % color_light_hue)
                            publish(HA_TOPIC + 'effect/state', payload=bool2payload[device_state and light_state and effect_light_state])
                            publish(HA_TOPIC + 'effect/brightness', payload='%d' % effect_light_brightness) # scale 20
                            publish(HA_TOPIC + 'effect/effect', payload=light_effect_types[effect_light_effect])

                        # 104  4  raw Sound Settings
                        elif DpId == 104 and DpIdType == 0:
                            sound_settings = DpIdData
                            sound_state = hex2bool[DpIdData[0:2]]
                            sound_effect = int(DpIdData[2:4], 16)
                            sound_volume = int(DpIdData[4:6], 16) # 1 to 15
                            sound_timer = int(DpIdData[6:8], 16) # minutes
                            publish(HA_TOPIC + 'sound/state', payload=bool2payload[device_state and sound_state])
                            publish(HA_TOPIC + 'sound/effect', payload=sound_effect_types[sound_effect])
                            publish(HA_TOPIC + 'sound/volume', payload='%d' % sound_volume) # scale 15
                            publish(HA_TOPIC + 'sound/timer', payload='%d' % sound_timer)

                        # 101 32  raw Alarm Settings
                        elif DpId == 101 and DpIdType == 0:
                            alarm_settings = DpIdData
                            alarm_1_settings = alarm_settings[0:16]
                            alarm_2_settings = alarm_settings[16:32]
                            alarm_3_settings = alarm_settings[32:48]
                            alarm_4_settings = alarm_settings[48:64]

                            alarm_1_state = hex2bool[alarm_1_settings[0:2]]
                            alarm_1_time = int(alarm_1_settings[2:6], 16) # minutes
                            alarm_1_brightness = int(alarm_1_settings[6:8], 16) # 1 to 100 scale
                            alarm_1_days = str(bin(int(alarm_1_settings[8:10],16)))[2:]
                            alarm_1_days = '0'*(7 - len(alarm_1_days)) + alarm_1_days
                            alarm_1_sound = int(alarm_1_settings[10:12], 16) # 0 to all
                            alarm_1_volume = int(alarm_1_settings[12:14], 16) # 1 to 15
                            alarm_1_snooze = int(alarm_1_settings[14:16], 16) # minutes
                            publish(HA_TOPIC + 'alarms/alarm_1/state', payload=bool2payload[alarm_1_state])
                            publish(HA_TOPIC + 'alarms/alarm_1/time_hour', payload='%d' % (alarm_1_time // 60))
                            publish(HA_TOPIC + 'alarms/alarm_1/time_minute', payload='%d' % (alarm_1_time % 60))
                            publish(HA_TOPIC + 'alarms/alarm_1/brightness', payload='%d' % alarm_1_brightness)
                            publish(HA_TOPIC + 'alarms/alarm_1/sound', payload=sound_effect_types[alarm_1_sound])
                            publish(HA_TOPIC + 'alarms/alarm_1/volume', payload='%d' % alarm_1_volume)
                            publish(HA_TOPIC + 'alarms/alarm_1/snooze', payload='%d' % alarm_1_snooze)
                            publish(HA_TOPIC + 'alarms/alarm_1/sun', payload=binary_payload[int(alarm_1_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_1/mon', payload=binary_payload[int(alarm_1_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_1/tue', payload=binary_payload[int(alarm_1_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_1/wed', payload=binary_payload[int(alarm_1_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_1/thu', payload=binary_payload[int(alarm_1_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_1/fri', payload=binary_payload[int(alarm_1_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_1/sat', payload=binary_payload[int(alarm_1_days[6])])

                            alarm_2_state = hex2bool[alarm_2_settings[0:2]]
                            alarm_2_time = int(alarm_2_settings[2:6], 16) # minutes
                            alarm_2_brightness = int(alarm_2_settings[6:8], 16) # 1 to 100 scale
                            alarm_2_days = str(bin(int(alarm_2_settings[8:10],16)))[2:]
                            alarm_2_days = '0'*(7 - len(alarm_2_days)) + alarm_2_days
                            alarm_2_sound = int(alarm_2_settings[10:12], 16) # 0 to all
                            alarm_2_volume = int(alarm_2_settings[12:14], 16) # 1 to 15
                            alarm_2_snooze = int(alarm_2_settings[14:16], 16) # minutes
                            publish(HA_TOPIC + 'alarms/alarm_2/state', payload=bool2payload[alarm_2_state])
                            publish(HA_TOPIC + 'alarms/alarm_2/time_hour', payload='%d' % (alarm_2_time // 60))
                            publish(HA_TOPIC + 'alarms/alarm_2/time_minute', payload='%d' % (alarm_2_time % 60))
                            publish(HA_TOPIC + 'alarms/alarm_2/brightness', payload='%d' % alarm_2_brightness)
                            publish(HA_TOPIC + 'alarms/alarm_2/sound', payload=sound_effect_types[alarm_2_sound])
                            publish(HA_TOPIC + 'alarms/alarm_2/volume', payload='%d' % alarm_2_volume)
                            publish(HA_TOPIC + 'alarms/alarm_2/snooze', payload='%d' % alarm_2_snooze)
                            publish(HA_TOPIC + 'alarms/alarm_2/sun', payload=binary_payload[int(alarm_2_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_2/mon', payload=binary_payload[int(alarm_2_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_2/tue', payload=binary_payload[int(alarm_2_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_2/wed', payload=binary_payload[int(alarm_2_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_2/thu', payload=binary_payload[int(alarm_2_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_2/fri', payload=binary_payload[int(alarm_2_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_2/sat', payload=binary_payload[int(alarm_2_days[6])])

                            alarm_3_state = hex2bool[alarm_3_settings[0:2]]
                            alarm_3_time = int(alarm_3_settings[2:6], 16) # minutes
                            alarm_3_brightness = int(alarm_3_settings[6:8], 16) # 1 to 100 scale
                            alarm_3_days = str(bin(int(alarm_3_settings[8:10],16)))[2:]
                            alarm_3_days = '0'*(7 - len(alarm_3_days)) + alarm_3_days
                            alarm_3_sound = int(alarm_3_settings[10:12], 16) # 0 to all
                            alarm_3_volume = int(alarm_3_settings[12:14], 16) # 1 to 15
                            alarm_3_snooze = int(alarm_3_settings[14:16], 16) # minutes
                            publish(HA_TOPIC + 'alarms/alarm_3/state', payload=bool2payload[alarm_3_state])
                            publish(HA_TOPIC + 'alarms/alarm_3/time_hour', payload='%d' % (alarm_3_time // 60))
                            publish(HA_TOPIC + 'alarms/alarm_3/time_minute', payload='%d' % (alarm_3_time % 60))
                            publish(HA_TOPIC + 'alarms/alarm_3/brightness', payload='%d' % alarm_3_brightness)
                            publish(HA_TOPIC + 'alarms/alarm_3/sound', payload=sound_effect_types[alarm_3_sound])
                            publish(HA_TOPIC + 'alarms/alarm_3/volume', payload='%d' % alarm_3_volume)
                            publish(HA_TOPIC + 'alarms/alarm_3/snooze', payload='%d' % alarm_3_snooze)
                            publish(HA_TOPIC + 'alarms/alarm_3/sun', payload=binary_payload[int(alarm_3_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_3/mon', payload=binary_payload[int(alarm_3_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_3/tue', payload=binary_payload[int(alarm_3_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_3/wed', payload=binary_payload[int(alarm_3_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_3/thu', payload=binary_payload[int(alarm_3_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_3/fri', payload=binary_payload[int(alarm_3_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_3/sat', payload=binary_payload[int(alarm_3_days[6])])

                            alarm_4_state = hex2bool[alarm_4_settings[0:2]]
                            alarm_4_time = int(alarm_4_settings[2:6], 16) # minutes
                            alarm_4_brightness = int(alarm_4_settings[6:8], 16) # 1 to 100 scale
                            alarm_4_days = str(bin(int(alarm_4_settings[8:10],16)))[2:]
                            alarm_4_days = '0'*(7 - len(alarm_4_days)) + alarm_4_days
                            alarm_4_sound = int(alarm_4_settings[10:12], 16) # 0 to all
                            alarm_4_volume = int(alarm_4_settings[12:14], 16) # 1 to 15
                            alarm_4_snooze = int(alarm_4_settings[14:16], 16) # minutes
                            publish(HA_TOPIC + 'alarms/alarm_4/state', payload=bool2payload[alarm_4_state])
                            publish(HA_TOPIC + 'alarms/alarm_4/time_hour', payload='%d' % (alarm_4_time // 60))
                            publish(HA_TOPIC + 'alarms/alarm_4/time_minute', payload='%d' % (alarm_4_time % 60))
                            publish(HA_TOPIC + 'alarms/alarm_4/brightness', payload='%d' % alarm_4_brightness)
                            publish(HA_TOPIC + 'alarms/alarm_4/sound', payload=sound_effect_types[alarm_4_sound])
                            publish(HA_TOPIC + 'alarms/alarm_4/volume', payload='%d' % alarm_4_volume)
                            publish(HA_TOPIC + 'alarms/alarm_4/snooze', payload='%d' % alarm_4_snooze)
                            publish(HA_TOPIC + 'alarms/alarm_4/sun', payload=binary_payload[int(alarm_4_days[0])])
                            publish(HA_TOPIC + 'alarms/alarm_4/mon', payload=binary_payload[int(alarm_4_days[1])])
                            publish(HA_TOPIC + 'alarms/alarm_4/tue', payload=binary_payload[int(alarm_4_days[2])])
                            publish(HA_TOPIC + 'alarms/alarm_4/wed', payload=binary_payload[int(alarm_4_days[3])])
                            publish(HA_TOPIC + 'alarms/alarm_4/thu', payload=binary_payload[int(alarm_4_days[4])])
                            publish(HA_TOPIC + 'alarms/alarm_4/fri', payload=binary_payload[int(alarm_4_days[5])])
                            publish(HA_TOPIC + 'alarms/alarm_4/sat', payload=binary_payload[int(alarm_4_days[6])])

                        # 102 17  raw Start/Stop Sleep with Full Settings
                        elif DpId == 102 and DpIdType == 0:
                            sleep_settings = DpIdData
                            sleep_time_settings = DpIdData[0:4]
                            sleep_state = hex2bool[DpIdData[4:6]]
                            sleep_sound_settings = DpIdData[6:12]
                            sleep_light_settings = DpIdData[12:34]

                            publish(HA_TOPIC + 'sleep/state', payload=bool2payload[sleep_state])

                            # Sleep Timer
                            sleep_time_minutes = int(sleep_time_settings[0:2], 16)
                            sleep_time_seconds = int(sleep_time_settings[2:4], 16)
                            publish(HA_TOPIC + 'sleep/time_minutes', payload='%d' % sleep_time_minutes)
                            publish(HA_TOPIC + 'sleep/time_seconds', payload='%d' % sleep_time_seconds)

                            # Sleep Sound
                            sleep_sound_state = hex2bool[sleep_sound_settings[0:2]]
                            sleep_sound_effect = int(sleep_sound_settings[2:4], 16)
                            sleep_sound_volume = int(sleep_sound_settings[4:6], 16) # 1 to 15
                            publish(HA_TOPIC + 'sleep/sound/state', payload=bool2payload[device_state and sleep_sound_state])
                            publish(HA_TOPIC + 'sleep/sound/effect', payload=sound_effect_types[sleep_sound_effect])
                            publish(HA_TOPIC + 'sleep/sound/volume', payload='%d' % sleep_sound_volume) # scale 15

                            # Sleep Light
                            sleep_light_state = hex2bool[sleep_light_settings[0:2]]
                            sleep_white_light_state = hex2bool[sleep_light_settings[2:4]]
                            sleep_white_light_brightness = int(sleep_light_settings[4:6], 16)
                            sleep_white_light_temperature = (50000 - 347*int(sleep_light_settings[6:8], 16)) // 100
                            sleep_color_light_state = hex2bool[sleep_light_settings[8:10]]
                            sleep_color_light_brightness = int(sleep_light_settings[10:12],16)
                            sleep_color_light_hue = int(sleep_light_settings[12:16],16)
                            sleep_effect_light_state = hex2bool[sleep_light_settings[16:18]]
                            sleep_effect_light_brightness = int(sleep_light_settings[18:20],16)
                            sleep_effect_light_effect = int(sleep_light_settings[20:22],16)
                            publish(HA_TOPIC + 'sleep/white/state', payload=bool2payload[device_state and sleep_light_state and sleep_white_light_state])
                            publish(HA_TOPIC + 'sleep/white/brightness', payload='%d' % sleep_white_light_brightness) # scale 20
                            publish(HA_TOPIC + 'sleep/white/color_temp', payload='%d' % sleep_white_light_temperature) # mireds, already adjusted calculation
                            publish(HA_TOPIC + 'sleep/color/state', payload=bool2payload[device_state and sleep_light_state and sleep_color_light_state])
                            publish(HA_TOPIC + 'sleep/color/brightness', payload='%d' % sleep_color_light_brightness) # scale 20
                            publish(HA_TOPIC + 'sleep/color/hs', payload='%d,100' % sleep_color_light_hue)
                            publish(HA_TOPIC + 'sleep/effect/state', payload=bool2payload[device_state and sleep_light_state and sleep_effect_light_state])
                            publish(HA_TOPIC + 'sleep/effect/brightness', payload='%d' % sleep_effect_light_brightness) # scale 20
                            publish(HA_TOPIC + 'sleep/effect/effect', payload=light_effect_types[sleep_effect_light_effect])

                            # Sync the related DPIDs for Kicks
                            pubcom('SerialSend5', payload=tuya_payload_raw(111, sleep_time_settings))
                            pubcom('SerialSend5', payload=tuya_payload_raw(112, sleep_sound_settings))
                            pubcom('SerialSend5', payload=tuya_payload_raw(113, sleep_light_settings))

                        elif DpId == 111 and DpIdType == 0:
                            sleep_time_remaining_minutes = int(DpIdData[0:2], 16)
                            sleep_time_remaining_seconds = int(DpIdData[2:4], 16)
                            publish(HA_TOPIC + 'sleep/time_remaining_minutes', payload='%d' % sleep_time_remaining_minutes)
                            publish(HA_TOPIC + 'sleep/time_remaining_seconds', payload='%d' % sleep_time_remaining_seconds)


                        # Only Write
                        #   111  2  raw Sleep Time Setting
                        #   112  3  raw Sleep Sound Settings
                        #   113 11  raw Sleep Lights Settings
                        elif DpId in [112, 113]:
                            if logging: publog('Sleep Sub-Setting: %s' % str(datapoint))

                        # Ignore
                        #   105  1 enum Time Format
                        #   106  2  raw Manual Time Set (Command Only)
                        #   107  1 bool Auto or Manual Time
                        #   108 32  raw Preview Alarm Full Alarm Settings (Command Only)
                        #   109  1  raw Which Alarm to Preview (Command Only)
                        #   110  1  raw Sound Cycle 0 = <-, 1 -> (Command Only)
                        elif DpId in [105, 105, 107, 108, 109, 110]:
                            if logging: publog('Intentionally Unhandled: %s' % str(datapoint))

                        else:
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
    #         if not color_light_state: pubcom('TuyaSend1', payload='2,1')
    #     else:
    #         if logging: publog('HA: Turn Color Light Off')
    #         if color_light_state: pubcom('TuyaSend1', payload='2,0')


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