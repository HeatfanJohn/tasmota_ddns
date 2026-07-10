import os
import sys
import json
import logging
import threading
import paho.mqtt.client as mqtt
import requests

# --- APPLICATION VERSION ---
VERSION = "4.6.0"

# --- CONFIGURE LOGGING ENGINE ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "tele/+/+")

NOIP_USERNAME = os.getenv("NOIP_USERNAME")
NOIP_PASSWORD = os.getenv("NOIP_PASSWORD")
NOIP_DOMAIN_SUFFIX = os.getenv("NOIP_DOMAIN_SUFFIX")

NETALERTX_URL = os.getenv("NETALERTX_URL")
NETALERTX_TOKEN = os.getenv("NETALERTX_TOKEN")
CACHE_FILE = "/app/ip_cache.json"

required_vars = {
    "MQTT_BROKER": MQTT_BROKER, 
    "NOIP_USERNAME": NOIP_USERNAME, 
    "NOIP_PASSWORD": NOIP_PASSWORD, 
    "NOIP_DOMAIN_SUFFIX": NOIP_DOMAIN_SUFFIX,
    "NETALERTX_URL": NETALERTX_URL,
    "NETALERTX_TOKEN": NETALERTX_TOKEN
}

missing_vars = [var for var, val in required_vars.items() if not val]
if missing_vars:
    logging.critical(f"v{VERSION} | Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

ip_cache = {}

def load_cache_from_disk():
    global ip_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                ip_cache = json.load(f)
            logging.info(f"Loaded {len(ip_cache)} cached device(s) from persistent file storage.")
        except Exception as e:
            logging.error(f"Failed to read persistent cache file: {e}")

def save_cache_to_disk():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(ip_cache, f, indent=4)
        logging.info("Persistent cache file successfully synchronized to disk.")
    except Exception as e:
        logging.error(f"Failed writing cache update to file: {e}")


def update_external_services_worker(hostname, internal_ip):
    """Worker execution running inside an isolated background thread for slow network I/O."""
    full_domain = f"{hostname}.{NOIP_DOMAIN_SUFFIX}"
    
    # 1. No-IP Dynamic DNS Update Handling
    if ip_cache.get(hostname) == internal_ip:
        logging.info(f"Cache Hit: {full_domain} is already known to be at {internal_ip}. Skipping No-IP sync.")
    else:
        logging.info(f"Cache Miss: IP changed or new for {full_domain}. Initiating No-IP request...")
        # Official integration URL endpoint
        url = "https://dynupdate.no-ip.com/nic/update"
        params = {"hostname": full_domain, "myip": internal_ip}
        headers = {"User-Agent": f"Tasmota Local IP Updater Python/{VERSION} support@example.com"}

        try:
            response = requests.get(url, params=params, headers=headers, auth=(NOIP_USERNAME, NOIP_PASSWORD), timeout=5)
            if response.status_code == 200:
                status = response.text.strip()
                if status.startswith("good") or status.startswith("nochg"):
                    ip_cache[hostname] = internal_ip
                    save_cache_to_disk()
                    logging.info(f"No-IP Sync Success: {full_domain} -> {internal_ip}")
                else:
                    logging.error(f"No-IP API Response Warning: {status}")
            else:
                logging.error(f"HTTP Failure Status {response.status_code} reaching No-IP.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error connecting to No-IP: {e}")

    # 2. NetAlertX Sync Handling with Automatic MAC Resolution
    try:
        logging.info(f"Resolving MAC Address for {internal_ip}...")
        
        mac_address = None
        if os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp", "r") as arp_file:
                for line in arp_file:
                    if internal_ip in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            mac_address = parts[3].upper()
                            break

        if not mac_address:
            logging.error(f"NetAlertX Sync Failure: Could not find a MAC address mapping for IP {internal_ip} in host ARP cache.")
            return

        logging.info(f"Resolved MAC Address for {internal_ip} -> {mac_address}")
        
        base_url = NETALERTX_URL.rstrip('/')
        netalertx_endpoint = f"{base_url}/device/{mac_address}/update-column"
        
        # FIXED: Modified the payload parameters to use columnName and columnValue keys 
        payload = {
            "columnName": "devName",
            "columnValue": hostname
        }
        
        netalertx_headers = {
            "Authorization": f"Bearer {NETALERTX_TOKEN}",
            "Content-Type": "application/json"
        }
        
        logging.info(f"Submitting payload to NetAlertX API: {netalertx_endpoint} -> devName: '{hostname}'")
        
        netalert_response = requests.post(
            netalertx_endpoint, 
            json=payload, 
            headers=netalertx_headers, 
            timeout=5
        )
        
        if netalert_response.status_code == 200:
            logging.info(f"NetAlertX Column Sync Success for device: {hostname} ({mac_address})")
        else:
            logging.error(f"NetAlertX API responded with HTTP error {netalert_response.status_code}: {netalert_response.text}")

    except Exception as e:
        logging.error(f"NetAlertX synchronization failed: {e}")


# --- MODERN VERSION 2 CALLBACK SIGNATURES ---
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logging.info(f"Successfully connected to the MQTT Broker. Subscribing to: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error(f"Connection failed with modern reason code: {reason_code}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    if reason_code != 0:
        logging.warning(f"Unexpected MQTT disconnect (Reason Code: {reason_code}). Client auto-reconnecting...")

def on_message(client, userdata, msg):
    try:
        topic_str = msg.topic
        payload_str = msg.payload.decode().strip()

        if topic_str.endswith("LWT"):
            device_topic = topic_str.split('/')[-2]
            if payload_str.lower() == "online":
                logging.info(f"Device Online: '{device_topic}' has successfully connected to MQTT.")
            elif payload_str.lower() == "offline":
                logging.warning(f"Device Offline: '{device_topic}' has disconnected or lost power unexpectedly!")
            return

        if topic_str.endswith("STATE"):
            logging.info(f"Proof of Life: Active MQTT traffic verified on topic '{topic_str}'")
            return

        if topic_str.endswith("INFO2"):
            logging.info(f"Boot Payload Detected on topic: {topic_str}")
            payload = json.loads(payload_str)
            hostname = payload["Info2"]["Hostname"]
            internal_ip = payload["Info2"]["IPAddress"]
            
            worker_thread = threading.Thread(
                target=update_external_services_worker, 
                args=(hostname, internal_ip),
                daemon=True
            )
            worker_thread.start()
            
    except Exception as e:
        logging.error(f"Error filtering MQTT payload: {e}")


# --- STARTUP WORKFLOW ---
logging.info(f"=== Starting Tasmota DDNS & NetAlertX Sync Daemon v{VERSION} ===")
load_cache_from_disk()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

logging.info(f"Connecting to MQTT Broker at '{MQTT_BROKER}'...")
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()
except Exception as e:
    logging.critical(f"Failed to start execution loop: {e}")
    sys.exit(1)

