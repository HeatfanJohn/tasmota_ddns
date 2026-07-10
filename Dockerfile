FROM python:3.11-slim

# Install system dependencies required for mDNS resolution
RUN apt-get update && apt-get install -y \
    libnss-mdns \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies 
RUN pip install --no-cache-dir paho-mqtt requests

# Explicitly create the application folder
RUN mkdir -p /app
WORKDIR /app

# Copy the script directly into the folder
COPY tasmota_ddns.py /app/tasmota_ddns.py

# Explicitly run it from the absolute path
CMD ["python", "/app/tasmota_ddns.py"]
