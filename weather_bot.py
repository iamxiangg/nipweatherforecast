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

        # 2. Rainfall (5-min readings)
        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        r_data = rr.json().get('data', {}).get('readings', [])[0].get('data', [])
        rain_map = {r['stationId']: r['value'] for r in r_data}

        # 3. 24-Hour Forecast (North, Central, South)
        r24 = requests.get("https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast", timeout=15)
        periods_24 = r24.json().get('data', {}).get('records', [{}])[0].get('periods', [])
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        formatted_24h = {"north": [], "central": [], "south": []}

        for p in periods_24:
            p_date = p.get('timePeriod', {}).get('start', '').split('T')[0]
            day_label = "today" if p_date == today_str else "tomorrow"
            p_text = p.get('timePeriod', {}).get('text', 'Period')
            
            for reg in formatted_24h.keys():
                forecast_text = p.get('regions', {}).get(reg, {}).get('text', 'N/A')
                formatted_24h[reg].append(f"{p_text} ({day_label}): {forecast_text}")

        return nowcast, rain_map, timing, formatted_24h
    except:
        return "ERROR", None, None, None

def main():
    nowcast, rain, timing, forecast24 = get_data()
    if nowcast == "ERROR" or not nowcast: return

    current_state_list = []
    message_blocks = []

    for town, cfg in TOWNS.items():
        expect = nowcast.get(cfg['area'], "No Data")
        raw_val = rain.get(cfg['station'], 0.0)
        status_label, hourly_rate = get_status_label(raw_val)
        region = cfg['region']
        
        current_state_list.append(f"{town}:{status_label}:{expect}")
        
        block = f"🏠 *{town.upper()}* ({region.capitalize()})\n"
        block += f"└ *Current:* {status_label} ({hourly_rate:.1f} mm/h)\n"
        block += f"└ *Expect:* {expect}\n"
        block += f"└ *24h Forecast:*\n"
        for line in forecast24.get(region, []):
            block += f"   • {line}\n"
        message_blocks.append(block)

    state_string = "|".join(current_state_list)
    last_state = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: last_state = f.read().strip()

    if state_string != last_state:
        msg = f"📊 *Weather Dashboard Update* ({timing})\n"
        msg += "------------------------------------\n\n" + "\n".join(message_blocks)
        
        for cid in CHAT_IDS:
            if not cid.strip(): continue
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                          json={"chat_id": cid.strip(), "text": msg, "parse_mode": "Markdown"})
        
        with open(DB_FILE, "w") as f: f.write(state_string)
        print("CHANGE_DETECTED=true")
    else:
        print("CHANGE_DETECTED=false")

if __name__ == "__main__":
    main()
