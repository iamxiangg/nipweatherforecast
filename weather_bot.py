def main():
    force_push = "--force" in sys.argv
    nowcast, rain, timing, forecast24 = get_data()
    if nowcast == "ERROR" or not nowcast: 
        print("CHANGE_DETECTED=false")
        return

    current_state_list = []
    message_blocks = []
    
    # Load previous state to compare specific fields
    last_state = open(DB_FILE, "r").read().strip() if os.path.exists(DB_FILE) else ""
    # Create a dictionary of {Town: "Category:Expect"}
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
        
        # Comparison logic for Bold/Italics
        prev = last_map.get(town, {"cat": "", "exp": ""})
        
        # If the category changed, bold/italicize the label
        display_status = f"***{status_label}***" if status_label != prev['cat'] and last_state else status_label
        # If the expectation changed, bold/italicize the expect text
        display_expect = f"***{expect}***" if expect != prev['exp'] and last_state else expect

        block = f"🏠 *{town.upper()}* ({cfg['region'].capitalize()})\n"
        block += f"└ *Current:* {display_status} ({rate:.1f} mm/h)\n"
        block += f"└ *Expect:* {display_expect}\n"
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
