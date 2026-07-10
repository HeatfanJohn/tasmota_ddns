#!/bin/sh
SCRIPT_FILE="$(pwd)/tasmota_ddns.py"

if [ ! -f "$SCRIPT_FILE" ]; then 
    echo "File Error: SCRIPT file missing: $SCRIPT_FILE" >&2
    exit 1 
fi

# Ensure initialization placeholder file exists on the host filesystem 
if [ ! -f "$(pwd)/ip_cache.json" ]; then
    echo "{}" > ip_cache.json
fi

docker run -d \
  --name tasmota-dns-updater \
  --restart unless-stopped \
  --network host \
  --env-file "$(pwd)/.env" \
  -v /var/run/dbus:/var/run/dbus \
  -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
  -v /etc/resolv.conf:/etc/resolv.conf:ro \
  -v /etc/nsswitch.conf:/etc/nsswitch.conf:ro \
  -v "$(pwd)/tasmota_ddns.py:/app/tasmota_ddns.py" \
  -v "$(pwd)/ip_cache.json:/app/ip_cache.json" \
  python:3.11-slim sh -c "apt-get update && apt-get install -y libnss-mdns iputils-ping && pip install paho-mqtt requests && python /app/tasmota_ddns.py"

if [ $? -eq 0 ]; then
    echo "Docker container started successfully in the background"
    echo "Use 'docker logs -f tasmota-ddns' to view logs"
else
    echo "Docker command failed with exit code $?"
fi

