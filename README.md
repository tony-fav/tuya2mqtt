This project is for writing interface layers between Tuya devices, flash with Tasmota which use serial communication with data points not directly supported by Tasmota.

Assumes Tasmota topics are of the form:
    command_topic = 'cmnd/' + DEVICE_TOPIC + '/'
    state_topic = 'stat/' + DEVICE_TOPIC + '/'
    telemetry_topic = 'tele/' + DEVICE_TOPIC + '/'
    result_topic = 'tele/' + DEVICE_TOPIC + '/RESULT'
    lwt_topic = 'tele/' + DEVICE_TOPIC + '/LWT'