import streamlit as st
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pyttsx3

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


def speak_text(message):
    """Speak weather summary aloud"""
    engine = pyttsx3.init()
    engine.say(message)
    engine.runAndWait()


# --- Streamlit UI ---

st.set_page_config(page_title="Weather AI Agent", page_icon="🌦️", layout="centered")

st.title("🌦️ Personal Weather AI Agent (Netherlands)")
st.write("Get live weather updates, 3-hour rain forecasts, and even voice alerts!")

# Input city name
city = st.text_input("Enter your city name:", "Leiden")

if st.button("Get Weather"):
    with st.spinner("Fetching live weather data..."):
        coords = get_city_coordinates(city)
        if not coords:
            st.error("⚠️ Could not find that city. Try again.")
        else:
            st.success(f"📍 Found {city}: {coords}")

            # Get nearest station
            station, distance = find_nearest_station(coords)
            if station:
                st.info(f"📡 Nearest station: {station['stationname']} ({distance:.1f} km away)")
                temp = station['temperature']
                rain = station['precipitation']
                windspeed = station['windspeed']
                wind_dir = station['winddirection']

                # Decision logic
                if rain > 0:
                    msg = f"🌧 It's raining ({rain} mm). Take an umbrella!"
                elif temp < 10:
                    msg = f"🥶 It's cold ({temp}°C). Wear a warm jacket!"
                elif "W" in wind_dir and windspeed > 6:
                    msg = f"💨 It's windy ({windspeed} Bft). Be careful if cycling!"
                else:
                    msg = f"☀️ The weather looks nice ({temp}°C, no rain). Enjoy your day!"

                st.subheader("Current Weather")
                st.success(msg)
                st.metric("Temperature (°C)", temp)
                st.metric("Wind Speed (Bft)", windspeed)
                st.metric("Precipitation (mm)", rain)

                # Forecast
                forecast_msg = get_forecast(*coords)
                st.subheader("3-Hour Forecast")
                st.info(forecast_msg)

                # Optional voice alert
                if st.button("🔊 Speak Weather Summary"):
                    summary = f"In {city}, {msg} {forecast_msg}"
                    speak_text(summary)
                    st.toast("Speaking weather summary...")

