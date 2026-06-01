import requests
import json
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1510822077173862570/LwepZXHkvgHN5KjovuoRyquZkpUMVmLhTUC4DTLTFPMYf0kCl0mcQ834Mw24LTDih-U_")
PUBMED_API_KEY = os.environ.get("PUBMED_API_KEY", "")

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

SEEN_FILE = "seen_pubmed.json"

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

def fetch_pubmed_ids(condition):
    today = datetime.now().strftime("%Y/%m/%d")
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{condition}[Title/Abstract]",
        "datetype": "pdat",
        "mindate": today,
        "maxdate": today,
        "retmax": 10,
        "retmode": "json",
        "sort": "pub+date",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"Error searching '{condition}': {e}")
        return []

def fetch_paper_details(pmid):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
    }
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching PMID {pmid}: {e}")
        return None

def parse_paper(xml_text):
    try:
        root = ET.fromstring(xml_text)
        article = root.find(".//PubmedArticle")
        if not article:
            return None

        title = article.findtext(".//ArticleTitle", "No title").strip()

        # Authors
        authors = []
        for author in article.findall(".//Author")[:3]:
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last:
                authors.append(f"{fore} {last}".strip())
        author_str = ", ".join(authors)
        if len(article.findall(".//Author")) > 3:
            author_str += " et al."

        # Journal
        journal = article.findtext(".//Journal/Title", "Unknown Journal")

        # Abstract
        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(
            (p.text or "") for p in abstract_parts if p.text
        )
        if len(abstract) > 350:
            abstract = abstract[:350].rsplit(" ", 1)[0] + "…"
        if not abstract:
            abstract = "No abstract available."

        # Pub date
        pub_date = article.findtext(".//PubDate/Year", "")

        return {
            "title": title,
            "authors": author_str,
            "journal": journal,
            "abstract": abstract,
            "pub_date": pub_date,
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def post_to_discord(pmid, paper, condition):
    color = CONDITION_COLORS.get(condition, 0x4A90D9)
    embed = {
        "title": f"📄 {paper['title']}",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "color": color,
        "description": paper["abstract"],
        "fields": [
            {"name": "🏷️ Matched Condition", "value": condition.title(), "inline": True},
            {"name": "📅 Year", "value": paper["pub_date"], "inline": True},
            {"name": "📰 Journal", "value": paper["journal"], "inline": False},
            {"name": "👥 Authors", "value": paper["authors"] or "N/A", "inline": False},
        ],
        "footer": {"text": "PubMed • New Paper Alert"},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    payload = {
        "username": "PubMed Bot",
        "embeds": [embed]
    }
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Discord post failed for PMID {pmid}: {e}")

def run():
    seen = load_seen()
    new_seen = set()
    posted = 0

    for condition in CONDITIONS:
        print(f"Checking PubMed: {condition}")
        pmids = fetch_pubmed_ids(condition)
        for pmid in pmids:
            if pmid in seen or pmid in new_seen:
                continue
            xml_text = fetch_paper_details(pmid)
            if not xml_text:
                continue
            paper = parse_paper(xml_text)
            if not paper:
                continue
            post_to_discord(pmid, paper, condition)
            new_seen.add(pmid)
            posted += 1

    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new paper(s).")

if __name__ == "__main__":
    run()
