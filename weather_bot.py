import requests
import os
import sys
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
DB_FILE = "last_weather.txt"
COOLDOWN_MINUTES = 15

TOWNS = {
    "Sembawang": {"stations": ["S104", "S210", "S227"], "region": "north", "area": "Sembawang"},
    "Yishun": {"stations": ["S209", "S104", "S109"], "region": "north", "area": "Yishun"},
    "Novena": {"stations": ["S111", "S88", "S123"], "region": "central", "area": "Novena"},
    "Marina Bay": {"stations": ["S108", "S119", "S121"], "region": "south", "area": "City"}
}

def get_status_label(val, expect):
    rate = val * 12 
    is_forecast_rain = any(term in expect.lower() for term in ["rain", "showers", "thundery", "sumatra"])
    
    if val == 0:
        if is_forecast_rain: return "☁️ Pending/Incoming", rate
        return "☁️ Dry", rate
        
    if rate < 2.5: return "💧 Light Rain", rate
    if 2.5 <= rate < 10: return "🌧️ Moderate Rain", rate
    if 10 <= rate < 50: return "⛈️ Heavy Rain", rate
    return "🌊 Very Heavy Rain", rate

def get_severity_logic(status_label, expect):
    bad_terms = ["heavy", "thundery", "very heavy", "sumatra"]
    warn_terms = ["moderate", "rain", "showers", "pending"]
    combined = (status_label + " " + expect).lower()
    if any(word in combined for word in bad_terms): return "🔴"
    if any(word in combined for word in warn_terms): return "🟡"
    return "🟢"

def get_data():
    try:
        sgt = timezone(timedelta(hours=8))
        now_sg = datetime.now(sgt)
        today_str = now_sg.strftime('%Y-%m-%d')

        rf = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15)
        f_item = rf.json().get('data', {}).get('items', [])[0]
        nowcast = {f['area']: f['forecast'] for f in f_item.get('forecasts', [])}
        timing = f_item.get('update_timestamp', 'T00:00').split('T')[1][:5]

        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        all_readings = rr.json().get('data', {}).get('readings', [])
        rain_map = {r['stationId']: r['value'] for r in all_readings[-1].get('data', [])} if all_readings else {}

        r24 = requests.get("https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast", timeout=15)
        periods_24 = r24.json().get('data', {}).get('records', [{}])[0].get('periods', [])
        formatted_24h = {"north": [], "central": [], "south": []}

        for p in periods_24:
            p_date = p.get('timePeriod', {}).get('start', '').split('T')[0]
            raw_text = p.get('timePeriod', {}).get('text', '').lower()
            tmr_suffix = " (Tmr)" if p_date != today_str else ""
            slot = "AM" if "6 am to midday" in raw_text else "PM" if "midday to 6 pm" in raw_text else "Night"
            for reg in formatted_24h.keys():
                txt = p.get('regions', {}).get(reg, {}).get('text', 'N/A')
                f_emoji = "⛈️" if "thundery" in txt.lower() else "🌧️" if "rain" in txt.lower() or "showers" in txt.lower() else "☁️"
                formatted_24h[reg].append(f"{f_emoji} {slot}{tmr_suffix}")

        return nowcast, rain_map, timing, formatted_24h
    except Exception as e:
        print(f"API Error: {e}")
        return None, None, None, None

def main():
    force_push = "--force" in sys.argv
    nowcast, rain, timing, forecast24 = get_data()
    if not nowcast: return

    current_state_list = []
    message_blocks = []
    
    # Load persistence
    last_sent_time = None
    last_state = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            content = f.read().split(":", 1)
            if len(content) == 2:
                last_sent_time = datetime.fromisoformat(content[0])
                last_state = content[1]

    for town, cfg in TOWNS.items():
        expect = nowcast.get(cfg['area'], "No Data")
        vals = [rain.get(sid, 0.0) for sid in cfg['stations'] if rain.get(sid) is not None]
        max_raw_val = max(vals) if vals else 0.0
        
        status_label, rate = get_status_label(max_raw_val, expect)
        current_state_list.append(f"{town}:{status_label}:{expect}")
        
        sev = get_severity_logic(status_label, expect)
        block = f"{sev} **{town.upper()}** | {status_label}\n└ **Now:** {rate:.1f} mm/h\n└ **Next 2h:** {expect}\n└ **Later:** {' | '.join(forecast24.get(cfg['region'], []))}"
        message_blocks.append(block)

    state_string = "|".join(current_state_list)
    should_send = force_push or (state_string != last_state)
    
    # Cooldown Logic
    if should_send and last_sent_time and not force_push:
        elapsed = (datetime.now() - last_sent_time).total_seconds() / 60
        if elapsed < COOLDOWN_MINUTES:
            should_send = False

    if should_send:
        msg = f"📊 *Weather Dashboard Update* ({timing})\n------------------------------------\n\n" + "\n\n".join(message_blocks)
        for cid in CHAT_IDS:
            if cid.strip():
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": cid.strip(), "text": msg, "parse_mode": "Markdown"})
        with open(DB_FILE, "w") as f: f.write(f"{datetime.now().isoformat()}:{state_string}")

if __name__ == "__main__":
    main()
