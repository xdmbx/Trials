import requests
import json
import os
from datetime import datetime, timedelta

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL_HERE")

CONDITIONS = [
    "anhedonia",
    "major depression",
    "treatment resistant depression",
    "treatment resistant anhedonia",
    "emotional blunting",
    "reward processing",
    "apathy",
    "depersonalization",
    "derealization",
    "cognitive dysfunction",
    "executive dysfunction",
    "purinergic",
]

DAYS_BACK = 1
SEEN_FILE = "seen_trials.json"

CONDITION_COLORS = {
    "anhedonia": 0x4A90D9,
    "major depression": 0x5B6EF5,
    "treatment resistant depression": 0x7B5EA7,
    "treatment resistant anhedonia": 0x9B59B6,
    "emotional blunting": 0x3498DB,
    "reward processing": 0x1ABC9C,
    "apathy": 0x95A5A6,
    "depersonalization": 0xE67E22,
    "derealization": 0xE74C3C,
    "cognitive dysfunction": 0x2ECC71,
    "executive dysfunction": 0x27AE60,
    "purinergic": 0xF39C12,
}

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
        "query.cond": condition,
        "filter.advanced": f"AREA[StudyFirstPostDate]RANGE[{min_date}, MAX]",
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

    # Countries
    locations = contacts_mod.get("locations", [])
    countries = list(set(loc.get("country", "") for loc in locations if loc.get("country")))
    country_str = ", ".join(countries[:5]) if countries else "Not specified"

    color = CONDITION_COLORS.get(matched_condition, 0x4A90D9)

    embed = {
        "title": f"🔬 {title}",
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "color": color,
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

    payload = {
        "username": "ClinicalTrials Bot",
        "avatar_url": "https://clinicaltrials.gov/favicon.ico",
        "embeds": [embed]
    }

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
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
            nct_id = trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            if not nct_id or nct_id in seen or nct_id in new_seen:
                continue  # Skip duplicates across conditions
            post_to_discord(trial, condition)
            new_seen.add(nct_id)
            posted += 1

    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new trial(s).")

if __name__ == "__main__":
    run()
