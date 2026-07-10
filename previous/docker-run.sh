#!/bin/sh

echo Make sure that you\'re running this from the directory that contains the python script

docker run -d \
  --name tasmota-dns-updater \
  --restart unless-stopped \
  -e MQTT_BROKER="myrpi4-tuya.local" \
  -e MQTT_TOPIC="tele/+/INFO2" \
  -e NOIP_USERNAME="jpmasseria@gmail.com" \
  -e NOIP_PASSWORD="259274Jipumnoip" \
  -e NOIP_DOMAIN_SUFFIX="ddns.net" \
  -v /var/run/dbus:/var/run/dbus \
  -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
  -v /etc/resolv.conf:/etc/resolv.conf:ro \
  -v /etc/nsswitch.conf:/etc/nsswitch.conf:ro \
  -v $(pwd)/tasmota_ddns.py:/app/tasmota_ddns.py \
  python:3.11-slim sh -c "apt-get update && apt-get install -y libnss-mdns && pip install paho-mqtt requests && python /app/tasmota_ddns.py"
