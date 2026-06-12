import requests
import time
import json
import os
from datetime import datetime, timedelta
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHANNEL_ID = "1510647038977773640"

from conditions_list import CONDITIONS

DAYS_BACK = 3
SEEN_FILE = "seen_trials.json"
REJECTS_FILE = "filtered_out.json"
SCREEN_MODEL = "claude-opus-4-5"   # stronger than haiku for judgment; change here if needed

# Every search must ALSO hit one of these, so broad mechanism keywords
# stop pulling in the whole field.
ANCHOR = ('anhedonia OR reward OR "emotional blunting" OR motivation OR '
          'depression OR antidepressant OR mood OR psychiatric OR anxiety OR '
          'dysphoria OR dopamine OR serotonin OR glutamate OR GABA OR opioid OR '
          'neuroplasticity OR neuroinflammation OR cognition OR brain OR neural')

ALLOWED_COUNTRIES = {
    "United States", "United Kingdom", "Germany", "France", "Italy",
    "Spain", "Netherlands", "Belgium", "Sweden", "Denmark", "Norway",
    "Finland", "Switzerland", "Austria", "Poland"
}

_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

COMMUNITY_PROFILE = """This feed serves a community focused on the BRAIN and MIND -- specifically the neuroscience of anhedonia, reward, motivation, mood, emotional and cognitive blunting, and treatment-resistant or drug-injury states. Members track brain mechanisms (dopaminergic reward circuitry, glutamatergic AMPA/NMDA, opioid/kappa, GABA/neurosteroid, sigma-1, TAAR1, histaminergic, neuroplasticity/BDNF, neuroinflammation as it affects mood/reward, mitochondrial function in neurons) and brain-targeted interventions (MAOIs, dopamine agonists, ketamine/psychedelics/psychoplastogens, novel antidepressants, DBS, TMS/SAINT, BCI, vagus nerve stimulation, neurotrophic peptides). They also follow the drug-induced and persistent neuropsychiatric injury states: PSSD, PFS, antipsychotic-induced blunting, benzo withdrawal, post-psychedelic, and the brain/cognitive side of post-viral states. The defining feature of a relevant item is that its core is about the BRAIN, MIND, mood, reward, emotion, cognition, or a neural mechanism/treatment."""

def is_relevant(title, summary, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A clinical trial matched the keyword "{condition}". Decide whether it genuinely belongs in this feed.

Title: {title}
Summary: {summary}

POST (RELEVANT) if the item is centered on the brain or mind: reward/motivation/pleasure circuitry, mood, emotion, anhedonia, emotional or cognitive blunting, treatment-resistant depression, a neural mechanism (receptor pharmacology, neuroplasticity, neuroinflammation affecting mood/reward, brain mitochondrial function, neural circuits), a brain-targeted intervention (drugs, neuromodulation, BCI, psychoplastogens, peptides), or a drug-induced/persistent neuropsychiatric injury state. Preclinical, animal, and mechanism papers count if the core is the brain/mind. Examples of RELEVANT: sigma-1 or TAAR1 receptor pharmacology; dopamine reward-circuit studies; psychoplastogens and neuroplasticity; MAOIs or novel antidepressants; BCI/DBS/TMS for treatment-resistant depression; vagus-nerve effects on brain dopamine; brain-fog or anhedonia in post-viral states.

REJECT (IRRELEVANT) if the brain/mind is incidental or absent. This includes general physical-body, systemic, or peripheral papers EVEN IF they mention a keyword: general COVID-19 / long-COVID immunology or non-neurological symptoms, general autonomic/cardiovascular/metabolic/immune disease without a brain-mood-reward angle, oncology, cardiology, orthopedics, dentistry, infectious disease, general internal medicine, veterinary, agricultural, or device/engineering papers. A paper about a body system is only relevant if its core connects to brain reward, mood, emotion, or cognition. If the item is not fundamentally about the brain or mind, answer IRRELEVANT.

If you cannot state in one sentence how the CORE of this item bears on the brain/mind as described, answer IRRELEVANT. Reply with ONLY one word: RELEVANT or IRRELEVANT."""
    for attempt in range(2):
        try:
            msg = _ai.messages.create(
                model=SCREEN_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip().upper().startswith("RELEVANT")
        except Exception as e:
            print(f"Screen error (attempt {attempt+1}): {e}")
            time.sleep(3)
    print(f"Screen failed twice; SKIPPING '{title[:50]}' (fail-closed).")
    return False

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
        "filter.advanced": f"AREA[StudyFirstPostDate]RANGE[{min_date}, MAX]",
        "fields": "NCTId,BriefTitle,Condition,Phase,StudyType,OverallStatus,StartDate,BriefSummary,LeadSponsorName,LocationCountry",
        "pageSize": 20,
        "sort": "StudyFirstPostDate:desc",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("studies", [])
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
        "title": f"🧪 {title}",
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "color": 0x0057b7,
        "description": summary,
        "fields": [
            {"name": "🎯 Matched", "value": matched_condition.title(), "inline": True},
            {"name": "🆔 NCT", "value": nct_id, "inline": True},
            {"name": "📊 Phase", "value": phase, "inline": True},
            {"name": "📍 Status", "value": status, "inline": True},
            {"name": "🔬 Type", "value": study_type, "inline": True},
            {"name": "🏛️ Sponsor", "value": sponsor, "inline": True},
            {"name": "🌍 Countries", "value": country_str, "inline": False},
        ],
        "footer": {"text": "ClinicalTrials.gov • New Trial Alert"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
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
        for trial in fetch_trials(condition):
            s = trial.get("protocolSection", {})
            nct_id = s.get("identificationModule", {}).get("nctId")
            if not nct_id or nct_id in seen or nct_id in new_seen:
                continue
            locs = s.get("contactsLocationsModule", {}).get("locations", [])
            countries = set(l.get("country", "") for l in locs)
            if countries and not countries.intersection(ALLOWED_COUNTRIES):
                continue
            title = s.get("identificationModule", {}).get("briefTitle", "")
            summary = s.get("descriptionModule", {}).get("briefSummary", "")
            if not is_relevant(title, summary, condition):
                log_reject(nct_id, title, condition)
                new_seen.add(nct_id)
                continue
            post_to_discord(trial, condition)
            time.sleep(2)
            new_seen.add(nct_id)
            posted += 1
    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new trial(s).")

if __name__ == "__main__":
    run()
