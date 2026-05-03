import requests
import os

# Get secrets from GitHub Actions environment
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TARGET_AREAS = ["Sembawang", "Yishun", "Novena"]

def run_weather_bot():
    # 1. Fetch 2-Hour Forecast
    url_2hr = "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast"
    res = requests.get(url_2hr).json()
    forecasts = res['data']['items'][0]['forecasts']
    
    # 2. Extract specific areas
    local_data = ""
    for f in forecasts:
        if f['area'] in TARGET_AREAS:
            local_data += f"• {f['area']}: {f['forecast']}\n"

    # 3. Fetch 24-Hour General
    url_24hr = "https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast"
    gen_res = requests.get(url_24hr).json()
    gen = gen_res['data']['items'][0]['general']

    # 4. Construct Message
    message = (
        f"🇸🇬 *Weather Update*\n\n"
        f"📍 *Local (2-Hr):*\n{local_data}\n"
        f"📅 *General (24-Hr):*\n{gen['forecast']}\n"
        f"🌡 {gen['temperature']['low']}°C - {gen['temperature']['high']}°C"
    )

    # 5. Push to Telegram
    tel_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(tel_url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    run_weather_bot()
