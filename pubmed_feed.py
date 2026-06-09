import requests
import json
import os
from datetime import datetime
import xml.etree.ElementTree as ET
import time
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PUBMED_API_KEY = os.environ.get("PUBMED_API_KEY", "")
CHANNEL_ID = "1510647038977773640"

from conditions_list import CONDITIONS

SEEN_FILE = "seen_pubmed.json"
REJECTS_FILE = "filtered_out_pubmed.json"
SCREEN_MODEL = "claude-opus-4-5"

ANCHOR = ('anhedonia OR reward OR "emotional blunting" OR motivation OR '
          'depression OR antidepressant OR mood OR psychiatric OR anxiety OR dysphoria')

_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

COMMUNITY_PROFILE = """This feed serves a community of people with severe, usually treatment-resistant anhedonia and closely related states: profound emotional blunting/numbing, 'blank mind', collapse of motivation, and 'substance blockage' (drugs producing little or no effect). For most members onset was a discrete injury: antipsychotics, SSRIs/SNRIs (PSSD), finasteride (PFS), bupropion, benzodiazepine withdrawal/kindling, MDMA/psychedelics, long COVID/post-viral, toxic exposure, or chronic-stress crashes. Members track the mechanisms behind these states (dopaminergic reward, glutamatergic AMPA/NMDA, opioid, GABA/neurosteroid, neuroinflammatory, neuroplasticity, mitochondrial/metabolic, gut-brain, HPA/autonomic) and the interventions they follow (MAOIs, dopamine agonists, ketamine/esketamine, AXS-05, ECT, DBS, TMS/SAINT, tVNS, plasmapheresis/IVIG, neurotrophic peptides, low-dose naltrexone, psychoplastogens)."""

def is_relevant(title, abstract, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A PubMed paper matched the keyword "{condition}". Decide whether it genuinely belongs in this feed.

Title: {title}
Abstract: {abstract}

POST (RELEVANT) only if you can state in one sentence how it bears on the community above: anhedonia, reward/motivation/pleasure, emotional blunting, treatment-resistant depression, one of the drug-induced or post-viral injury states, or one of the listed mechanisms/interventions acting on mood/reward/emotion/cognition. Preclinical and mechanism studies count if that link is real.

REJECT (IRRELEVANT) if the keyword is incidental with no mood/reward/brain angle: oncology, cardiology, orthopedics/dentistry, general neurology/stroke/neurodegeneration with no mood angle, metabolic/immune disease with no CNS-mood angle, veterinary/agricultural/plant work, or a different psychiatric condition with no anhedonia/reward/blunting tie.

If you cannot articulate the connection in one sentence, answer IRRELEVANT. Reply with ONLY one word: RELEVANT or IRRELEVANT."""
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
    time.sleep(0.5)
    today = datetime.now().strftime("%Y/%m/%d")
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"({condition}[Title/Abstract]) AND ({ANCHOR})",
        "datetype": "edat",
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
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
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
        if article is None:
            return None
        title = (article.findtext(".//ArticleTitle") or "No title").strip()
        authors = []
        for a in article.findall(".//Author")[:3]:
            last = a.findtext("LastName", "")
            fore = a.findtext("ForeName", "")
            if last:
                authors.append(f"{fore} {last}".strip())
        author_str = ", ".join(authors)
        if len(article.findall(".//Author")) > 3:
            author_str += " et al."
        journal = article.findtext(".//Journal/Title", "Unknown Journal")
        abstract_parts = article.findall(".//AbstractText")
        full_abstract = " ".join((p.text or "") for p in abstract_parts if p.text)
        year = article.findtext(".//PubDate/Year", "")
        return {
            "title": title,
            "authors": author_str or "N/A",
            "journal": journal,
            "year": year,
            "full_abstract": full_abstract,
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def post_to_discord(paper, pmid, matched_condition):
    abstract = paper["full_abstract"] or "No abstract available."
    if len(abstract) > 350:
        abstract = abstract[:350].rsplit(" ", 1)[0] + "…"
    embed = {
        "title": f"📄 {paper['title']}",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "color": 0x6f42c1,
        "description": abstract,
        "fields": [
            {"name": "🎯 Matched", "value": matched_condition.title(), "inline": True},
            {"name": "🆔 PMID", "value": pmid, "inline": True},
            {"name": "📅 Year", "value": paper["year"] or "N/A", "inline": True},
            {"name": "✍️ Authors", "value": paper["authors"], "inline": False},
            {"name": "📚 Journal", "value": paper["journal"], "inline": False},
        ],
        "footer": {"text": "PubMed • New Paper Alert"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
                          headers=headers, json={"embeds": [embed]}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Discord post failed for {pmid}: {e}")

def run():
    seen = load_seen()
    posted = 0
    new_seen = set()
    for condition in CONDITIONS:
        print(f"Checking: {condition}")
        for pmid in fetch_pubmed_ids(condition):
            if pmid in seen or pmid in new_seen:
                continue
            xml_text = fetch_paper_details(pmid)
            if not xml_text:
                continue
            paper = parse_paper(xml_text)
            if not paper:
                new_seen.add(pmid)
                continue
            if not is_relevant(paper["title"], paper["full_abstract"], condition):
                log_reject(pmid, paper["title"], condition)
                new_seen.add(pmid)
                continue
            post_to_discord(paper, pmid, condition)
            time.sleep(2)
            new_seen.add(pmid)
            posted += 1
    save_seen(seen | new_seen)
    print(f"Done. Posted {posted} new paper(s).")

if __name__ == "__main__":
    run()
