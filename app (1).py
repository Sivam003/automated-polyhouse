import streamlit as st
import paho.mqtt.client as mqtt
import time
import json
from datetime import datetime

# --- 1. THREAD-SAFE DATA STORE ---
# This prevents the background MQTT thread from crashing the Streamlit UI thread
@st.cache_resource
def get_data_store():
    return {
        "ai_status": "Waiting for Edge Node...",
        "ai_conf": 0.0,
        "temp": 0.0,
        "hum": 0,
        "alerts": [], # Stores our notification history
        "fan_status": "OFF",
        "light_status": "ON" # Defaulted to ON based on your hardware setup
    }

data_store = get_data_store()

# --- 2. CLOUD MQTT CALLBACKS ---
def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    topic = msg.topic
    
    try:
        # Route 1: Handle AI Vision Data
        if topic == "polyhouse/ncr2026/ai/status":
            data_store["ai_status"] = payload
            # Trigger an alert if a disease is detected
            if "Healthy" not in payload and "Waiting" not in payload:
                timestamp = datetime.now().strftime("%H:%M:%S")
                data_store["alerts"].insert(0, f"[{timestamp}] ⚠️ AI Alert: {payload}")
                
        elif topic == "polyhouse/ncr2026/ai/conf":
            data_store["ai_conf"] = float(payload)
            
        # Route 2: Handle ESP32 Sensor Data
        elif topic == "polyhouse/ncr2026/sensors":
            data = json.loads(payload)
            data_store["temp"] = data["temp"]
            data_store["hum"] = data["hum"]
            
            # Logic to mirror the ESP32 hardware Fan Notification
            if data["temp"] > 28.0 and data_store["fan_status"] == "OFF":
                data_store["fan_status"] = "ON"
                timestamp = datetime.now().strftime("%H:%M:%S")
                data_store["alerts"].insert(0, f"[{timestamp}] 💨 High Temp ({data['temp']}°C): Exhaust Fan activated")
            elif data["temp"] <= 28.0 and data_store["fan_status"] == "ON":
                data_store["fan_status"] = "OFF"
                timestamp = datetime.now().strftime("%H:%M:%S")
                data_store["alerts"].insert(0, f"[{timestamp}] 🛑 Temp Normalized ({data['temp']}°C): Exhaust Fan deactivated")
                
    except Exception as e:
        print(f"Error parsing incoming data: {e}")

@st.cache_resource
def setup_mqtt():
    # Try-except block ensures compatibility with all paho-mqtt versions
    try:
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    except:
        client = mqtt.Client()
        
    client.on_message = on_message
    client.connect("broker.hivemq.com", 1883, 60)
    # The '#' symbol tells it to listen to EVERYTHING in your project folder
    client.subscribe("polyhouse/ncr2026/#")
    client.loop_start()
    return client

# Start the MQTT background listener
setup_mqtt()

# --- 3. DASHBOARD UI ---
st.set_page_config(page_title="Polyhouse Edge AI Dashboard", layout="wide")

st.title("🌱 Cloud-Connected Hydroponic Control Center")
st.markdown("**System Architecture:** Distributed IoT Edge | **Broker:** HiveMQ Public Cloud | **Status:** 🟢 Live")
st.divider()

# --- TOP ROW: Metrics & AI ---
col1, col2 = st.columns(2)

with col1:
    st.header("📊 Real-Time Telemetry")
    st.caption("Source: ESP32 Sensor Node")
    
    # Display Sensors
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1:
        st.metric("Water Temperature", f"{data_store['temp']} °C")
    with sub_col2:
        st.metric("Relative Humidity", f"{data_store['hum']} %")
    
    st.write("---")
    
    # Display Physical Actuators
    st.subheader("⚙️ Hardware Actuators")
    fan_color = "🟢 ON" if data_store["fan_status"] == "ON" else "🔴 OFF"
    light_color = "🟢 ON" if data_store["light_status"] == "ON" else "🔴 OFF"
    
    st.write(f"**Exhaust Fan (Pin 26/27):** {fan_color}")
    st.write(f"**Grow Light (Pin 25):** {light_color}")

with col2:
    st.header("🧠 Edge AI Pathologist")
    st.caption("Source: Raspberry Pi Vision Node (MobileNetV2)")
    
    status_text = data_store['ai_status']
    
    # Dynamic styling based on AI diagnosis
    if "Healthy" in status_text:
        st.success(status_text)
    elif "Waiting" in status_text:
        st.info(status_text)
    else:
        st.error(status_text)
        # Trigger the browser Toast pop-up notification
        st.toast(f"Plant Pathology Alert: {status_text}", icon="⚠️")
        
    # Confidence Progress Bar
    st.write(f"**Confidence Score:** {data_store['ai_conf']}%")
    st.progress(data_store['ai_conf'] / 100.0)

st.divider()

# --- BOTTOM ROW: Notification History ---
st.header("📋 Automated System Log")

if len(data_store["alerts"]) == 0:
    st.info("System operating normally. No alerts recorded in this session.")
else:
    # Display the 6 most recent alerts to prevent clutter
    for alert in data_store["alerts"][:6]:
        if "High Temp" in alert or "AI Alert" in alert:
            st.warning(alert)
        else:
            st.success(alert)

# --- REFRESH LOGIC ---
# Forces the Streamlit UI to redraw every 2 seconds to fetch the newest data_store values
time.sleep(2)
st.rerun()