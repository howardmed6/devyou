import json
import requests
from datetime import datetime

def send_notification(message):
    try:
        bot_token = "7869024150:AAGFO6ZvpO4-5J4karX_lef252tkD3BhclE"
        chat_id = "6166225652"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(url, {"chat_id": chat_id, "text": message}, timeout=5)
    except:
        pass

def update_status(): 
    try:
        with open("data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        return
    
    updated = 0
    for video in data:
        if video['status'] == 'pending':
            video['status'] = 'metadata_update'
            updated += 1
    
    if updated > 0:
        send_notification(f"Cambiados {updated}: pending -> downloaded")
    
    with open("data.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    update_status()