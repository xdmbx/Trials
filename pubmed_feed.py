import requests
import json
import os
from datetime import datetime
import xml.etree.ElementTree as ET
import time
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHANNEL_ID = "1510647038977773640"

from conditions_list import CONDITIONS

SEEN_FILE = "seen_pubmed.json"
REJECTS_FILE = "filtered_out_pubmed.json"

_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

COMMUNITY_PROFILE = """A research community focused on severe, treatment-resistant anhedonia, reward dysfunction, emotional blunting, 'blank mind', and global non-response to psychoactive substances. Also relevant: dopamine/glutamate/opioid systems, neuroinflammation, neuroplasticity, depression mechanisms, novel antidepressants, neuromodulation, and adjacent neuroscience/pharmacology."""

def is_relevant(title, abstract, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A PubMed paper matched the keyword "{condition}". Decide if it's relevant enough to post.

Title: {title}
Abstract: {abstract}

Be LOOSE — anything about the brain, mental health, neuroscience, pharmacology, or adjacent mechanisms should pass. It does NOT have to be specifically about anhedonia; adjacent is fine. Only reject things CLEARLY unrelated (e.g. an oncology paper, a dentistry study, an agricultural paper) that matched a keyword incidentally.

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

def log_reject(pmid, title, condition):
    rejects = []
    if os.path.exists(REJECTS_FILE):
        try:
            with open(REJECTS_FILE) as f:
                rejects = json.load(f)
        except Exception:
            rejects = []
    rejects.append({"pmid": pmid, "title": title, "condition": condition, "date": datetime.now().isoformat()})
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

def fetch_pubmed_ids(condition):
    time.sleep(1.0)
    today = datetime.now().strftime("%Y/%m/%d")
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{condition}[Title/Abstract]",
        "datetype": "edat",
        "mindate": today,
        "maxdate": today,
        "retmax": 10,
        "retmode": "json",
        "sort": "pub+date",
        "api_key": os.environ.get("PUBMED_API_KEY", ""),
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"Error searching '{condition}': {e}")
        return []

def fetch_paper_details(pmid):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
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
        if article is None:
            return None
        title = article.findtext(".//ArticleTitle", "No title").strip()
        authors = []
        for author in article.findall(".//Author")[:3]:
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last:
                authors.append(f"{fore} {last}".strip())
        author_str = ", ".join(authors)
        if len(article.findall(".//Author")) > 3:
            author_str += " et al."
        journal = article.findtext(".//Journal/Title", "Unknown Journal")
        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join((p.text or "") for p in abstract_parts if p.text)
        full_abstract = abstract  # keep full text for screening
        if len(abstract) > 350:
            abstract = abstract[:350].rsplit(" ", 1)[0] + "…"
        if not abstract:
            abstract = "No abstract available."
        pub_date = article.findtext(".//PubDate/Year", "")
        return {
            "title": title,
            "authors": author_str,
            "journal": journal,
            "abstract": abstract,
            "full_abstract": full_abstract,
            "pub_date": pub_date,
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def post_to_discord(pmid, paper, condition):
    embed = {
        "title": f"📄 {paper['title']}",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "color": 0x4A90D9,
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
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                          headers=headers, json={"embeds": [embed]}, timeout=10)
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

            # AI relevance screen
            if not is_relevant(paper["title"], paper.get("full_abstract", paper["abstract"]), condition):
                log_reject(pmid, paper["title"], condition)
                new_seen.add(pmid)
                continue

            post_to_discord(pmid, paper, condition)
            new_seen.add(pmid)
            posted += 1

    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new paper(s).")

if __name__ == "__main__":
    run()
