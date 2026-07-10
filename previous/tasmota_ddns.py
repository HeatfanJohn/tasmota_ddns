import os
import sys
import json
import paho.mqtt.client as mqtt
import requests

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
MQTT_BROKER = os.getenv("MQTT_BROKER")
# Default to standard Tasmota wildcard telemetry topic if not provided
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "tele/+/INFO2")

NOIP_USERNAME = os.getenv("NOIP_USERNAME")
NOIP_PASSWORD = os.getenv("NOIP_PASSWORD")
NOIP_DOMAIN_SUFFIX = os.getenv("NOIP_DOMAIN_SUFFIX")

# Validate that required environment variables are set
required_vars = {
    "MQTT_BROKER": MQTT_BROKER,
    "NOIP_USERNAME": NOIP_USERNAME,
    "NOIP_PASSWORD": NOIP_PASSWORD,
    "NOIP_DOMAIN_SUFFIX": NOIP_DOMAIN_SUFFIX
}

missing_vars = [var for var, val in required_vars.items() if not val]
if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}", file=sys.stderr)
    sys.exit(1)


def update_noip(hostname, internal_ip):
    """Sends the internal IP address update to No-IP via their HTTP API."""
    full_domain = f"{hostname}.{NOIP_DOMAIN_SUFFIX}"
    url = "https://no-ip.com"
    params = {"hostname": full_domain, "myip": internal_ip}
    headers = {"User-Agent": "Tasmota Local IP Updater Python/1.0 mail@example.com"}

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            auth=(NOIP_USERNAME, NOIP_PASSWORD),
            timeout=10,
        )

        if response.status_code == 200:
            status = response.text.strip()
            if status.startswith("good"):
                print(f"Success: Updated {full_domain} to local IP {internal_ip}")
            elif status.startswith("nochg"):
                print(f"No Change: {full_domain} is already set to local IP {internal_ip}")
            else:
                print(f"No-IP Warning response for {full_domain}: {status}")
        else:
            print(f"HTTP Error {response.status_code}: Failed to update No-IP for {full_domain}")

    except requests.exceptions.RequestException as e:
        print(f"Network error while connecting to No-IP: {e}")


def on_message(client, userdata, msg):
    """MQTT Callback function for Tasmota INFO2 packet."""
    try:
        payload = json.loads(msg.payload.decode())
        hostname = payload["Info2"]["Hostname"]
        internal_ip = payload["Info2"]["IPAddress"]

        print(f"MQTT Received -> Device: {hostname} has internal IP: {internal_ip}")
        update_noip(hostname, internal_ip)

    except KeyError:
        print("Malformed payload: Missing Info2, Hostname, or IPAddress keys.")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")


# --- INITIALIZE MQTT CLIENT ---
client = mqtt.Client()
client.on_message = on_message

print(f"Connecting to MQTT Broker at {MQTT_BROKER}...")
try:
    client.connect(MQTT_BROKER, 1883, 60)
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}", file=sys.stderr)
    sys.exit(1)

client.subscribe(MQTT_TOPIC)
print(f"Monitoring Tasmota IP changes on topic: {MQTT_TOPIC}. Press Ctrl+C to exit.")
client.loop_forever()

