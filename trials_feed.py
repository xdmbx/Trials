import requests
import json
import os
from datetime import datetime, timedelta

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL_HERE")

CONDITIONS = [
    # Core Symptoms
    "anhedonia",
    "emotional blunting",
    "emotional numbness",
    "affective flattening",
    "reward deficiency",
    "motivational deficits",
    "dopamine dysfunction",
    "hedonic tone",
    "sexual dysfunction",
    "erectile dysfunction",
    "penile numbness",
    "sensory loss",
    "persistent sexual dysfunction",
    "post-SSRI sexual dysfunction",
    "PSSD",
    "cognitive impairment",
    "brain fog",
    "executive dysfunction",
    "apathy",
    "depersonalization",
    "derealization",
    "treatment-resistant symptoms",
    # Drug Injury / Withdrawal
    "antipsychotic withdrawal",
    "dopamine supersensitivity",
    "dopamine receptor regulation",
    "D2 receptor",
    "D3 receptor",
    "receptor occupancy",
    "post-antipsychotic syndrome",
    "tardive dysphoria",
    "persistent adverse effects",
    "long-term antipsychotic effects",
    "quetiapine",
    "stimulant neurotoxicity",
    "amphetamine neurotoxicity",
    "drug-induced sexual dysfunction",
    # Dopamine Restoration
    "dopamine agonist",
    "dopaminergic signaling",
    "mesolimbic dopamine",
    "ventral tegmental area",
    "nucleus accumbens",
    "dopamine transporter",
    "DAT",
    "D2 agonist",
    "D3 agonist",
    "bromocriptine",
    "cabergoline",
    "pramipexole",
    "ropinirole",
    "rotigotine",
    "selegiline",
    "rasagiline",
    "MAO-B inhibition",
    "catecholamine restoration",
    "reward circuitry",
    # Neuroplasticity
    "neuroplasticity",
    "synaptic plasticity",
    "structural plasticity",
    "synaptogenesis",
    "neurogenesis",
    "dendritic spine density",
    "experience-dependent plasticity",
    "plasticity enhancement",
    "cortical plasticity",
    "network plasticity",
    "functional connectivity",
    # BDNF / TrkB
    "BDNF",
    "brain-derived neurotrophic factor",
    "TrkB",
    "tropomyosin receptor kinase B",
    "neurotrophin signaling",
    "TrkB agonist",
    "7,8-DHF",
    "deoxygedunin",
    "ACD856",
    "neurotrophic factors",
    "neurorestoration",
    # Glutamate
    "NMDA receptor",
    "AMPA receptor",
    "AMPA potentiator",
    "AMPAkine",
    "TAK-653",
    "ketamine",
    "esketamine",
    "rapastinel",
    "apimostinel",
    "glutamatergic dysfunction",
    "synaptic rescue",
    "mTOR signaling",
    "mTORC1",
    "rapid antidepressant",
    # Neuroinflammation
    "neuroinflammation",
    "microglia",
    "microglial activation",
    "astrocytes",
    "cytokines",
    "TNF-alpha",
    "IL-1beta",
    "IL-6",
    "neuroimmune signaling",
    "neuroimmune modulation",
    "chronic inflammation",
    "central nervous system inflammation",
    "neurodegeneration",
    # Cell Danger Response
    "cell danger response",
    "purinergic signaling",
    "ATP signaling",
    "extracellular ATP",
    "P2X7 receptor",
    "P2X4 receptor",
    "suramin",
    "mitochondrial signaling",
    "metabolic dysfunction",
    # Mitochondria
    "mitochondrial dysfunction",
    "mitochondrial biogenesis",
    "bioenergetics",
    "oxidative stress",
    "ATP production",
    "mitophagy",
    "electron transport chain",
    "redox signaling",
    "NAD+",
    "mitochondrial medicine",
    # Blood-Brain Barrier
    "blood-brain barrier",
    "BBB permeability",
    "neurovascular unit",
    "endothelial dysfunction",
    "BBB disruption",
    "tight junctions",
    "neurovascular inflammation",
    # Psychedelics
    "psilocybin",
    "psilocin",
    "LSD",
    "DMT",
    "mescaline",
    "psychedelic-assisted therapy",
    "psychedelic neurobiology",
    "mystical experience",
    "default mode network",
    "network reset",
    # Experimental Compounds
    "9-ME-BC",
    "NSI-189",
    "cerebrolysin",
    "semax",
    "selank",
    "bromantane",
    "mexidol",
    "dihexa",
    "ISRIB",
    "BPC-157",
    "JNJ-55308942",
    "GLYX-13",
    "tropisetron",
    # Brain Stimulation
    "SAINT",
    "TMS",
    "rTMS",
    "deep TMS",
    "theta burst stimulation",
    "vagus nerve stimulation",
    "tDCS",
    "neuromodulation",
    "ECT",
    # Imaging / Biomarkers
    "functional MRI",
    "resting state fMRI",
    "PET imaging",
    "dopamine PET",
    "D2 receptor availability",
    "connectome",
    "reward network",
    "salience network",
    "biomarkers",
    "precision psychiatry",
    # Overlapping Diagnoses
    "major depressive disorder",
    "treatment-resistant depression",
    "parkinson's disease",
    "schizophrenia",
    "post-SSRI sexual dysfunction",
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
        "avatar_url": "https://cdn.discordapp.com/attachments/1511181435522908260/1511181812578128083/IMG_0076.png?ex=6a1f853c&is=6a1e33bc&hm=49e9e38c8f78682dd0e5118f7c4b013bb272f3aa6a5463f2ba2cb07929eb6484&",
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
