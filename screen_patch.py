import anthropic
import os
import json
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REJECTS_FILE = "filtered_out.json"
_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

COMMUNITY_PROFILE = """A research community focused on severe, treatment-resistant anhedonia, reward dysfunction, emotional blunting, 'blank mind', and global non-response to psychoactive substances. Also relevant: dopamine/glutamate/opioid systems, neuroinflammation, neuroplasticity, depression mechanisms, novel antidepressants, neuromodulation, and related neuroscience/pharmacology."""

def is_relevant(title, summary, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A clinical trial was matched on the keyword "{condition}". Decide if it's relevant enough to post.

Title: {title}
Summary: {summary}

Be LOOSE — anything about the brain, mental health, neuroscience, pharmacology, or adjacent mechanisms should pass. Only reject things that are CLEARLY unrelated (e.g. a cancer drug trial that happened to match a keyword incidentally, a dentistry study, etc).

Reply with ONLY one word: RELEVANT or IRRELEVANT."""
    try:
        msg = _ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = msg.content[0].text.strip().upper()
        return "IRRELEVANT" not in answer
    except Exception as e:
        print(f"Screen error (defaulting to post): {e}")
        return True  # On error, post it rather than lose it

def log_reject(nct_id, title, condition):
    rejects = []
    if os.path.exists(REJECTS_FILE):
        with open(REJECTS_FILE) as f:
            rejects = json.load(f)
    rejects.append({"nct_id": nct_id, "title": title, "condition": condition, "date": datetime.now().isoformat()})
    with open(REJECTS_FILE, "w") as f:
        json.dump(rejects, f, indent=2)
