# WeerWijs 🌦️

**Your smart Dutch weather companion** - A comprehensive weather intelligence platform for the Netherlands, providing live updates, 5-day forecasts, smart recommendations, and interactive visualizations.

## Features

### Core Weather Intelligence
- **✅ Live Weather Data**: Real-time weather from Buienradar with automatic retry logic
- **🗺️ Interactive Weather Map**: Dynamic map with all Dutch weather stations, color-coded by conditions
- **🌧️ Rain Forecast**: 3-hour rain predictions with intensity warnings

### Enhanced Weather Metrics (New!)
- **🌡️ Feels-Like Temperature**: Wind chill-adjusted temperature for real comfort assessment
- **💧 Humidity & Visibility**: Track air moisture and visibility distance
- **🌐 Air Pressure**: Atmospheric pressure monitoring
- **📊 24-Hour Rainfall**: Total precipitation in the last 24 hours
- **📋 Weather Descriptions**: Official Buienradar weather condition text

### 5-Day Forecast (New!)
- **📅 Daily Forecast**: Min/max temperatures, rain & sun probabilities
- **📈 Interactive Charts**: Plotly visualization of temperature trends and rain chances
- **💨 Wind Predictions**: 5-day wind speed forecast

### Sun Intensity Monitor (New!)
- **☀️ UV-Like Indicator**: Sun intensity in W/m² with color-coded levels
- **🌞 Smart Advice**: Automatic sunscreen recommendations based on sun power
- **🎨 Visual Warnings**: Green (low), Orange (moderate), Red (high) indicators

### Smart Recommendations
- **🎯 Activity Recommendations**: Cycling, running, BBQ, beach, walking - with suitability analysis
- **👔 Smart Clothing Advisor**: Outfit suggestions with layers, footwear, and accessories
- **🏙️ Multi-City Comparison**: Compare 6 cities side-by-side (configurable)
- **🗣️ Voice Alerts**: TTS weather summaries with download fallback

### Performance & Reliability
- **⚡ Smart Caching**: 70% fewer API calls, instant repeat searches (5-30 min cache)
- **🔄 Auto-Retry**: Exponential backoff for network failures
- **🔌 Offline Mode**: Shows cached data when internet unavailable
- **🟢 Connection Status**: Real-time connectivity indicator

## How to Run

### 1. Activate Virtual Environment

Before running the application, activate the virtual environment. **Note:** The `.venv` folder is in the project root directory.

**If you're in the project root** :

**macOS/Linux:**
```bash
source .venv/bin/activate
```

*Windows:*
```bash
.venv\Scripts\activate
```

After activation, you should see `(.venv)` at the beginning of your command prompt.

To deactivate when you're done:
```bash
deactivate
```

### 2. Streamlit Weather Dashboard (Recommended)

1. Run the Streamlit app:
   ```bash
   streamlit run app.py
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
pip install -r requirements.txt
```

## Project Structure

```
README.md               # Project documentation
requirements.txt        # Python dependencies
app.py                  # Main Streamlit application (GUI)
weather_agent.py        # Command-line interface logic
.env                    # Environment variables (optional)
```

This project is ideal for users in the Netherlands who want a comprehensive, interactive personal weather assistant.

---
*Last deployment: 2025-12-24*