import time
import random
import os
from flask import Flask, render_template
from flask_socketio import SocketIO
import eventlet

# We must patch the standard library for eventlet to work
eventlet.monkey_patch()

# --- 1. FLASK & SOCKET.IO SETUP ---
app = Flask(__name__, template_folder='.')
socketio = SocketIO(app, async_mode='eventlet')

# --- 2. SIMULATION STATE ---
# This is the "database" of our farm, matching your new 5 plants
plant_zones = {
    'tomato': {'humidity': 62, 'salinity': 2.0, 'temp': 25, 'status': 'OK'},
    'pepper': {'humidity': 67, 'salinity': 1.5, 'temp': 28, 'status': 'OK'},
    'cucumber': {'humidity': 72, 'salinity': 2.2, 'temp': 25, 'status': 'OK'},
    'onion': {'humidity': 35, 'salinity': 1.1, 'temp': 21, 'status': 'Warning'}, # Warning
    'pumpkin': {'humidity': 52, 'salinity': 1.7, 'temp': 24, 'status': 'OK'},
}

pump_status = {
    'state': 'OFF',
    'reason': 'Watering complete. All zones stable.',
    'temp': 45,
    'pressure': 50,
    'manualOverride': False
}

weather_forecast = {
    'today': {'temp': 26, 'rain': 10, 'icon': 'sun'},
    'tomorrow': {'temp': 28, 'rain': 60, 'icon': 'cloud'}
}

simulation_running = False # To make sure we only start it once

# --- 3. SIMULATION LOGIC ---

def get_irrigation_status(plants, pump):
    """Generates the main status bar text."""
    if pump['state'] == 'ON':
        return 'Pump is ON. Watering in progress...', 'blue'
    
    warning_plants = [name for name, data in plants.items() if data['status'] == 'Warning']
    if warning_plants:
        return f"Warning: {', '.join(warning_plants)} humidity low.", 'yellow'

    critical_plants = [name for name, data in plants.items() if data['status'] == 'Critical']
    if critical_plants:
        return f"CRITICAL: {', '.join(critical_plants)} require immediate watering!", 'red'

    return 'Pump is OFF. All plants are sufficiently watered.', 'green'

def update_simulation_data():
    """This function simulates the farm data changing."""
    global pump_status, plant_zones, weather_forecast
    
    # 1. Simulate Plants (if pump is OFF)
    if pump_status['state'] == 'OFF':
        for plant, data in plant_zones.items():
            data['humidity'] -= random.randint(0, 2)
            data['humidity'] = max(20, data['humidity']) # Don't go below 20
            
            # Update status
            if data['humidity'] < 40: data['status'] = 'Critical'
            elif data['humidity'] < 55: data['status'] = 'Warning'
            else: data['status'] = 'OK'
            
    # 2. Simulate Pump (Basic Auto-mode)
    if not pump_status['manualOverride']:
        is_critical = any(p['status'] == 'Critical' for p in plant_zones.values())
        if is_critical and pump_status['state'] == 'OFF':
            # Turn pump ON
            pump_status['state'] = 'ON'
            pump_status['reason'] = 'Auto-watering critical plants.'
            # Simulate watering
            for plant, data in plant_zones.items():
                if data['status'] == 'Critical':
                    data['humidity'] += 30 # Water them
                    data['status'] = 'OK'
            # After 3 seconds, turn it back off
            socketio.sleep(3)
            pump_status['state'] = 'OFF'
            pump_status['reason'] = 'Auto-watering complete.'

    # 3. Simulate sensors
    pump_status['temp'] = random.randint(44, 46)
    pump_status['pressure'] = random.randint(49, 51)
    
    # 4. Construct final data packet
    irrigation_text, irrigation_color = get_irrigation_status(plant_zones, pump_status)
    
    return {
        'weather': weather_forecast,
        'pump': pump_status,
        'plants': plant_zones,
        'irrigation': {
            'text': irrigation_text,
            'color': irrigation_color
        }
    }


def simulation_loop():
    """This is the main loop for the farm simulator."""
    print("--- Starting background simulation loop ---")
    while True:
        # 1. Get new simulated data
        data_packet = update_simulation_data()
        
        # 2. Send this data to all connected dashboards
        socketio.emit('farm_update', data_packet)
        
        # 3. Wait for 5 seconds before the next update
        socketio.sleep(5) 

# --- 4. SERVER ROUTES AND EVENTS ---

@app.route('/')
def index():
    """Serves the index.html dashboard."""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """A new user opened the dashboard."""
    print('Client connected (Browser opened)')
    
    global simulation_running
    if not simulation_running:
        # Start the background simulation only on the first connection
        socketio.start_background_task(target=simulation_loop)
        simulation_running = True

@socketio.on('command_force_start')
def handle_force_start():
    """Listens for the 'Force Start' button."""
    global pump_status
    pump_status['manualOverride'] = True
    pump_status['state'] = 'ON'
    pump_status['reason'] = 'Manual override: FORCED START'
    print("--- Command Received: FORCE START ---")
    # Immediately send an update
    socketio.emit('farm_update', update_simulation_data())

@socketio.on('command_force_stop')
def handle_force_stop():
    """Listens for the 'Force Stop' button."""
    global pump_status
    pump_status['manualOverride'] = True
    pump_status['state'] = 'OFF'
    pump_status['reason'] = 'Manual override: FORCED STOP'
    print("--- Command Received: FORCE STOP ---")
    # Immediately send an update
    socketio.emit('farm_update', update_simulation_data())
    
@socketio.on('command_set_auto')
def handle_set_auto():
    """Listens for the 'Set Auto' button."""
    global pump_status
    pump_status['manualOverride'] = False
    pump_status['reason'] = 'System set to automatic control.'
    print("--- Command Received: SET AUTO ---")
    # Immediately send an update
    socketio.emit('farm_update', update_simulation_data())


# --- 5. RUN THE SERVER ---
if __name__ == '__main__':
    print("--- Starting All-in-One Server ---")
    # Get the port from Render's environment, or default to 8080
    port = int(os.environ.get('PORT', 8080))
    # We must use eventlet to run the server
    socketio.run(app, host='0.0.0.0', port=port)
