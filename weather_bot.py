import requests
import os
import sys
from datetime import datetime

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
DB_FILE = "last_weather.txt"

TOWNS = {
    "Sembawang": {"station": "S104", "region": "north", "area": "Sembawang"},
    "Yishun": {"station": "S122", "region": "north", "area": "Yishun"},
    "Novena": {"station": "S111", "region": "central", "area": "Novena"},
    "Marina Bay": {"station": "S108", "region": "south", "area": "Downtown"}
}

def get_status_label(val):
    hourly_rate = val * 12 
    if val == 0: return "☁️ Dry", hourly_rate
    if hourly_rate < 2.5: return "💧 Light Rain", hourly_rate
    if 2.5 <= hourly_rate < 10: return "🌧️ Moderate Rain", hourly_rate
    if 10 <= hourly_rate < 50: return "⛈️ Heavy Rain", hourly_rate
    return "🌊 Very Heavy Rain", hourly_rate

def get_data():
    try:
        # 1. 2-Hour Nowcast
        rf = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15)
        f_item = rf.json().get('data', {}).get('items', [])[0]
        nowcast = {f['area']: f['forecast'] for f in f_item.get('forecasts', [])}
        timing = f_item.get('update_timestamp', 'T00:00').split('T')[1][:5]

        # 2. Rainfall
        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        r_data = rr.json().get('data', {}).get('readings', [])[0].get('data', [])
        rain_map = {r['stationId']: r['value'] for r in r_data}

        # 3. 24-Hour Forecast
        r24 = requests.get("https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast", timeout=15)
        periods_24 = r24.json().get('data', {}).get('records', [{}])[0].get('periods', [])
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        formatted_24h = {"north": [], "central": [], "south": []}

        for p in periods_24:
            start_time = p.get('timePeriod', {}).get('start', '')
            p_date = start_time.split('T')[0]
            day_label = "today" if p_date == today_str else "tomorrow"
            
            # --- CONCISE TIME LOGIC ---
            # Extract just the first word (e.g., "Morning", "Afternoon", "Night")
            raw_text = p.get('timePeriod', {}).get('text', 'Period')
            if "6 am to Midday" in raw_text: p_name = "Morning"
            elif "Midday to 6 pm" in raw_text: p_name = "Afternoon"
            elif "6 pm to 6 am" in raw_text: p_name = "Night"
            else: p_name = raw_text # Fallback
            
            for reg in formatted_24h.keys():
                forecast_text = p.get('regions', {}).get(reg, {}).get('text', 'N/A')
                formatted_24h[reg].append(f"{p_name} ({day_label}): {forecast_text}")

        return nowcast, rain_map, timing, formatted_24h
    except:
        return "ERROR", None, None, None

# ... main() remains same as previous version ...
