def main():
    # Check if --force is passed in the command line
    force_push = "--force" in sys.argv
    
    nowcast, rain, timing, forecast24 = get_data()
    if nowcast == "ERROR" or not nowcast: 
        print("CHANGE_DETECTED=false")
        return

    current_state_list = []
    message_blocks = []

    for town, cfg in TOWNS.items():
        expect = nowcast.get(cfg['area'], "No Data")
        status_label, rate = get_status_label(rain.get(cfg['station'], 0.0))
        current_state_list.append(f"{town}:{status_label}:{expect}")
        
        block = f"🏠 *{town.upper()}* ({cfg['region'].capitalize()})\n"
        block += f"└ *Current:* {status_label} ({rate:.1f} mm/h)\n"
        block += f"└ *Expect:* {expect}\n"
        block += f"└ *24h Forecast:*\n"
        for line in forecast24.get(cfg['region'], []):
            block += f"   • {line}\n"
        message_blocks.append(block)

    state_string = "|".join(current_state_list)
    last_state = open(DB_FILE, "r").read().strip() if os.path.exists(DB_FILE) else ""

    # Logic: Send if weather changed OR if it's the forced 07:30 morning push
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
