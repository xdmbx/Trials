import requests
import json
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_WEBHOOK_URL_HERE")
PUBMED_API_KEY = os.environ.get("PUBMED_API_KEY", "")



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
