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

COMMUNITY_PROFILE = """This feed serves a specific community: people living with severe, usually treatment-resistant anhedonia and closely related states -- profound emotional blunting/numbing, 'blank mind' (loss of inner speech, mental imagery, and spontaneous thought), collapse of motivation/drive, and 'substance blockage' (psychoactive drugs producing little or no subjective effect). For most members the onset was a discrete injury or trigger: antipsychotics (quetiapine, olanzapine, risperidone, aripiprazole), SSRIs/SNRIs (PSSD-type states), finasteride (PFS), bupropion, benzodiazepine withdrawal or kindling, MDMA or classic psychedelics, long COVID / post-viral states, carbon-monoxide or other toxic exposures, melanocortin peptides, or chronic-stress crashes -- though some cases are gradual or lifelong. Members track the mechanisms thought to drive these states (dopaminergic reward signalling, glutamatergic AMPA/NMDA, opioid, GABAergic/neurosteroid, neuroinflammatory, neuroplasticity/BDNF-TrkB, mitochondrial/metabolic, gut-brain, HPA/autonomic) and the interventions they actually try or follow (MAOIs such as tranylcypromine and phenelzine, dopamine agonists like pramipexole, low-dose amisulpride, ketamine/esketamine/arketamine, AXS-05, ECT, deep brain stimulation, TMS/SAINT, tVNS, stellate ganglion block, plasmapheresis/IVIG, neurotrophic peptides such as semax, cerebrolysin, NSI-189 and MIF-1, low-dose naltrexone, methylene blue, and non-hallucinogenic psychoplastogens)."""

def is_relevant(title, abstract, condition):
    prompt = f"""{COMMUNITY_PROFILE}

A PubMed paper matched the keyword "{condition}". Decide whether it genuinely belongs in this community's feed.

Title: {title}
Abstract: {abstract}

POST (RELEVANT) only if you can state in one sentence how it bears on the community above -- i.e. it relates to: anhedonia or reward/motivation/pleasure processing; emotional blunting or blank mind; global non-response to psychoactive drugs; one of the drug-induced or persistent neuropsychiatric injury states listed (PSSD, PFS, antipsychotic-induced, benzo withdrawal/kindling, post-psychedelic/MDMA, post-viral/long-COVID, toxic exposure); treatment-resistant depression; one of the listed mechanisms acting on mood/reward/motivation/emotion/cognition; or one of the listed interventions. Preclinical work, animal models, mechanism papers, novel compounds and research chemicals all count if that connection is real.

REJECT (IRRELEVANT) if the keyword appears incidentally and you cannot state a real connection -- including oncology, cardiology, orthopedics/dentistry, general neurology/neurodegeneration or stroke with no mood/reward/cognition angle, metabolic or immune disease with no CNS-mood angle, veterinary/agricultural/plant work, devices/engineering, pure epidemiology with no mechanism or intervention tie, and studies about a different psychiatric condition (schizophrenia/psychosis, ADHD, autism, OCD, PTSD, eating disorders) UNLESS they bear on anhedonia, reward, emotional blunting, or one of the listed mechanisms or interventions.

If you cannot articulate the connection in one sentence, answer IRRELEVANT. Reply with ONLY one word: RELEVANT or IRRELEVANT."""
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
        full_abstract = abstract
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
