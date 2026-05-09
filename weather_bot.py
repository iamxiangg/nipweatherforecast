import requests
import os
import sys
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
DB_FILE = "last_weather.txt"

# Optimized Stations (Triangulated for your 4 specific locations)
TOWNS = {
    "Sembawang": {"stations": ["S104", "S210", "S227"], "region": "north", "area": "Sembawang"},
    "Yishun": {"stations": ["S209", "S104", "S109"], "region": "north", "area": "Yishun"},
    "Novena": {"stations": ["S111", "S88", "S123"], "region": "central", "area": "Novena"},
    "Marina Bay": {"stations": ["S108", "S119", "S121"], "region": "south", "area": "City"}
}

def get_severity_logic(status_label, expect):
    """Returns a color emoji based on how 'bad' the weather is."""
    bad_terms = ["heavy", "thundery", "very heavy", "sumatra"]
    warn_terms = ["moderate", "rain", "showers"]
    
    combined = (status_label + " " + expect).lower()
    
    if any(word in combined for word in bad_terms):
        return "🔴"
    if any(word in combined for word in warn_terms):
        return "🟡"
    return "🟢"

def get_status_label(val):
    rate = val * 12 
    if val == 0: return "☁️ Dry", rate
    if rate < 2.5: return "💧 Light Rain", rate
    if 2.5 <= rate < 10: return "🌧️ Moderate Rain", rate
    if 10 <= rate < 50: return "⛈️ Heavy Rain", rate
    return "🌊 Very Heavy Rain", rate

def get_data():
    try:
        # TZ Fix: Use Singapore Time
        sgt = timezone(timedelta(hours=8))
        now_sg = datetime.now(sgt)
        today_str = now_sg.strftime('%Y-%m-%d')

        # 1. Nowcast API (Next 2h)
        rf = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15)
        f_item = rf.json().get('data', {}).get('items', [])[0]
        nowcast = {f['area']: f['forecast'] for f in f_item.get('forecasts', [])}
        timing = f_item.get('update_timestamp', 'T00:00').split('T')[1][:5]

        # 2. Rainfall API
        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        all_readings = rr.json().get('data', {}).get('readings', [])
        if not all_readings: return "ERROR", None, None, None
        
        latest_reading = all_readings[-1] 
        r_data = latest_reading.get('data', [])
        rain_map = {r['stationId']: r['value'] for r in r_data}
        
        # 3. 24-Hour Forecast
        r24 = requests.get("https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast", timeout=15)
        periods_24 = r24.json().get('data', {}).get('records', [{}])[0].get('periods', [])
        formatted_24h = {"north": [], "central": [], "south": []}

        for p in periods_24:
            p_date = p.get('timePeriod', {}).get('start', '').split('T')[0]
            raw_text = p.get('timePeriod', {}).get('text', '').lower()
            day_abbr = "Tdy" if p_date == today_str else "Tmr"
            
            if "6 am" in raw_text: slot = "Mor"
            elif "midday" in raw_text: slot = "Aft"
            else: slot = "Nit"
            
            for reg in formatted_24h.keys():
                txt = p.get('regions', {}).get(reg, {}).get('text', 'N/A')
                # Use simple emoji for forecast to save space
                f_emoji = "⛈️" if "thundery" in txt.lower() else "🌧️" if "rain" in txt.lower() or "showers" in txt.lower() else "☁️"
                formatted_24h[reg].append(f"{f_emoji} ({slot} {day_abbr})")

        return nowcast, rain_map, timing, formatted_24h
    except Exception as e:
        print(f"API Error: {e}")
        return "ERROR", None, None, None

def main():
    force_push = "--force" in sys.argv
    nowcast, rain, timing, forecast24 = get_data()
    if nowcast == "ERROR" or not nowcast: 
        print("CHANGE_DETECTED=false")
        return

    current_state_list = []
    message_blocks = []
    
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
        
        prev = last_map.get(town, {"cat": "", "exp": ""})
        # Detection
        d_status = f"***{status_label}***" if status_label != prev.get('cat') and last_state else status_label
        d_expect = f"***{expect}***" if expect != prev.get('exp') and last_state else expect
        
        # Severity Icon
        sev = get_severity_logic(status_label, expect)

        # Condensed Layout
        block = f"{sev} **{town.upper()}** | {d_status}\n"
        block += f"└ **Now:** {rate:.1f} mm/h\n"
        block += f"└ **Next 2h:** {d_expect}\n"
        block += f"└ **Later:** {' | '.join(forecast24.get(cfg['region'], []))}\n"
        message_blocks.append(block)

    state_string = "|".join(current_state_list)

    if state_string != last_state or force_push:
        header = "🌅 *Morning Weather Brief*" if force_push else "📊 *Weather Dashboard Update*"
        msg = f"{header} ({timing})\n------------------------------------\n\n" + "\n\n".join(message_blocks)
        
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
