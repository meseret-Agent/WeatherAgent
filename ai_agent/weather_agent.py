import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

"""
Personal AI Weather Agent for the Netherlands” — built in Python using live Buienradar data and geolocation intelligence.

"""
class WeatherAgent:
    def __init__(self, city="Leiden"):
        self.city = city
        self.data = None
        self.user_coords = None

    def get_city_coordinates(self):
        """Get latitude and longitude of the given city using geopy"""
        geolocator = Nominatim(user_agent="weather_agent")
        location = geolocator.geocode(self.city + ", Netherlands")
        if location:
            self.user_coords = (location.latitude, location.longitude)
            print(f"📍 Found {self.city}: {self.user_coords}")
        else:
            print(f"⚠️ Could not find coordinates for {self.city}")

    def find_nearest_station(self):
        """Find the nearest Buienradar station"""
        url = "https://data.buienradar.nl/2.0/feed/json"
        response = requests.get(url)
        data = response.json()

        if not self.user_coords:
            print("⚠️ No coordinates for your city.")
            return

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

    def act(self):
        """Decide what to do based on the weather"""
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

# --- Run the agent interactively ---
city = input("Enter your city name (e.g. Leiden): ")
agent = WeatherAgent(city)

agent.get_city_coordinates()
agent.find_nearest_station()
print(agent.act())
