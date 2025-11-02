from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import requests
import threading
import os 

# --- 1. CONFIGURATION ---
ALERT_LEVEL = 30 
APP_URL = "https://mabrouka-server.onrender.com" 
ALERT_TOPIC_NAME = "mabrouka-farm-alert-team-XYZ"
ALERT_URL = f"https://ntfy.sh/{ALERT_TOPIC_NAME}"
last_alert_sent = False

# --- 2. FLASK & SOCKET.IO SETUP ---
app = Flask(__name__, template_folder='.')
socketio = SocketIO(app, async_mode='eventlet') 

@app.route('/')
def index():
    return render_template('index.html')

# --- 3. SOCKET.IO EVENT HANDLERS ---

@socketio.on('farm_update')
def handle_farm_update(data):
    """
    Receives data from the farm simulator and broadcasts
    it to all other connected clients (the web browsers).
    """
    # print(f"Server received update from simulator: {data}") # Commented out to reduce log spam
    emit('farm_update', data, broadcast=True) 
       
    if 'soil' in data:
        if data['soil'] < ALERT_LEVEL:
            socketio.start_background_task(send_alert, "critical")
        elif data['soil'] > (ALERT_LEVEL + 10):
            socketio.start_background_task(send_alert, "good")

# --- UPDATED: Handler for new buttons ---
@socketio.on('command')
def handle_command(data):
    """
    Receives a command from a browser (e.g., { 'pump': 'ON' }).
    Broadcasts a 'command_to_sim' event for the simulator to hear.
    """
    print(f"Server received command from browser: {data}")
    # Broadcast a *different* event name for the simulator to listen to
    emit('command_to_sim', data, broadcast=True)

@socketio.on('connect')
def handle_connect():
    print('A client connected (Browser or Simulator)')

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected')
    
# --- 4. ALERTING LOGIC (ntfy.sh) ---
def send_alert(alert_type="critical"):
    global last_alert_sent
    if alert_type == "critical" and not last_alert_sent:
        last_alert_sent = True
        print(f"ALERT! Soil is critical. Sending push notification...")
        try:
            requests.post(
                ALERT_URL,
                headers={
                    "Title": "🚨 FARM ALERT! 🚨", "Priority": "5",
                    "Tags": "rotating_light", "Click": APP_URL 
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
    port = int(os.environ.get('PORT', 8080))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
