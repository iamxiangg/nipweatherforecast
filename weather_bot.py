import requests
import os

# --- CONFIG ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
# Enter multiple IDs separated by commas in GitHub Secrets, e.g., "110089567,987654321"
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")
TARGET_AREAS = ["Sembawang", "Yishun", "Novena"]
DB_FILE = "last_weather.txt"

def get_weather():
    url_2hr = "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast"
    try:
        res = requests.get(url_2hr).json()
        forecasts = res['data']['items'][0]['forecasts']
        # Filter and sort to ensure the comparison string is consistent
        current = {f['area']: f['forecast'] for f in forecasts if f['area'] in TARGET_AREAS}
        status_str = "|".join([f"{k}:{v}" for k, v in sorted(current.items())])
        return current, status_str
    except:
        return None, None

def send_to_all(message):
    for cid in CHAT_IDS:
        if not cid.strip(): continue
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": cid.strip(), "text": message, "parse_mode": "Markdown"})

def main():
    current_data, status_string = get_weather()
    if not current_data: return

    # Check for state change
    last_status = ""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            last_status = f.read().strip()

    if status_string != last_status:
        # Construct message
        msg = "⚠️ *Weather Update (Change Detected)*\n\n"
        for area, forecast in current_data.items():
            msg += f"• {area}: {forecast}\n"
        
        send_to_all(msg)
        
        # Update the memory file
        with open(DB_FILE, "w") as f:
            f.write(status_string)
        print("Change detected. Pushed to all chats.")
    else:
        print("No change. Silent.")

if __name__ == "__main__":
    main()
