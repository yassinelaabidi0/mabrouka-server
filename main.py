from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import requests
import threading
import os # Added for Render's PORT

# --- 1. CONFIGURATION ---
ALERT_LEVEL = 30 

# !!! IMPORTANT !!!
# Make sure this is your correct public URL
APP_URL = "https://mabrouka-server.onrender.com" 

# Create a unique alert "channel" on ntfy.sh
ALERT_TOPIC_NAME = "mabrouka-farm-alert-team-XYZ" # CHANGE THIS
ALERT_URL = f"https://ntfy.sh/{ALERT_TOPIC_NAME}"

last_alert_sent = False

# --- 2. FLASK & SOCKET.IO SETUP ---
app = Flask(__name__, template_folder='.')
socketio = SocketIO(app, async_mode='eventlet') 

@app.route('/')
def index():
    # This serves the index.html file
    return render_template('index.html')

# --- 3. NEW: SOCKET.IO EVENT HANDLER ---
# This function receives data from your farm_simulator.py
@socketio.on('farm_update')
# --- 3. NEW: SOCKET.IO EVENT HANDLER ---
# This function receives data from your farm_simulator.py
@socketio.on('farm_update')
def handle_farm_update(data):

    print(f"Server received update from simulator: {data}")

    emit('farm_update', data, broadcast=True) 
       
    if 'soil' in data:
        if data['soil'] < ALERT_LEVEL:
            socketio.start_background_task(send_alert, "critical")
        elif data['soil'] > (ALERT_LEVEL + 10):
            socketio.start_background_task(send_alert, "good")

@socketio.on('connect')
def handle_connect():
    print('A client connected (Browser or Simulator)')

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected')
    
# --- 4. ALERTING LOGIC (ntfy.sh) ---
# --- 4. ALERTING LOGIC (ntfy.sh) ---
def send_alert(alert_type="critical"):
    global last_alert_sent
    if alert_type == "critical" and not last_alert_sent:
        # Set the flag *before* the request to prevent spam
        last_alert_sent = True
        print(f"ALERT! Soil is critical. Sending push notification...")
        try:
            requests.post(
                ALERT_URL,
                headers={
                    "Title": "🚨 FARM ALERT! 🚨",
                    "Priority": "5",
                    "Tags": "rotating_light",
                    "Click": APP_URL 
                },
                data="The soil is very dry! Please check the farm." 
            )
            print("Alert sent successfully.")
        except Exception as e:
            print(f"Error sending alert: {e}")
            
    elif alert_type == "good" and last_alert_sent:
        print("RESET! Soil is good again.")
        last_alert_sent = False

# --- 5. RUN SERVER ---
if __name__ == '__main__':
    print(f"Starting web server...")
    # Use Render's PORT environment variable, default to 8080
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)





