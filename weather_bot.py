import requests
import os
import sys

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
DB_FILE = "last_weather.txt"

TOWNS = {
    "Sembawang": {"station": "S104"},
    "Yishun": {"station": "S122"},
    "Novena": {"station": "S111"}
}

def send_telegram(text):
    for cid in CHAT_IDS:
        cid = cid.strip()
        if not cid: continue
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": cid, "text": text, "parse_mode": "Markdown"})

def get_data():
    try:
        # 1. Fetch Forecast
        rf = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15)
        if rf.status_code != 200: raise Exception(f"Forecast API Status {rf.status_code}")
        
        items_f = rf.json().get('data', {}).get('items', [])
        if not items_f: return None, None, None # No data case
            
        item_f = items_f[0]
        update_time = item_f.get('update_timestamp', 'T00:00').split('T')[1][:5]
        forecast_list = {f['area']: f['forecast'] for f in item_f.get('forecasts', [])}

        # 2. Fetch Rainfall
        rr = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15)
        if rr.status_code != 200: raise Exception(f"Rainfall API Status {rr.status_code}")
        
        items_r = rr.json().get('data', {}).get('items', [])
        rainfall_list = {r['station_id']: r['value'] for r in items_r[0].get('readings', [])} if items_r else {}

        return forecast_list, rainfall_list, update_time
    except Exception as e:
        # Send system alert only once per failure period
        send_telegram(f"⚠️ *System Alert:* Weather API is currently unreachable.\nError: `{str(e)}`")
        return "ERROR", None, None

def main():
    forecasts, rain_sensors, timing = get_data()
    
    if forecasts == "ERROR":
        print("CHANGE_DETECTED=false") # Don't update memory on error
        return
    
    if not forecasts:
        print("No new data available. Skipping.")
        print("CHANGE_DETECTED=false")
        return

    # Create memory string: if a town is missing from API, we use 'N/A'
    # This prevents the bot from thinking a missing town = a change.
    current_expect_id = "|".join([f"{t}:{forecasts.get(t, 'N/A')}" for t in TOWNS])

    last_expect_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_expect_id = f.read().strip()

    if current_expect_id != last_expect_id:
        msg = f"📊 *Weather Forecast Change* ({timing})\n"
        msg += "------------------------------------\n\n"
        
        for town, ids in TOWNS.items():
            expect = forecasts.get(town)
            if not expect: continue # Skip towns missing from this specific API pull
            
            val = rain_sensors.get(ids['station'], 0.0)
            status = "☔ Raining" if val > 0 else "☁️ Dry"
            msg += f"🏠 *{town.upper()}*\n└ *Current:* {status} ({val}mm)\n└ *Expect:* {expect}\n\n"

        send_telegram(msg)
        
        with open(DB_FILE, "w") as f:
            f.write(current_expect_id)
        print("CHANGE_DETECTED=true")
    else:
        print("CHANGE_DETECTED=false")

if __name__ == "__main__":
    main()
