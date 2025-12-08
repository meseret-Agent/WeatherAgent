import streamlit as st
import requests
import os
import json
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pyttsx3
import folium
from streamlit_folium import st_folium

# Load environment variables from .env file
load_dotenv()

# --- Utility functions ---

def get_city_coordinates(city):
    """Get city coordinates from OpenStreetMap"""
    geolocator = Nominatim(user_agent="weather_agent")
    location = geolocator.geocode(city + ", Netherlands")
    if location:
        return (location.latitude, location.longitude)
    return None


def find_nearest_station(user_coords):
    """Find nearest Buienradar station"""
    url = "https://data.buienradar.nl/2.0/feed/json"
    response = requests.get(url)
    data = response.json()
    stations = data['actual']['stationmeasurements']

    nearest_station = None
    min_distance = float("inf")

    for station in stations:
        station_coords = (station['lat'], station['lon'])
        distance = geodesic(user_coords, station_coords).km
        if distance < min_distance:
            min_distance = distance
            nearest_station = station

    return nearest_station, min_distance


def get_forecast(lat, lon):
    """Fetch 3-hour rain forecast"""
    url = f"https://gpsgadget.buienradar.nl/data/raintext?lat={lat}&lon={lon}"
    response = requests.get(url)
    lines = response.text.strip().split("\n")

    forecast_data = []
    for line in lines:
        value, time = line.split("|")
        forecast_data.append((int(value), time))

    will_rain = any(val > 70 for val, _ in forecast_data)
    if will_rain:
        next_rain_time = next(time for val, time in forecast_data if val > 70)
        return f"🌧 Rain expected around {next_rain_time}. Take an umbrella!"
    else:
        return "☀️ No rain expected in the next 3 hours."


def chat_with_gemini(user_message, weather_context, api_key):
    """Send a message to Gemini API with weather context and retry on rate limits"""
    import time
    
    if not api_key:
        return "❌ Please enter your Gemini API key in the sidebar to use the chat feature."
    
    # Use gemini-pro on v1 endpoint (most stable)
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={key}".format(key=api_key)
    
    # Build the prompt with weather context
    system_prompt = """You are a helpful weather assistant for the Netherlands. 
You have access to the current weather data and should answer questions about weather, activities, and recommendations.

Current Weather Data:
{context}

Answer the user's question in a friendly, concise way. Use emojis when appropriate. 
If asked about activities, give practical advice based on the current conditions.
If you don't have enough information to answer, say so politely.""".format(context=weather_context)

    payload = {
        "contents": [{
            "parts": [{
                "text": "{prompt}\n\nUser: {message}".format(prompt=system_prompt, message=user_message)
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    # Retry logic with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            # Handle rate limit specifically
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # 1s, 2s, 4s
                    return "⏳ Rate limit hit. Please wait {wait}s and try again. (Free tier has limits - wait between requests)".format(wait=wait_time)
                else:
                    return "❌ Rate limit exceeded. Please wait a minute before trying again.\n\n💡 Tip: The free Gemini API has rate limits. Wait 30-60 seconds between requests."
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the generated text
            if 'candidates' in result and len(result['candidates']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return "Sorry, I couldn't generate a response. Please try again."
                
        except requests.exceptions.Timeout:
            return "⏱️ Request timed out. Please try again."
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                return "❌ Too many requests. Please wait 30 seconds and try again.\n\n💡 The free API has request limits."
            return "❌ API Error: {error}".format(error=str(e))
        except requests.exceptions.RequestException as e:
            return "❌ Connection Error: {error}".format(error=str(e))
        except (KeyError, IndexError) as e:
            return "❌ Failed to parse response: {error}".format(error=str(e))
    
    return "❌ Failed after {retries} attempts. Please try again later.".format(retries=max_retries)


def get_all_stations():
    """Fetch all Buienradar weather stations with their data"""
    url = "https://data.buienradar.nl/2.0/feed/json"
    response = requests.get(url)
    data = response.json()
    return data['actual']['stationmeasurements']


def get_activity_recommendations(station):
    """Get activity recommendations based on weather conditions"""
    temp = station.get('temperature', 15)
    rain = station.get('precipitation', 0)
    windspeed = station.get('windspeed', 3)
    wind_dir = station.get('winddirection', '')
    
    # Initialize recommendations
    recommendations = []
    
    # Cycling recommendation
    cycling = {
        'name': '🚴 Cycling',
        'suitable': False,
        'reason': ''
    }
    if rain and rain > 0:
        cycling['reason'] = "Not recommended - it's raining"
    elif windspeed and windspeed > 5:
        cycling['reason'] = f"Challenging - strong wind ({windspeed} Bft)"
    elif temp and temp < 5:
        cycling['reason'] = f"Cold ride - only {temp}°C, dress warmly"
        cycling['suitable'] = True
    elif temp and temp > 30:
        cycling['reason'] = f"Very hot ({temp}°C) - stay hydrated!"
        cycling['suitable'] = True
    else:
        cycling['suitable'] = True
        cycling['reason'] = f"Great conditions! {temp}°C, light wind"
    recommendations.append(cycling)
    
    # Running recommendation
    running = {
        'name': '🏃 Running',
        'suitable': False,
        'reason': ''
    }
    if rain and rain > 0:
        running['reason'] = "Not ideal - rainy conditions"
    elif temp and temp > 28:
        running['reason'] = f"Too hot ({temp}°C) - risk of overheating"
    elif temp and temp < 0:
        running['reason'] = f"Very cold ({temp}°C) - icy conditions possible"
    else:
        running['suitable'] = True
        running['reason'] = f"Good for a run! {temp}°C"
    recommendations.append(running)
    
    # BBQ / Outdoor dining
    bbq = {
        'name': '🍖 BBQ / Outdoor Dining',
        'suitable': False,
        'reason': ''
    }
    if rain and rain > 0:
        bbq['reason'] = "Not recommended - rainy"
    elif temp and temp < 15:
        bbq['reason'] = f"A bit cold ({temp}°C) for outdoor dining"
    elif windspeed and windspeed > 4:
        bbq['reason'] = f"Windy ({windspeed} Bft) - BBQ may be tricky"
    else:
        bbq['suitable'] = True
        bbq['reason'] = f"Perfect BBQ weather! {temp}°C, calm"
    recommendations.append(bbq)
    
    # Beach recommendation
    beach = {
        'name': '🏖️ Beach',
        'suitable': False,
        'reason': ''
    }
    if rain and rain > 0:
        beach['reason'] = "Not beach weather - rainy"
    elif temp and temp < 18:
        beach['reason'] = f"Too cold for beach ({temp}°C)"
    elif windspeed and windspeed > 5:
        beach['reason'] = f"Very windy ({windspeed} Bft) - sand storms!"
    else:
        beach['suitable'] = True
        beach['reason'] = f"Beach day! {temp}°C and calm"
    recommendations.append(beach)
    
    # Walking recommendation
    walking = {
        'name': '🚶 Walking',
        'suitable': False,
        'reason': ''
    }
    if rain and rain > 2:
        walking['reason'] = "Heavy rain - bring umbrella"
    elif rain and rain > 0:
        walking['suitable'] = True
        walking['reason'] = "Light rain - bring umbrella"
    else:
        walking['suitable'] = True
        walking['reason'] = f"Nice for a walk! {temp}°C"
    recommendations.append(walking)
    
    return recommendations


def get_clothing_advice(station):
    """Get smart clothing recommendations based on weather"""
    temp = station.get('temperature', 15)
    rain = station.get('precipitation', 0)
    windspeed = station.get('windspeed', 3)
    
    advice = {
        'layers': [],
        'accessories': [],
        'footwear': '',
        'summary': ''
    }
    
    # Temperature-based clothing
    if temp and temp < 0:
        advice['layers'] = ['Thermal base layer', 'Warm sweater', 'Winter coat']
        advice['footwear'] = 'Insulated winter boots'
        advice['accessories'].extend(['Scarf', 'Gloves', 'Winter hat'])
        advice['summary'] = "❄️ Bundle up! It's freezing."
    elif temp and temp < 10:
        advice['layers'] = ['Long sleeve shirt', 'Sweater', 'Jacket']
        advice['footwear'] = 'Closed shoes or boots'
        advice['accessories'].append('Light scarf')
        advice['summary'] = "🧥 Dress warmly - it's quite cold."
    elif temp and temp < 15:
        advice['layers'] = ['Long sleeve shirt', 'Light jacket or cardigan']
        advice['footwear'] = 'Comfortable closed shoes'
        advice['summary'] = "👔 Layers recommended - mild but cool."
    elif temp and temp < 20:
        advice['layers'] = ['T-shirt or light shirt', 'Optional light jacket']
        advice['footwear'] = 'Sneakers or casual shoes'
        advice['summary'] = "👕 Pleasant weather - light clothing."
    elif temp and temp < 25:
        advice['layers'] = ['T-shirt or polo', 'Shorts or light pants OK']
        advice['footwear'] = 'Light shoes or sandals'
        advice['accessories'].append('Sunglasses')
        advice['summary'] = "☀️ Warm and nice - dress light!"
    else:
        advice['layers'] = ['Light breathable shirt', 'Shorts recommended']
        advice['footwear'] = 'Sandals or breathable shoes'
        advice['accessories'].extend(['Sunglasses', 'Hat', 'Sunscreen'])
        advice['summary'] = "🌞 Hot! Minimal clothing and sun protection."
    
    # Rain adjustments
    if rain and rain > 0:
        advice['accessories'].append('☔ Umbrella')
        if rain > 2:
            advice['accessories'].append('Rain jacket/coat')
            advice['footwear'] = 'Waterproof boots'
    
    # Wind adjustments
    if windspeed and windspeed > 4:
        advice['accessories'].append('Windbreaker recommended')
        if 'Light jacket' not in str(advice['layers']):
            advice['layers'].append('Windproof layer')
    
    return advice


def get_multi_city_weather(user_city=None, user_station=None):
    """Get weather data for user's city + 5 major Dutch cities"""
    comparison_data = []
    
    # Add user's searched city first (if provided)
    if user_city and user_station:
        comparison_data.append({
            'city': user_city + " ⭐",  # Star to highlight it's the searched city
            'temp': user_station.get('temperature', 'N/A'),
            'rain': user_station.get('precipitation', 0),
            'wind': user_station.get('windspeed', 'N/A'),
            'station': user_station.get('stationname', 'Unknown')
        })
    
    # Add 5 major Dutch cities
    cities = {
        'Amsterdam': (52.3676, 4.9041),
        'Rotterdam': (51.9225, 4.47917),
        'The Hague': (52.0705, 4.3007),
        'Utrecht': (52.0907, 5.1214),
        'Eindhoven': (51.4416, 5.4697)
    }
    
    all_stations = get_all_stations()
    
    for city_name, coords in cities.items():
        # Skip if this is the same city as user's search
        if user_city and city_name.lower() == user_city.lower():
            continue
            
        # Find nearest station
        nearest_station = None
        min_distance = float('inf')
        
        for station in all_stations:
            if station.get('lat') and station.get('lon'):
                station_coords = (station['lat'], station['lon'])
                distance = geodesic(coords, station_coords).km
                if distance < min_distance:
                    min_distance = distance
                    nearest_station = station
        
        if nearest_station:
            comparison_data.append({
                'city': city_name,
                'temp': nearest_station.get('temperature', 'N/A'),
                'rain': nearest_station.get('precipitation', 0),
                'wind': nearest_station.get('windspeed', 'N/A'),
                'station': nearest_station.get('stationname', 'Unknown')
            })
    
    return comparison_data


def get_marker_color(station):
    """Determine marker color based on weather conditions"""
    temp = station.get('temperature', 15)
    rain = station.get('precipitation', 0)
    
    if rain and rain > 0:
        return 'blue'  # Raining
    elif temp and temp < 5:
        return 'purple'  # Very cold
    elif temp and temp < 10:
        return 'lightblue'  # Cold
    elif temp and temp > 25:
        return 'red'  # Hot
    elif temp and temp > 20:
        return 'orange'  # Warm
    else:
        return 'green'  # Nice weather


def create_weather_map(stations, user_coords=None, user_city=None):
    """Create an interactive folium map with all weather stations"""
    # Center the map on the Netherlands
    center_lat = 52.1326
    center_lon = 5.2913
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles='CartoDB positron'
    )
    
    # Add markers for all stations
    for station in stations:
        lat = station.get('lat')
        lon = station.get('lon')
        
        if lat and lon:
            temp = station.get('temperature')
            rain = station.get('precipitation', 0)
            windspeed = station.get('windspeed')
            wind_dir = station.get('winddirection', '-')
            name = station.get('stationname', 'Unknown')
            
            # Format values for display
            temp_display = f"{temp}°C" if temp is not None else "Not available"
            wind_display = f"{windspeed} Bft ({wind_dir})" if windspeed is not None else "Not available"
            
            # Create popup content
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <h4 style="margin: 0 0 8px 0; color: #333;">📡 {name}</h4>
                <p style="margin: 4px 0;"><b>🌡️ Temperature:</b> {temp_display}</p>
                <p style="margin: 4px 0;"><b>🌧️ Rain:</b> {rain if rain else 0} mm</p>
                <p style="margin: 4px 0;"><b>💨 Wind:</b> {wind_display}</p>
            </div>
            """
            
            color = get_marker_color(station)
            
            # Choose icon based on weather condition
            rain = station.get('precipitation', 0)
            temp = station.get('temperature', 15)
            
            if rain and rain > 0:
                icon_type = 'tint'  # Water droplet for rain
            elif temp and temp < 10:
                icon_type = 'cloud'  # Cloud for cold weather
            else:
                icon_type = 'cloud'  # Default cloud
            
            # Tooltip also handles missing temp
            tooltip_text = f"{name}: {temp_display}" if temp is not None else f"{name}"
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=tooltip_text,
                icon=folium.Icon(color=color, icon=icon_type)
            ).add_to(m)
    
    # Highlight user's location if provided
    if user_coords and user_city:
        folium.Marker(
            location=user_coords,
            popup=f"📍 Your location: {user_city}",
            tooltip=f"📍 {user_city}",
            icon=folium.Icon(color='darkred', icon='home')
        ).add_to(m)
        
        # Add a circle around user's location
        folium.Circle(
            location=user_coords,
            radius=15000,  # 15 km radius
            color='darkred',
            fill=True,
            fill_opacity=0.1
        ).add_to(m)
    
    return m


def speak_text(message):
    """Speak weather summary aloud"""
    engine = pyttsx3.init()
    engine.say(message)
    engine.runAndWait()


# --- Streamlit UI ---

st.set_page_config(page_title="Weather AI Agent", page_icon="🌦️", layout="wide")

st.title("�️ Dutch Weather Intelligence Platform")
st.write("Professional weather insights for the Netherlands - Real-time data, smart recommendations, and comprehensive city comparisons.")

# Initialize session state
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = None
if 'city_name' not in st.session_state:
    st.session_state.city_name = None
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = None

# Input city name
city = st.text_input("Which city's weather would you like to explore?", "Leiden", placeholder="e.g., Amsterdam, Rotterdam, Utrecht...")

if st.button("Get Weather"):
    with st.spinner("Fetching live weather data..."):
        coords = get_city_coordinates(city)
        if not coords:
            st.error("⚠️ Could not find that city. Try again.")
            st.session_state.weather_data = None
        else:
            # Get nearest station
            station, distance = find_nearest_station(coords)
            
            # Get all stations for the map
            all_stations = get_all_stations()
            
            if station:
                # Store data in session state to persist across reruns
                st.session_state.weather_data = {
                    'coords': coords,
                    'station': station,
                    'distance': distance,
                    'all_stations': all_stations
                }
                st.session_state.city_name = city

# Display weather data if available in session state
if st.session_state.weather_data:
    data = st.session_state.weather_data
    city_display = st.session_state.city_name
    coords = data['coords']
    station = data['station']
    distance = data['distance']
    all_stations = data['all_stations']
    
    st.success(f"📍 Found {city_display}: {coords}")
    st.info(f"📡 Nearest station: {station['stationname']} ({distance:.1f} km away)")
    
    # Get weather data
    temp = station['temperature']
    rain = station['precipitation']
    windspeed = station['windspeed']
    wind_dir = station['winddirection']
    
    # Weather decision message
    if rain and rain > 0:
        msg = f"🌧 It's raining ({rain} mm). Take an umbrella!"
    elif windspeed and windspeed > 5:
        msg = f"💨 It's windy ({windspeed} Bft, {wind_dir}). Hold onto your hat!"
    elif temp and temp < 10:
        msg = f"🥶 It's cold ({temp}°C). Dress warmly!"
    else:
        msg = f"☀️ The weather looks nice ({temp}°C, no rain). Enjoy your day!"
    
    # Row 1: Current Weather (left) + Clothing Advisor (right)
    row1_col1, row1_col2 = st.columns([1, 1])
    
    with row1_col1:
        st.subheader("Current Weather")
        st.success(msg)
        
        # Metrics
        st.metric("🌡️ Temperature", f"{temp}°C")
        st.metric("💨 Wind Speed", f"{windspeed} Bft")
        st.metric("🌧️ Precipitation", f"{rain if rain else 0} mm")

        # Forecast
        forecast_msg = get_forecast(*coords)
        st.subheader("3-Hour Forecast")
        st.info(forecast_msg)

        # Optional voice alert
        if st.button("🔊 Speak Weather Summary"):
            summary = f"In {city_display}, {msg} {forecast_msg}"
            try:
                speak_text(summary)
                st.success("🔊 Speaking weather summary...")
            except Exception as e:
                st.error(f"Could not speak: {e}")
    
    with row1_col2:
        # Clothing Advisor
        st.subheader("👔 Smart Clothing Advisor")
        clothing = get_clothing_advice(station)
        st.info(clothing['summary'])
        
        st.write("**What to wear:**")
        st.write("🧥 **Layers:**")
        for layer in clothing['layers']:
            st.write(f"  • {layer}")
        
        st.write(f"👟 **Footwear:** {clothing['footwear']}")
        
        if clothing['accessories']:
            st.write("🎒 **Accessories:**")
            for acc in clothing['accessories']:
                st.write(f"  • {acc}")
    
    # Row 2: Activity Recommendations (full width)
    st.divider()
    st.subheader("🎯 Activity Recommendations")
    recommendations = get_activity_recommendations(station)
    
    # Display in 2 columns for better layout
    act_col1, act_col2 = st.columns(2)
    for idx, rec in enumerate(recommendations):
        with (act_col1 if idx % 2 == 0 else act_col2):
            if rec['suitable']:
                st.success(f"✅ **{rec['name']}**: {rec['reason']}")
            else:
                st.warning(f"⚠️ **{rec['name']}**: {rec['reason']}")
    
    # Row 3: Map (full width)
    st.divider()
    st.subheader("🗺️ Interactive Weather Map")
    st.caption("Click on any station marker to see details. Your location is marked in dark red.")
    
    # Create and display the map
    weather_map = create_weather_map(all_stations, coords, city_display)
    st_folium(weather_map, width=None, height=500)  # Full width
    
    # Add legend below map
    st.caption("**Map Legend:**")
    legend_cols = st.columns(7)
    with legend_cols[0]:
        st.markdown("💧 **Raining**")
    with legend_cols[1]:
        st.markdown("🟣 **Very Cold** (<5°C)")
    with legend_cols[2]:
        st.markdown("☁️ **Cold** (5-10°C)")
    with legend_cols[3]:
        st.markdown("🟢 **Nice** (10-20°C)")
    with legend_cols[4]:
        st.markdown("🟠 **Warm** (20-25°C)")
    with legend_cols[5]:
        st.markdown("🔴 **Hot** (>25°C)")
    with legend_cols[6]:
        st.markdown("🏠 **Your Location**")

# Multi-City Comparison
st.divider()
st.subheader("🏙️ Multi-City Weather Comparison")

if st.session_state.weather_data:
    # Get comparison data including user's city
    data = st.session_state.weather_data
    city_display = st.session_state.city_name
    station = data['station']
    
    st.caption(f"Your city ({city_display}) ⭐ plus 5 major Dutch cities")
    multi_city_data = get_multi_city_weather(city_display, station)
else:
    st.caption("Compare current weather across 5 major Dutch cities")
    multi_city_data = get_multi_city_weather()

# Create columns for cities (dynamically adjust based on how many cities we have)
num_cities = len(multi_city_data)
cols = st.columns(min(num_cities, 6))  # Max 6 columns

for idx, city_data in enumerate(multi_city_data):
    if idx < 6:  # Only show max 6 cities
        with cols[idx]:
            st.markdown(f"**{city_data['city']}**")
            
            # Temperature with color
            temp = city_data['temp']
            if temp != 'N/A':
                if temp < 10:
                    st.markdown(f"🌡️ <span style='color: blue;'>{temp}°C</span>", unsafe_allow_html=True)
                elif temp > 25:
                    st.markdown(f"🌡️ <span style='color: red;'>{temp}°C</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"🌡️ {temp}°C")
            else:
                st.markdown(f"🌡️ {temp}")
            
            # Rain
            rain_val = city_data['rain']
            if rain_val and rain_val > 0:
                st.markdown(f"🌧️ **{rain_val} mm**")
            else:
                st.markdown(f"☀️ No rain")
            
            # Wind
            st.markdown(f"💨 {city_data['wind']} Bft")
