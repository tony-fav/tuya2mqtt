FROM python:3-alpine
ADD ./t2t2m2p2m2ha-dekala.py /
RUN pip install paho.mqtt
CMD [ "python", "./t2t2m2p2m2ha-dekala.py" ]