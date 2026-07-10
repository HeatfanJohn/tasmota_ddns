#!/bin/sh
SCRIPT_FILE="$(pwd)/tasmota_ddns.py"
DOCKERFILE_FILE="$(pwd)/Dockerfile"

# --- VALIDATION CHECKS ---
if [ ! -f "$SCRIPT_FILE" ]; then 
    echo "File Error: SCRIPT file missing: $SCRIPT_FILE" >&2
    exit 1 
fi

if [ ! -f "$DOCKERFILE_FILE" ]; then 
    echo "File Error: Dockerfile missing in current directory: $DOCKERFILE_FILE" >&2
    exit 1 
fi

# Ensure initialization placeholder file exists on the host filesystem 
if [ ! -f "$(pwd)/ip_cache.json" ]; then
    echo "{}" > ip_cache.json
fi

# --- CONFIGURATION VARIABLES ---
# Both strictly set to tasmota-ddns-updater
CONTAINER_NAME="tasmota-ddns-updater"
IMAGE_NAME="tasmota-ddns-updater"

echo "Building local Docker image [ $IMAGE_NAME ]..."
docker build -t "$IMAGE_NAME" .

if [ $? -ne 0 ]; then
    echo "Build Error: Docker image compilation failed." >&2
    exit 1
fi

# Automatically stop and purge any existing stale container instances
if [ "$(docker ps -aq -f name=^${CONTAINER_NAME}$)" ]; then
    echo "Removing legacy container instance..."
    docker rm -f "$CONTAINER_NAME" > /dev/null
fi

# --- CONTAINER EXECUTION ---
echo "Launching daemon container..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --network host \
  --env-file "$(pwd)/.env" \
  -v /var/run/dbus:/var/run/dbus \
  -v /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
  -v /etc/resolv.conf:/etc/resolv.conf:ro \
  -v /etc/nsswitch.conf:/etc/nsswitch.conf:ro \
  -v "$(pwd)/ip_cache.json:/app/ip_cache.json" \
  "$IMAGE_NAME"

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------------"
    echo "Docker container started successfully in the background."
    echo "Use 'docker logs -f $CONTAINER_NAME' to view real-time logs."
    echo "--------------------------------------------------------"
else
    echo "Docker run command failed with exit code $?"
fi
