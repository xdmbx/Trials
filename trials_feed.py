import requests
import time
import json
import os
from datetime import datetime, timedelta
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHANNEL_ID = "1510647038977773640"

# --- paste your full CONDITIONS list here, unchanged ---
from conditions_list import CONDITIONS

DAYS_BACK = 1
SEEN_FILE = "seen_trials.json"
REJECTS_FILE = "filtered_out.json"

ALLOWED_COUNTRIES = {
    "United States", "United Kingdom", "Germany", "France", "Italy",
    "Spain", "Netherlands", "Belgium", "Sweden", "Denmark", "Norway",
    "Finland", "Switzerland", "Austria", "Poland"
}

_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

COMMUNITY_PROFILE = """A research community focused on severe, treatment-resistant anhedonia, reward dysfunction, emotional blunting, 'blank mind', and global non-response to psychoactive substances. Also relevant: dopamine/glutamate/opioid systems, neuroinflammation, neuroplasticity, depression mechanisms, novel antidepressants, neuromodulation, and adjacent neuroscience/pharmacology."""

def is_relevant(title, summary, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A clinical trial matched the keyword "{condition}". Decide if it's relevant enough to post.

Title: {title}
Summary: {summary}

Be LOOSE — anything about the brain, mental health, neuroscience, pharmacology, or adjacent mechanisms should pass. It does NOT have to be specifically about anhedonia; adjacent is fine. Only reject things CLEARLY unrelated (e.g. a cancer chemo trial, a dentistry study, an orthopedic device) that matched a keyword incidentally.

Reply with ONLY one word: RELEVANT or IRRELEVANT."""
    try:
        msg = _ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        return "IRRELEVANT" not in msg.content[0].text.strip().upper()
    except Exception as e:
        print(f"Screen error (defaulting to post): {e}")
        return True

def log_reject(nct_id, title, condition):
    rejects = []
    if os.path.exists(REJECTS_FILE):
        try:
            with open(REJECTS_FILE) as f:
                rejects = json.load(f)
        except Exception:
            rejects = []
    rejects.append({"nct_id": nct_id, "title": title, "condition": condition, "date": datetime.now().isoformat()})
    with open(REJECTS_FILE, "w") as f:
        json.dump(rejects, f, indent=2)

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def fetch_trials(condition):
    min_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": condition,
        "filter.advanced": f"AREA[StudyFirstPostDate]RANGE[{min_date}, MAX] AND AREA[LocationCountry](United States OR United Kingdom OR Germany OR France OR Italy OR Spain OR Netherlands OR Belgium OR Sweden OR Denmark OR Norway OR Finland OR Switzerland OR Austria OR Poland)",
        "fields": "NCTId,BriefTitle,Condition,Phase,StudyType,OverallStatus,StartDate,BriefSummary,LeadSponsorName,LocationCountry",
        "pageSize": 20,
        "sort": "StudyFirstPostDate:desc"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get("studies", [])
    except Exception as e:
        print(f"Error fetching '{condition}': {e}")
        return []

def post_to_discord(trial, matched_condition):
    s = trial.get("protocolSection", {})
    id_mod = s.get("identificationModule", {})
    status_mod = s.get("statusModule", {})
    desc_mod = s.get("descriptionModule", {})
    design_mod = s.get("designModule", {})
    sponsor_mod = s.get("sponsorCollaboratorsModule", {})
    contacts_mod = s.get("contactsLocationsModule", {})

    nct_id = id_mod.get("nctId", "N/A")
    title = id_mod.get("briefTitle", "No title")
    phase = ", ".join(design_mod.get("phases", ["Not specified"]))
    status = status_mod.get("overallStatus", "N/A")
    study_type = design_mod.get("studyType", "N/A")
    sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "N/A")
    summary = desc_mod.get("briefSummary", "No summary available.")
    if len(summary) > 350:
        summary = summary[:350].rsplit(" ", 1)[0] + "…"

    locations = contacts_mod.get("locations", [])
    countries = list(set(loc.get("country", "") for loc in locations if loc.get("country")))
    country_str = ", ".join(countries[:5]) if countries else "Not specified"

    embed = {
        "title": f"🔬 {title}",
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "color": 0x0057b7,
        "description": summary,
        "fields": [
            {"name": "🏷️ Matched Condition", "value": matched_condition.title(), "inline": True},
            {"name": "📋 NCT ID", "value": nct_id, "inline": True},
            {"name": "⚗️ Phase", "value": phase, "inline": True},
            {"name": "📊 Status", "value": status, "inline": True},
            {"name": "🔭 Study Type", "value": study_type, "inline": True},
            {"name": "🏢 Sponsor", "value": sponsor, "inline": True},
            {"name": "🌍 Countries", "value": country_str, "inline": False},
        ],
        "footer": {"text": "ClinicalTrials.gov • New Trial Alert"},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                          headers=headers, json={"embeds": [embed]}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Discord post failed for {nct_id}: {e}")

def run():
    seen = load_seen()
    posted = 0
    new_seen = set()

    for condition in CONDITIONS:
        print(f"Checking: {condition}")
        trials = fetch_trials(condition)
        for trial in trials:
            s = trial.get("protocolSection", {})
            nct_id = s.get("identificationModule", {}).get("nctId")
            if not nct_id or nct_id in seen or nct_id in new_seen:
                continue

            # Country safety filter (catches trials missing country data in API filter)
            locs = s.get("contactsLocationsModule", {}).get("locations", [])
            countries = set(l.get("country", "") for l in locs)
            if countries and not countries.intersection(ALLOWED_COUNTRIES):
                continue

            # AI relevance screen
            title = s.get("identificationModule", {}).get("briefTitle", "")
            summary = s.get("descriptionModule", {}).get("briefSummary", "")
            if not is_relevant(title, summary, condition):
                log_reject(nct_id, title, condition)
                new_seen.add(nct_id)  # mark seen so we don't re-screen daily
                continue

            post_to_discord(trial, condition)
            time.sleep(2)
            new_seen.add(nct_id)
            posted += 1

    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new trial(s).")

if __name__ == "__main__":
    run()
