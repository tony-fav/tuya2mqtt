FROM python:3-alpine
ADD ./tuya2mqtt.py /
ADD ./devices/dekala_table_lamp/driver.py /devices/dekala_table_lamp/
ADD ./devices/heimvision_night_light/driver.py /devices/heimvision_night_light/
ADD ./devices/soulsens_night_light/driver.py /devices/soulsens_night_light/
ADD ./devices/asakuki_diffuser/driver.py /devices/asakuki_diffuser/
RUN pip install paho.mqtt
CMD [ "python", "./tuya2mqtt.py" ]