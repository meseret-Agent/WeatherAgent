# Weather AI Agent

This project is a **Weather AI Agent** designed to provide live weather updates, 3-hour rain forecasts, and voice alerts for cities in the Netherlands.

## Features

- **✅ Live Weather Data**: Fetches real-time weather from Buienradar's API.
- **🗺️ Interactive Weather Map**: dynamic map showing weather stations across the Netherlands with color-coded conditions (Rain, Cold, Nice, Hot).
- **🎯 Activity Recommendations**: Smart suggestions for outdoor activities like cycling, running, BBQ, and walking based on current conditions.
- **👔 Smart Clothing Advisor**: Detailed outfit advice including layers, footwear, and accessories.
- **🏙️ Multi-City Comparison**: Compare your city's weather side-by-side with 5 major Dutch cities (Amsterdam, Rotterdam, The Hague, Utrecht, Eindhoven).
- **🗣️ Voice Alerts**: distinct text-to-speech weather summaries.
- **🌧️ Rain Forecast**: Predicts rain intensity for the next 3 hours.

## How to Run

### Streamlit Weather Dashboard (Recommended)

1. Navigate to the `ai_agent` directory:
   ```bash
   cd ai_agent
   ```
2. Run the Streamlit app:
   ```bash
   streamlit run weather_dashboard.py
   ```
3. Open the provided URL in your browser (usually `http://localhost:8501`).

### Command-Line Weather Agent

1. Run the script:
   ```bash
   python weather_agent.py
   ```
2. Enter the city name when prompted.

## Requirements

Install the required dependencies:
```bash
pip install -r ai_agent/requirements.txt
```

## Project Structure

```
ai_agent/
    README.md               # Project documentation
    requirements.txt        # Python dependencies
    weather_dashboard.py    # Main Streamlit application (GUI)
    weather_agent.py        # Command-line interface logic
    .env                    # Environment variables (optional)
```

This project is ideal for users in the Netherlands who want a comprehensive, interactive personal weather assistant.