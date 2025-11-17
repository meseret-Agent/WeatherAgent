import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pyttsx3  # For text-to-speech

class WeatherAgent:
    def __init__(self, city="Leiden"):
        self.city = city
        self.data = None
        self.user_coords = None

# ------------------------
# 1. Get city coordinates
# ------------------------

    def get_city_coordinates(self):
        geolocator = Nominatim(user_agent="weather_agent")
        location = geolocator.geocode(self.city + ", Netherlands")
        if location:
            self.user_coords = (location.latitude, location.longitude)
            print(f"📍 Found {self.city}: {self.user_coords}")
        else:
            print(f"⚠️ Could not find coordinates for {self.city}")

# --------------------------------------
# 2. Find the nearst Buienradar station
# --------------------------------------
    def find_nearest_station(self):
        url = "https://data.buienradar.nl/2.0/feed/json"
        response = requests.get(url)
        data = response.json()

        stations = data['actual']['stationmeasurements']
        nearest_station = None
        min_distance = float("inf")

        for station in stations:
            station_coords = (station['lat'], station['lon'])
            distance = geodesic(self.user_coords, station_coords).km

            if distance < min_distance:
                min_distance = distance
                nearest_station = station

        self.data = nearest_station
        print(f"📡 Nearest station: {nearest_station['stationname']} ({min_distance:.1f} km away)")

# --------------------------------------
# 3. 3-Hour Rain Forecast
# --------------------------------------
    def forecast(self):
        """Get 3-hour rain forecast from Buienradar"""
        if not self.user_coords:
            return "⚠️ No coordinates available for forecast."

        lat, lon = self.user_coords
        url = f"https://gpsgadget.buienradar.nl/data/raintext?lat={lat}&lon={lon}"
        response = requests.get(url)
        lines = response.text.strip().split("\n")

        forecast_data = []
        for line in lines:
            value, time = line.split("|")
            rain_intensity = int(value)
            forecast_data.append((rain_intensity, time))

        # Analyze if rain is expected
        will_rain = any(val > 70 for val, _ in forecast_data)
        if will_rain:
            next_rain_time = next(time for val, time in forecast_data if val > 70)
            return f"🌧 Rain expected around {next_rain_time}. Take an umbrella!"
        else:
            return "☀️ No rain expected in the next 3 hours."
        
# --------------------------------------
# 4. Current Weather Summary
# --------------------------------------
    def act(self):
        """Give a decision based on current weather"""
        if not self.data:
            return f"No weather data found for {self.city}."

        temp = self.data['temperature']
        rain = self.data['precipitation']
        windspeed = self.data['windspeed']
        wind_dir = self.data['winddirection']

        if rain > 0:
            return f"🌧 It's raining ({rain} mm). Take an umbrella!"
        elif temp < 10:
            return f"🥶 It's cold ({temp}°C). Wear a warm jacket!"
        elif "W" in wind_dir and windspeed > 6:
            return f"💨 It's windy ({windspeed} Bft). Be careful if cycling!"
        else:
            return f"☀️ The weather looks nice ({temp}°C, no rain). Enjoy your day!"

# --------------------------------------
# 5. Clean Text for Text to Speech Function
# --------------------------------------
    def clean_text(self, text):
        """Replace emojis with none readable words for voice output"""
        replacements = {
            "☀️": "",
            "🌧": "",
            "💨": "",
            "🥶": "",
            "📍": "",
            "📡": "",
        }
        for emoji, word in replacements.items():
            text = text.replace(emoji, word)
        return text

# --------------------------------------
# 6.  Text to Speech Function
# --------------------------------------
    def speak(self, message):
        """Speak only the cleaned text version (no emojis)"""
        engine = pyttsx3.init()
        # choose your voice
        # voices = engine.getProperty('voices')
        # engine.setProperty('voice',voices[14].id) # Daniel
        
        # Adjust speaking speed and volume
        engine.setProperty('rate', 165)   # 140–200, lower = slower
        engine.setProperty('volume', 1.0) # 0.0 to 1.0
        clean_message = self.clean_text(message)
        engine.say(clean_message)
        engine.runAndWait()


# --- Run the agent ---
city = input("Enter your city name (e.g. Leiden): ")
agent = WeatherAgent(city)

agent.get_city_coordinates()
agent.find_nearest_station()

# Print current weather
print(agent.act())

# Print forecast
print(agent.forecast())

# Combine both for speech
final_message = f"{agent.act()} {agent.forecast()}"
print(final_message)
agent.speak(final_message)
