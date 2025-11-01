from flask import Flask, render_template
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import requests
import threading
import time

# --- 1. CONFIGURATION ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "wiempower/mabrouka/farm/status"
ALERT_LEVEL = 30 

# !!! IMPORTANT !!!
# You won't know this URL until *after* you deploy on Render.
# For now, just leave it as a placeholder. You will edit it later.
APP_URL = "https://mabrouka-server.onrender.com" 

# Create a unique alert "channel" on ntfy.sh
ALERT_TOPIC_NAME = "mabrouka-farm-alert-team-XYZ" # CHANGE THIS
ALERT_URL = f"https://ntfy.sh/{ALERT_TOPIC_NAME}"

last_alert_sent = False

# --- 2. FLASK & SOCKET.IO SETUP ---
app = Flask(__name__)
# Render works well with eventlet for websockets
socketio = SocketIO(app, async_mode='eventlet') 

@app.route('/')
def index():
    return render_template('index.html')

# --- 3. ALERTING LOGIC (ntfy.sh) ---
def send_alert(alert_type="critical"):
    global last_alert_sent
    if alert_type == "critical" and not last_alert_sent:
        print(f"ALERT! Soil is critical. Sending push notification...")
        try:
            requests.post(
                ALERT_URL,
                headers={
                    "Title": "🚨 FARM ALERT! 🚨",
                    "Priority": "5",
                    "Tags": "rotating_light",
                    "Click": APP_URL # Links notification back to our app
                },
                data="The soil is very dry! Please check the farm." 
            )
            last_alert_sent = True 
        except Exception as e:
            print(f"Error sending alert: {e}")
            
    elif alert_type == "good" and last_alert_sent:
        print("RESET! Soil is good again.")
        last_alert_sent = False 

# --- 4. MQTT CLIENT SETUP ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Server Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Server failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        print(f"Server received message: {msg.payload.decode()}")
        data = json.loads(msg.payload.decode())
        
        socketio.emit('farm_update', data) 
        
        if 'soil' in data:
            if data['soil'] < ALERT_LEVEL:
                # We don't need a separate thread for emit,
                # but we do for the alert to prevent blocking.
                threading.Thread(target=send_alert, args=("critical",)).start()
            elif data['soil'] > (ALERT_LEVEL + 10):
                threading.Thread(target=send_alert, args=("good",)).start()
            
    except Exception as e:
        print(f"Error processing message: {e}")

def start_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever() 

# --- 5. RUN EVERYTHING ---
if __name__ == '__main__':
    print("Starting MQTT listener thread...")
    mqtt_thread = threading.Thread(target=start_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    print(f"Starting web server...")
    # Render provides the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port)
