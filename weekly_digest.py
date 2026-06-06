import os
import requests
from datetime import datetime, timedelta, timezone
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TRIALS_CHANNEL_ID = "1510647038977773640"
GENERAL_CHANNEL_ID = "1498837630035558553"

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

def fetch_week_messages():
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    messages = []
    last_id = None
    while True:
        params = {"limit": 100}
        if last_id:
            params["before"] = last_id
        r = requests.get(f"https://discord.com/api/v10/channels/{TRIALS_CHANNEL_ID}/messages", headers=headers, params=params)
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        for msg in batch:
            msg_time = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            if msg_time >= cutoff and msg.get("embeds"):
                for embed in msg["embeds"]:
                    entry = {"title": embed.get("title", ""), "description": embed.get("description", "")}
                    for field in embed.get("fields", []):
                        entry[field["name"]] = field["value"]
                    messages.append(entry)
        last_msg_time = datetime.fromisoformat(batch[-1]["timestamp"].replace("Z", "+00:00"))
        if last_msg_time < cutoff:
            break
        last_id = batch[-1]["id"]
    return messages

def generate_digest(entries):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    entries_text = "\n\n".join([
        f"Title: {e.get('title', '')}\nSummary: {e.get('description', '')}\nCondition: {e.get('🏷️ Matched Condition', '')}\nPhase: {e.get('⚗️ Phase', '')}\nStatus: {e.get('📊 Status', '')}\nCountries: {e.get('🌍 Countries', '')}"
        for e in entries
    ])
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""You are writing a weekly digest for a Discord community focused on severe anhedonia, reward dysfunction, and related neurological conditions. Members have treatment-resistant presentations and follow research closely.

Here are this week's clinical trials and studies:

{entries_text}

Write a compelling, warm but scientifically grounded weekly digest. Include:
- A brief intro for the week
- The most relevant/exciting findings and why they matter for this community specifically
- Any notable patterns across multiple trials (e.g. multiple ketamine trials, immune-focused research, etc.)
- A closing note of encouragement

Keep it under 1800 characters total. Use plain language where possible but don't oversimplify."""
        }]
    )
    return message.content[0].text

def post_digest(text):
    week_str = datetime.now().strftime("%B %d, %Y")
    embed = {
        "title": f"📋 Weekly Research Digest — {week_str}",
        "description": text,
        "color": 0x4A90D9,
        "footer": {"text": "Compiled weekly from ClinicalTrials.gov & PubMed"}
    }
    requests.post(
        f"https://discord.com/api/v10/channels/{GENERAL_CHANNEL_ID}/messages",
        headers=headers,
        json={"embeds": [embed]}
    )
    print("Digest posted.")

if __name__ == "__main__":
    print("Fetching this week's trials...")
    entries = fetch_week_messages()
    print(f"Found {len(entries)} entries")
    if not entries:
        print("No entries this week, skipping digest.")
    else:
        digest = generate_digest(entries)
        post_digest(digest)
