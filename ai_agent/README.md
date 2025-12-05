# Weather AI Agent

This project is a **Weather AI Agent** designed to provide live weather updates, 3-hour rain forecasts, and voice alerts for cities in the Netherlands.

## Features

- **Weather Data**: Fetches live weather data from Buienradar's API.
- **Rain Forecast**: Predicts rain intensity and timing for the next 3 hours.
- **Geolocation**: Uses the `geopy` library to find city coordinates and calculate distances to weather stations.
- **Text-to-Speech**: Uses `pyttsx3` to provide voice alerts for weather summaries.
- **Streamlit UI**: Offers a user-friendly interface for interacting with the weather agent.

## How to Run

### Command-Line Weather Agent

1. Navigate to the `ai_agent` directory:
   ```bash
   cd ai_agent
   ```
2. Run the script:
   ```bash
   python weather_agent.py
   ```
3. Enter the city name when prompted to get the weather status.

### Streamlit Weather Dashboard

1. Navigate to the `ai_agent` directory:
   ```bash
   cd ai_agent
   ```
2. Run the Streamlit app:
   ```bash
   streamlit run weather_dashboard.py
   ```
3. Open the provided URL in your browser to interact with the dashboard.

## Requirements

Install the required dependencies using `pip`:
```bash
pip install -r ai_agent/requirements.txt
```

## Project Structure

```
.gitattributes
.gitignore
ai_agent/
    README.md
    requirements.txt
    weather_agent.py
    weather_dashboard.py
```

This project is ideal for users in the Netherlands who want quick and interactive weather updates.