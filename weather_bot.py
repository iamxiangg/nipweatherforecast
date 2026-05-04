import requests
import os
import sys
from datetime import datetime

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
DB_FILE = "last_weather.txt"

# Triangulated Stations (Primary + 2 neighbors)
TOWNS = {
    "Sembawang": {"stations": ["S104", "S109", "S102"], "region": "north", "area": "Sembawang"},
    "Yishun": {"stations": ["S122", "S104", "S109"], "region": "north", "area": "Yishun"},
    "Novena": {"stations": ["S111", "S116", "S106"], "region": "central", "area": "Novena"},
    "Marina Bay": {"stations": ["S108", "S121", "S111"], "region": "south", "area": "Downtown"}
}

def get_status_label(val):
    rate = val * 12 
    if val == 0: return "☁️ Dry", rate
    if rate < 2.5: return "💧 Light Rain", rate
    if 2.5 <= rate < 10: return "🌧️ Moderate Rain", rate
    if 10 <= rate < 50: return "⛈️ Heavy Rain", rate
    return "🌊 Very Heavy Rain", rate

def get_data():
    try:
        # 1. 2-Hour Nowcast
        rf = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15)
        f_item = rf.json().get('data', {}).get('items', [])[0]
        nowcast = {f['area']: f['forecast'] for f in f_item.get('forecasts', [])}
        timing = f_item.get('update_timestamp', 'T00:00').split('T')[1][:5]

        # 2. Rainfall
        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        r_readings = rr.json().get('data', {}).get('readings', [])[0].get('data', [])
        rain_map = {r['stationId']: r['value'] for r in r_readings}

        # 3. 24-Hour Forecast
        r24 = requests.get("https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast", timeout=15)
        periods_24 = r24.json().get('data', {}).get('records', [{}])[0].get('periods', [])
        today_str = datetime.now().strftime('%Y-%m-%d')
        formatted_24h = {"north": [], "central": [], "south": []}

        for p in periods_24:
            p_date = p.get('timePeriod', {}).get('start', '').split('T')[0]
            day = "today" if p_date == today_str else "tomorrow"
            raw_text = p.get('timePeriod', {}).get('text', '')
            if "6 am to Midday" in raw_text: p_name = "Morning"
            elif "Midday to 6 pm" in raw_text: p_name = "Afternoon"
            else: p_name = "Night"
            for reg in formatted_24h.keys():
                txt = p.get('regions', {}).get(reg, {}).get('text', 'N/A')
                formatted_24h[reg].append(f"{p_name} ({day}): {txt}")

        return nowcast, rain_map, timing, formatted_24h
    except:
        return "ERROR", None, None, None

def main():
    force_push = "--force" in sys.argv
    nowcast, rain, timing, forecast24 = get_data()
    if nowcast == "ERROR" or not nowcast: 
        print("CHANGE_DETECTED=false")
        return

    current_state_list = []
    message_blocks = []
    
    # Load previous state for bold/italicize comparison
    last_state = open(DB_FILE, "r").read().strip() if os.path.exists(DB_FILE) else ""
    last_map = {}
    if last_state:
        for entry in last_state.split("|"):
            parts = entry.split(":")
            if len(parts) >= 3:
                last_map[parts[0]] = {"cat": parts[1], "exp": parts[2]}

    for town, cfg in TOWNS.items():
        expect = nowcast.get(cfg['area'], "No Data")
        vals = [rain.get(sid, 0.0) for sid in cfg['stations']]
        max_raw_val = max(vals) 
        status_label, rate = get_status_label(max_raw_val)
        
        current_state_list.append(f"{town}:{status_label}:{expect}")
        
        # Compare and Format
        prev = last_map.get(town, {"cat": "", "exp": ""})
        # Use bold-italics (***) if different from last saved state
        d_status = f"***{status_label}***" if status_label != prev['cat'] and last_state else status_label
        d_expect = f"***{expect}***" if expect != prev['exp'] and last_state else expect

        block = f"🏠 *{town.upper()}* ({cfg['region'].capitalize()})\n"
        block += f"└ *Current:* {d_status} ({rate:.1f} mm/h)\n"
        block += f"└ *Expect:* {d_expect}\n"
        block += f"└ *24h Forecast:*\n"
        for line in forecast24.get(cfg['region'], []):
            block += f"   • {line}\n"
        message_blocks.append(block)

    state_string = "|".join(current_state_list)

    if state_string != last_state or force_push:
        header = "🌅 *Morning Weather Brief*" if force_push else "📊 *Weather Dashboard Update*"
        msg = f"{header} ({timing})\n------------------------------------\n\n" + "\n".join(message_blocks)
        
        for cid in CHAT_IDS:
            if cid.strip():
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": cid.strip(), "text": msg, "parse_mode": "Markdown"})
        
        with open(DB_FILE, "w") as f: 
            f.write(state_string)
        print("CHANGE_DETECTED=true")
    else:
        print("CHANGE_DETECTED=false")

if __name__ == "__main__":
    main()
