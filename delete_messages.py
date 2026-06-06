import os
import requests
import time
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = "1510647038977773640"

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

cutoff = datetime.now(timezone.utc) - timedelta(hours=3)

def get_messages():
    messages = []
    last_id = None
    while True:
        params = {"limit": 100}
        if last_id:
            params["before"] = last_id
        r = requests.get(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages", headers=headers, params=params)
        batch = r.json()
        if not isinstance(batch, list):
            print(f"API error: {batch}")
            break
        if not batch:
            break
        for msg in batch:
            msg_time = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            if msg_time >= cutoff:
                messages.append(msg["id"])
        if datetime.fromisoformat(batch[-1]["timestamp"].replace("Z", "+00:00")) < cutoff:
            break
        last_id = batch[-1]["id"]
    return messages

while True:
    message_ids = get_messages()
    if not message_ids:
        print("Done!")
        break
    print(f"Found {len(message_ids)} messages to delete")
    for i in range(0, len(message_ids), 100):
        chunk = message_ids[i:i+100]
        r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages/bulk-delete", headers=headers, json={"messages": chunk})
        if r.status_code == 429:
            retry = r.json().get("retry_after", 2)
            print(f"Rate limited, waiting {retry}s")
            time.sleep(retry + 0.5)
        else:
            print(f"Deleted chunk: {r.status_code}")
            time.sleep(1)
