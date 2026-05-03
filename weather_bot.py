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

def get_data():
    try:
        # 1. Fetch Forecast
        res_f = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=15).json()
        
        # SAFE CHECK: Ensure data and items exist
        items_f = res_f.get('data', {}).get('items', [])
        if not items_f:
            print("Fetch Error: No forecast items found in API response.")
            return None, None, None
            
        item_f = items_f[0]
        update_time = item_f.get('update_timestamp', '00:00T00:00').split('T')[1][:5]
        forecast_list = {f['area']: f['forecast'] for f in item_f.get('forecasts', [])}

        # 2. Fetch Rainfall
        res_r = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=15).json()
        items_r = res_r.get('data', {}).get('items', [])
        
        if not items_r:
            print("Fetch Error: No rainfall items found in API response.")
            return None, None, None
            
        rainfall_list = {r['station_id']: r['value'] for r in items_r[0].get('readings', [])}

        return forecast_list, rainfall_list, update_time
    except Exception as e:
        print(f"Fetch Error: {str(e)}")
        return None, None, None

def main():
    forecasts, rain_sensors, timing = get_data()
    
    # If API fails, exit quietly without triggering a 'CHANGE_DETECTED'
    if forecasts is None:
        print("CHANGE_DETECTED=false")
        return

    current_expect_id = "|".join([f"{t}:{forecasts.get(t, 'N/A')}" for t in TOWNS])

    last_expect_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_expect_id = f.read().strip()

    if current_expect_id != last_expect_id:
        msg = f"📊 *Weather Change Alert* ({timing})\n"
        msg += "------------------------------------\n\n"
        for town, ids in TOWNS.items():
            expect = forecasts.get(town, "No Data")
            val = rain_sensors.get(ids['station'], 0.0)
            status = "☔ Raining" if val > 0 else "☁️ Dry"
            msg += f"🏠 *{town.upper()}*\n└ *Current:* {status} ({val}mm)\n└ *Expect:* {expect}\n\n"

        for cid in CHAT_IDS:
            if not cid.strip(): continue
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                          json={"chat_id": cid.strip(), "text": msg, "parse_mode": "Markdown"})
        
        with open(DB_FILE, "w") as f:
            f.write(current_expect_id)
        
        print("CHANGE_DETECTED=true")
    else:
        print("CHANGE_DETECTED=false")

if __name__ == "__main__":
    main()
