import discord
import os
import re
import time
import requests
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LINKS_FORUM_ID = 1498842238082351205

DRY_RUN = False
SLEEP_BETWEEN = 2

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def fetch_pmc_or_pubmed(url):
    pmcid = re.search(r'PMC(\d+)', url)
    pmid = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
    try:
        if pmcid:
            r = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params={"db": "pmc", "id": pmcid.group(1), "rettype": "abstract", "retmode": "text"},
                timeout=20, headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.ok and len(r.text.strip()) > 100:
                return r.text[:8000]
        if pmid:
            r = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params={"db": "pubmed", "id": pmid.group(1), "rettype": "abstract", "retmode": "text"},
                timeout=20, headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.ok and len(r.text.strip()) > 100:
                return r.text[:8000]
    except Exception:
        pass
    return ""


def fetch_crossref(url):
    doi = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', url, re.I)
    if not doi:
        return ""
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi.group(0)}",
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok:
            m = r.json().get("message", {})
            title = " ".join(m.get("title", []) or [])
            abstract = re.sub(r"<[^>]+>", "", m.get("abstract", "") or "")
            blob = (title + ". " + abstract).strip()
            if len(blob) > 60:
                return blob[:8000]
    except Exception:
        pass
    return ""


def fetch_page(url):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok:
            return r.text[:8000]
    except Exception:
        pass
    return ""


def get_content(url):
    return fetch_pmc_or_pubmed(url) or fetch_crossref(url) or fetch_page(url)


def summarize(url, context_text):
    content = get_content(url)
    prompt = f"""A member of a research community focused on severe anhedonia and reward dysfunction shared this link.

Posted text: {context_text}
URL: {url}
Page content (may be truncated or empty): {content}

Write a 2-4 sentence plain-language summary of what this source says. Describe the findings or content factually. Do NOT give medical advice, dosing, or tell anyone what to try -- just explain what the source reports.

If the page content is only a captcha, cookie notice, login wall, "verify you are human", or otherwise contains no actual article content, respond with exactly the single word: SKIP"""
    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    if text.upper().startswith("SKIP") or len(text) < 40:
        return None
    return text


async def already_summarized(thread):
    async for m in thread.history(limit=50, oldest_first=True):
        if m.author.id == client.user.id and m.embeds:
            title = m.embeds[0].title or ""
            if "Plain-Language Summary" in title:
                return True
    return False


async def first_url(thread):
    try:
        starter = await thread.fetch_message(thread.id)
    except Exception:
        starter = None
        async for m in thread.history(limit=1, oldest_first=True):
            starter = m
            break
    if not starter:
        return None, ""
    text = starter.content or ""
    urls = re.findall(r'https?://\S+', text)
    return (urls[0] if urls else None), text


async def post_summary(thread, summary):
    embed = discord.Embed(
        title="📝 Plain-Language Summary",
        description=summary,
        color=0x1ABC9C,
    )
    embed.set_footer(text="AI summary • factual only, not medical advice")
    await thread.send(embed=embed)


@client.event
async def on_ready():
    print(f"Connected as {client.user}")
    forum = client.get_channel(LINKS_FORUM_ID) or await client.fetch_channel(LINKS_FORUM_ID)
    threads = list(forum.threads)
    async for t in forum.archived_threads(limit=None):
        threads.append(t)

    seen_ids = set()
    filled = skipped_existing = skipped_inaccessible = skipped_nourl = errors = 0
    print(f"Found {len(threads)} threads in the links forum.\n")

    for thread in threads:
        if thread.id in seen_ids:
            continue
        seen_ids.add(thread.id)
        name = thread.name[:60]
        try:
            if await already_summarized(thread):
                skipped_existing += 1
                print(f"  = has summary       | {name}")
                continue
            url, text = await first_url(thread)
            if not url:
                skipped_nourl += 1
                print(f"  - no url            | {name}")
                continue
            summary = summarize(url, text)
            if summary is None:
                skipped_inaccessible += 1
                print(f"  x blocked/skipped   | {name}")
                continue
            if DRY_RUN:
                print(f"  ~ WOULD POST        | {name}")
                print(f"      -> {summary[:120]}...")
            else:
                await post_summary(thread, summary)
                print(f"  + filled            | {name}")
            filled += 1
        except Exception as e:
            errors += 1
            print(f"  ! error             | {name} :: {e}")
        time.sleep(SLEEP_BETWEEN)

    print("\n---------- backfill complete ----------")
    print(f"  filled (posted)        : {filled}{'  [DRY RUN]' if DRY_RUN else ''}")
    print(f"  skipped, had summary   : {skipped_existing}")
    print(f"  skipped, no url        : {skipped_nourl}")
    print(f"  skipped, inaccessible  : {skipped_inaccessible}")
    print(f"  errors                 : {errors}")
    await client.close()


if __name__ == "__main__":
    client.run(BOT_TOKEN)
