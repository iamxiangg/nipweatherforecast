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
        # 1. Forecast
        res_f = requests.get("https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast", timeout=10).json()
        item_f = res_f['data']['items'][0]
        update_time = item_f['update_timestamp'].split('T')[1][:5]
        forecast_list = {f['area']: f['forecast'] for f in item_f['forecasts']}

        # 2. Rainfall
        res_r = requests.get("https://api-open.data.gov.sg/v2/real-time/api/rainfall", timeout=10).json()
        rainfall_list = {r['station_id']: r['value'] for r in res_r['data']['items'][0]['readings']}

        return forecast_list, rainfall_list, update_time
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None, None, None

def main():
    forecasts, rain_sensors, timing = get_data()
    if not forecasts:
        sys.exit(0)

    current_expect_id = "|".join([f"{t}:{forecasts.get(t)}" for t in TOWNS])

    last_expect_id = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_expect_id = f.read().strip()

    if current_expect_id != last_expect_id:
        # Build and Send Telegram Message
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
        
        # Save memory
        with open(DB_FILE, "w") as f:
            f.write(current_expect_id)
        
        print("CHANGE_DETECTED=true") # Signal for GitHub Action
    else:
        print("CHANGE_DETECTED=false")

if __name__ == "__main__":
    main()
