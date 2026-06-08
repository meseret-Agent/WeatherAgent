import streamlit as st
import requests
import os
import json
import time
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pyttsx3
import folium
from streamlit_folium import st_folium

# Load environment variables from .env file
load_dotenv()

# --- Utility functions ---

def api_request_with_retry(url, max_retries=3, timeout=10):
    """Make API request with retry logic and exponential backoff"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise Exception(f"⏱️ Request timed out after {max_retries} attempts")
            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
        except requests.exceptions.ConnectionError:
            if attempt == max_retries - 1:
                raise Exception("🔌 No internet connection. Please check your network.")
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            if attempt == max_retries - 1:
                raise Exception(f"❌ API Error: {str(e)}")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise Exception(f"❌ Request failed: {str(e)}")
            time.sleep(2 ** attempt)
    
    raise Exception("❌ Failed after all retry attempts")


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_city_coordinates(city):
    """Get city coordinates and validate it's in Netherlands"""
    
    # Fallback coordinates for major Dutch cities (in case Nominatim fails)
    DUTCH_CITIES = {
        'amsterdam': (52.3676, 4.9041),
        'rotterdam': (51.9225, 4.47917),
        'the hague': (52.0705, 4.3007),
        'den haag': (52.0705, 4.3007),
        'utrecht': (52.0907, 5.1214),
        'eindhoven': (51.4416, 5.4697),
        'groningen': (53.2194, 6.5665),
        'tilburg': (51.5555, 5.0913),
        'almere': (52.3508, 5.2647),
        'breda': (51.5719, 4.7683),
        'nijmegen': (51.8126, 5.8372),
        'enschede': (52.2215, 6.8937),
        'haarlem': (52.3874, 4.6462),
        'arnhem': (51.9851, 5.8987),
        'zaanstad': (52.4389, 4.8294),
        'amersfoort': (52.1561, 5.3878),
        'apeldoorn': (52.2112, 5.9699),
        'leiden': (52.1601, 4.4970),
        'maastricht': (50.8514, 5.6909),
        'dordrecht': (51.8133, 4.6901),
        'zoetermeer': (52.0575, 4.4932),
        'zwolle': (52.5168, 6.0830),
        'delft': (52.0116, 4.3571),
        'alkmaar': (52.6318, 4.7474),
    }
    
    # First try the fallback dictionary for common cities
    city_lower = city.lower().strip()
    if city_lower in DUTCH_CITIES:
        return DUTCH_CITIES[city_lower]
    
    # If not in fallback, try Nominatim API
    try:
        # Use a descriptive user agent - required by Nominatim usage policy
        geolocator = Nominatim(
            user_agent="WeerWijs_Dutch_Weather_App/1.0 (https://github.com/yourusername/weatheragent)",
            timeout=10
        )
        
        # Search WITHOUT Netherlands constraint to get the actual main city
        # (searching "Madrid, Netherlands" might find a street named Madrid in NL)
        location = geolocator.geocode(city)
        
        if location:
            lat, lon = location.latitude, location.longitude
            
            # Validate coordinates are within Netherlands boundaries
            # Netherlands: roughly 50.75°N to 53.7°N, 3.2°E to 7.2°E
            if 50.5 <= lat <= 53.8 and 3.0 <= lon <= 7.5:
                return (lat, lon)
            else:
                # City is outside Netherlands
                return None
        
        # If no location found at all
        return None
        
    except Exception as e:
        # If Nominatim fails (rate limit, network issue, etc.), return None
        # The error will be handled by the calling function
        print(f"Geocoding failed for {city}: {str(e)}")
        return None


def find_nearest_station(user_coords):
    """Find nearest Buienradar station"""
    url = "https://data.buienradar.nl/2.0/feed/json"
    response = api_request_with_retry(url)
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


@st.cache_data(ttl=900)  # Cache for 15 minutes
def get_forecast(lat, lon):
    """Fetch 3-hour rain forecast"""
    url = f"https://gpsgadget.buienradar.nl/data/raintext?lat={lat}&lon={lon}"
    response = api_request_with_retry(url)
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





@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_all_stations():
    """Fetch all Buienradar weather stations with their data"""
    url = "https://data.buienradar.nl/2.0/feed/json"
    response = api_request_with_retry(url)
    data = response.json()
    return data['actual']['stationmeasurements']


@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_five_day_forecast():
    """Fetch 5-day weather forecast from Buienradar"""
    url = "https://data.buienradar.nl/2.0/feed/json"
    response = api_request_with_retry(url)
    data = response.json()
    return data['forecast']['fivedayforecast']


def get_sun_intensity_level(sunpower):
    """Determine sun intensity level from sunpower (W/m²)"""
    if sunpower is None or sunpower == 0:
        return {
            'level': 'None',
            'color': 'gray',
            'icon': '🌙',
            'advice': 'No sun protection needed'
        }
    elif sunpower < 100:
        return {
            'level': 'Low',
            'color': 'green',
            'icon': '🌤️',
            'advice': 'Minimal sun protection needed'
        }
    elif sunpower < 300:
        return {
            'level': 'Moderate',
            'color': 'orange',
            'icon': '☀️',
            'advice': 'Consider sunscreen if outdoors for extended periods'
        }
    else:
        return {
            'level': 'High',
            'color': 'red',
            'icon': '🌞',
            'advice': 'Sunscreen recommended! Limit exposure during peak hours'
        }


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


def get_multi_city_weather(user_city=None, user_station=None, comparison_cities=None):
    """Get weather data for user's city + configurable Dutch cities"""
    comparison_data = []
    
    # Default cities if none provided
    if comparison_cities is None:
        comparison_cities = {
            'Amsterdam': (52.3676, 4.9041),
            'Rotterdam': (51.9225, 4.47917),
            'The Hague': (52.0705, 4.3007),
            'Utrecht': (52.0907, 5.1214),
            'Eindhoven': (51.4416, 5.4697)
        }
    
    # Add user's searched city first (if provided)
    if user_city and user_station:
        comparison_data.append({
            'city': user_city + " ⭐",  # Star to highlight it's the searched city
            'temp': user_station.get('temperature', 'N/A'),
            'rain': user_station.get('precipitation', 0),
            'wind': user_station.get('windspeed', 'N/A'),
            'station': user_station.get('stationname', 'Unknown')
        })
    
    all_stations = get_all_stations()
    
    for city_name, coords in comparison_cities.items():
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
    """Speak weather summary aloud with fallback"""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 165)
        engine.setProperty('volume', 1.0)
        engine.say(message)
        engine.runAndWait()
        return True, "Success"
    except Exception as e:
        return False, str(e)


# --- Streamlit UI ---

st.set_page_config(page_title="WeerWijs", page_icon="🌦️", layout="wide")

st.title("🌦️ WeerWijs")
st.write("*Your smart Dutch weather companion* - Real-time insights, smart recommendations, and comprehensive city comparisons.")

# Inject responsive CSS for mobile optimization
st.markdown("""
<style>
    /* Mobile responsive styles */
    @media (max-width: 768px) {
        /* Allow columns to wrap instead of forcing full vertical stack */
        .stColumns {
            flex-wrap: wrap !important;
            gap: 0.5rem !important;
        }
        
        /* Columns should be flexible but allow wrapping */
        [data-testid="column"] {
            flex: 1 1 45% !important;  /* Allow 2 columns per row on mobile */
            min-width: 45% !important;
            margin-bottom: 1rem;
        }
        
        /* For very small items (like 5-7 columns), make them even smaller */
        .stColumns:has(> [data-testid="column"]:nth-child(5)) [data-testid="column"],
        .stColumns:has(> [data-testid="column"]:nth-child(6)) [data-testid="column"],
        .stColumns:has(> [data-testid="column"]:nth-child(7)) [data-testid="column"] {
            flex: 1 1 30% !important;  /* 3 columns per row for legend/city comparison */
            min-width: 30% !important;
        }
        
        /* Reduce padding on mobile for more screen space */
        .block-container {
            padding: 1rem 0.75rem 2rem 0.75rem !important;
            max-width: 100% !important;
        }
        
        /* Adjust font sizes for mobile readability */
        h1 { 
            font-size: 1.8rem !important; 
            margin-bottom: 0.5rem !important;
        }
        h2, .stSubheader { 
            font-size: 1.4rem !important; 
            margin-top: 1rem !important;
        }
        h3 { 
            font-size: 1.2rem !important; 
        }
        
        /* Ensure buttons are touch-friendly (min 44px height) */
        .stButton button {
            min-height: 44px !important;
            padding: 0.75rem 1rem !important;
            font-size: 1rem !important;
        }
        
        /* Make form submit buttons full width on mobile */
        [data-testid="stFormSubmitButton"] button {
            width: 100% !important;
        }
        
        /* Optimize input fields for mobile */
        input[type="text"] {
            font-size: 16px !important; /* Prevents zoom on iOS */
            padding: 0.75rem !important;
        }
        
        /* Adjust metrics and info boxes */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }
        
        /* Make success/warning/info boxes more compact */
        .stAlert {
            padding: 0.75rem !important;
            margin: 0.5rem 0 !important;
        }
        
        /* Optimize plotly charts for mobile */
        .js-plotly-plot {
            width: 100% !important;
        }
        
        /* Ensure maps are responsive */
        iframe {
            max-width: 100% !important;
        }
        
        /* Reduce caption font size slightly */
        .stCaptionContainer {
            font-size: 0.75rem !important;
        }
        
        /* Make dividers more subtle on mobile */
        hr {
            margin: 1rem 0 !important;
        }
        
        /* Make markdown text in columns more compact */
        [data-testid="column"] p {
            font-size: 0.9rem !important;
            margin-bottom: 0.5rem !important;
        }
    }
    
    /* Tablet optimization (between mobile and desktop) */
    @media (min-width: 769px) and (max-width: 1024px) {
        .block-container {
            padding: 2rem 2rem 3rem 2rem !important;
        }
        
        [data-testid="column"] {
            min-width: 45% !important;
        }
    }
    
    /* Ensure all devices can scroll smoothly */
    html {
        scroll-behavior: smooth;
    }
    
    /* Prevent horizontal overflow */
    body {
        overflow-x: hidden !important;
    }
    
    .main {
        overflow-x: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# Connection status check removed - only show errors in fetch process

# Initialize session state
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = None
if 'city_name' not in st.session_state:
    st.session_state.city_name = None
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'first_load' not in st.session_state:
    st.session_state.first_load = True

# Auto-load Amsterdam on first visit
if st.session_state.first_load:
    st.session_state.first_load = False
    default_city = "Amsterdam"
    with st.spinner("Loading weather for Amsterdam..."):
        try:
            coords = get_city_coordinates(default_city)
            if coords:
                station, distance = find_nearest_station(coords)
                all_stations = get_all_stations()
                if station:
                    st.session_state.weather_data = {
                        'coords': coords,
                        'station': station,
                        'distance': distance,
                        'all_stations': all_stations
                    }
                    st.session_state.city_name = default_city
        except Exception:
            pass  # Silently fail, user can search manually

# Search Form with prominent styling
st.markdown("### 🔍 **Explore Weather by City**")
with st.form("city_search_form", clear_on_submit=False):
    city = st.text_input(
        "Which city's weather would you like to explore?", 
        "Amsterdam", 
        placeholder="e.g., Amsterdam, Rotterdam, Utrecht...",
        help="Enter any city in the Netherlands"
    )
    submitted = st.form_submit_button("🌤️ Get Weather", type="primary", use_container_width=True)

if submitted:
    with st.spinner("Fetching live weather data..."):
        try:
            coords = get_city_coordinates(city)
            if not coords:
                st.error("⚠️ City not found in the Netherlands. Please enter a Dutch city (e.g., Amsterdam, Rotterdam, Utrecht, Leiden).")
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
        except Exception as e:
            st.error(f"""
            ❌ **Unable to fetch weather data**
            
            **Error:** {str(e)}
            
            **Possible solutions:**
            - Check your internet connection
            - Try again in a few seconds
            - The weather service might be temporarily down
            """)
            if st.button("🔄 Retry"):
                st.rerun()

# Display weather data if available in session state
if st.session_state.weather_data:
    data = st.session_state.weather_data
    city_display = st.session_state.city_name
    coords = data['coords']
    station = data['station']
    distance = data['distance']
    all_stations = data['all_stations']
    
    # Station info removed for cleaner UI
    
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
    
    # Row 1: Current Weather + Clothing Advisor + Activity Recommendations (3 columns)
    row1_col1, row1_col2, row1_col3 = st.columns([1, 1, 1])
    
    with row1_col1:
        st.subheader("Current Weather")
        st.success(msg)
        
        # Weather metrics as simple list
        st.write("**Current conditions:**")
        
        # Temperature
        feels_like = station.get('feeltemperature')
        if feels_like is not None:
            st.write(f"🌡️ **Temperature:** {temp}°C (feels like {feels_like}°C)")
        else:
            st.write(f"🌡️ **Temperature:** {temp}°C")
        
        # Wind
        wind_gusts = station.get('windgusts')
        if wind_gusts:
            st.write(f"💨 **Wind Speed:** {windspeed} Bft (gusts: {wind_gusts} m/s)")
        else:
            st.write(f"💨 **Wind Speed:** {windspeed} Bft")
        
        # Precipitation
        rain_24h = station.get('rainFallLast24Hour', 0)
        if rain_24h:
            st.write(f"🌧️ **Precipitation:** {rain if rain else 0} mm (24h total: {rain_24h} mm)")
        else:
            st.write(f"🌧️ **Precipitation:** {rain if rain else 0} mm")
        
        # Humidity
        humidity = station.get('humidity')
        if humidity is not None:
            st.write(f"💧 **Humidity:** {humidity}%")
        
        # Visibility
        visibility = station.get('visibility')
        if visibility is not None:
            vis_km = visibility / 1000
            st.write(f"👁️ **Visibility:** {vis_km:.1f} km")
        
        # Air pressure
        pressure = station.get('airpressure')
        if pressure is not None:
            st.write(f"🌐 **Air Pressure:** {pressure} hPa")
        
        # Sun intensity
        sunpower = station.get('sunpower')
        if sunpower is not None:
            sun_info = get_sun_intensity_level(sunpower)
            st.write(f"{sun_info['icon']} **Sun Intensity:** {sun_info['level']} ({sunpower} W/m²)")
            st.caption(f"   {sun_info['advice']}")

        # Optional voice alert
        if st.button("🔊 Speak Weather Summary"):
            forecast_msg = get_forecast(*coords)
            summary = f"In {city_display}, {msg} {forecast_msg}"
            # Remove emojis for speech
            clean_summary = summary.replace("🌧", "").replace("☀️", "").replace("💨", "").replace("🥶", "")
            
            success, error_msg = speak_text(clean_summary)
            
            if success:
                st.success("🔊 Speaking weather summary...")
            else:
                st.warning(f"⚠️ Text-to-speech unavailable: {error_msg}")
                st.info("💡 Download the summary as text instead:")
                st.download_button(
                    label="📥 Download Weather Summary",
                    data=summary,
                    file_name=f"weather_{city_display}_{time.strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
    
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
    
    with row1_col3:
        # Activity Recommendations
        st.subheader("🎯 Activity Recommendations")
        recommendations = get_activity_recommendations(station)
        
        for rec in recommendations:
            if rec['suitable']:
                st.success(f"✅ **{rec['name']}**: {rec['reason']}")
            else:
                st.warning(f"⚠️ **{rec['name']}**: {rec['reason']}")
    
    # 3-Hour Rain Forecast
    st.divider()
    forecast_msg = get_forecast(*coords)
    st.subheader("🌧️ 3-Hour Rain Forecast")
    st.info(forecast_msg)
    
    # Row 3: 5-Day Forecast (left) + Interactive Map (right)
    st.divider()
    
    # Two columns for forecast and map
    forecast_col, map_col = st.columns([1, 1])
    
    with forecast_col:
        st.subheader("📅 5-Day Forecast")
        
        try:
            forecast_data = get_five_day_forecast()
            
            if forecast_data and len(forecast_data) > 0:
                # Prepare data for visualization
                import plotly.graph_objects as go
                from datetime import datetime
                
                days = []
                min_temps = []
                max_temps = []
                rain_chances = []
                sun_chances = []
                
                # Helper function to safely convert values to int
                def safe_int(value, default=0):
                    """Safely convert a value to int, handling various formats"""
                    if value is None:
                        return default
                    try:
                        # Try direct int conversion first
                        return int(value)
                    except (ValueError, TypeError):
                        try:
                            # Try float conversion first (handles decimal strings)
                            return int(float(value))
                        except (ValueError, TypeError):
                            return default
                
                for day in forecast_data:
                    date_str = day['day'][:10]  # Get YYYY-MM-DD
                    days.append(date_str)
                    min_temps.append(safe_int(day.get('mintemperature', 0)))
                    max_temps.append(safe_int(day.get('maxtemperature', 0)))
                    rain_chances.append(safe_int(day.get('rainChance', 0)))
                    sun_chances.append(safe_int(day.get('sunChance', 0)))
                
                # Create figure with secondary y-axis
                fig = go.Figure()
                
                # Add temperature traces
                fig.add_trace(go.Scatter(
                    x=days, y=max_temps,
                    name='Max Temp',
                    line=dict(color='red', width=2),
                    mode='lines+markers'
                ))
                fig.add_trace(go.Scatter(
                    x=days, y=min_temps,
                    name='Min Temp',
                    line=dict(color='blue', width=2),
                    mode='lines+markers',
                    fill='tonexty',
                    fillcolor='rgba(200, 200, 255, 0.2)'
                ))
                
                # Add rain chance as bar chart
                fig.add_trace(go.Bar(
                    x=days, y=rain_chances,
                    name='Rain %',
                    yaxis='y2',
                    marker=dict(color='lightblue', opacity=0.6)
                ))
                
                # Update layout for side column
                fig.update_layout(
                    xaxis_title='Date',
                    yaxis=dict(title='Temp (°C)'),
                    yaxis2=dict(
                        title='Rain %',
                        overlaying='y',
                        side='right',
                        range=[0, 100]
                    ),
                    hovermode='x unified',
                    height=350,
                    margin=dict(l=20, r=20, t=20, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Display all 5 days horizontally
                st.caption("**5-Day Details:**")
                fcst_cols = st.columns(5)
                for idx, day in enumerate(forecast_data):
                    with fcst_cols[idx]:
                        # Convert date to DD/MM format
                        from datetime import datetime
                        date_obj = datetime.strptime(day['day'][:10], '%Y-%m-%d')
                        date_str = date_obj.strftime('%d/%m')
                        st.markdown(f"**{date_str}**")
                        st.markdown(f"🌡️ {day['mintemperature']}-{day['maxtemperature']}°C")
                        st.markdown(f"🌧️ {day['rainChance']}%")
            else:
                st.info("Forecast unavailable")
        except Exception as e:
            st.warning(f"Could not load forecast: {str(e)}")
    
    with map_col:
        st.subheader("🗺️ Weather Map")
        st.caption("Click markers for details")
        
        # Create and display the map
        weather_map = create_weather_map(all_stations, coords, city_display)
        st_folium(weather_map, width=None, height=500)
        
        # Add legend below map
        st.caption("**Map Legend:**")
        legend_cols = st.columns(7)
        with legend_cols[0]:
            st.markdown("💧 **Raining**")
        with legend_cols[1]:
            st.markdown("🟣 **Frigid**")
            st.write("<5°C")
        with legend_cols[2]:
            st.markdown("⚪ **Cold**")
            st.write("5-10°C")
        with legend_cols[3]:
            st.markdown("🟢 **Nice**")
            st.write("10-20°C")
        with legend_cols[4]:
            st.markdown("🟠 **Warm**")
            st.write("20-25°C")
        with legend_cols[5]:
            st.markdown("🔴 **Hot**")
            st.write("25+°C")
        with legend_cols[6]:
            st.markdown("🏠 **Your**")
            st.write("Location")

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
