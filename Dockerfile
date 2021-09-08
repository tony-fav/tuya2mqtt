FROM python:3-alpine
ADD ./t2t2m2p2m2ha.py /
ADD ./devices/dekala_table_lamp/driver.py /devices/dekala_table_lamp/
ADD ./devices/heimvision_night_light/driver.py /devices/heimvision_night_light/
ADD ./devices/soulsens_night_light/driver.py /devices/soulsens_night_light/
RUN pip install paho.mqtt
CMD [ "python", "./t2t2m2p2m2ha.py" ]