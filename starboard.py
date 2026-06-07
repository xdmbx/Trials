import discord
import os
import json
import re
import requests
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
STARBOARD_CHANNEL_ID = 1512326918584668242
LINKS_FORUM_ID = 1498842238082351205
STAR_EMOJI = "⭐"
SEEN_FILE = "starred.json"

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def load_starred():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_starred(starred):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(starred), f)

def get_pubmed_abstract(pmid):
    try:
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
        title = root.findtext(".//ArticleTitle", "")
        parts = root.findall(".//AbstractText")
        abstract = " ".join((p.text or "") for p in parts if p.text)
        return f"Title: {title}\nAbstract: {abstract}".strip()
    except Exception:
        return ""

def get_crossref_by_doi(doi):
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=15,
                         headers={"User-Agent": "ResearchBot/1.0"})
        r.raise_for_status()
        msg = r.json().get("message", {})
        title = (msg.get("title") or [""])[0]
        abstract = msg.get("abstract", "")
        abstract = re.sub(r"<[^>]+>", "", abstract)
        return f"Title: {title}\nAbstract: {abstract}".strip()
    except Exception:
        return ""

def extract_source_text(url):
    m = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
    if m:
        text = get_pubmed_abstract(m.group(1))
        if text:
            return text, "pubmed"
    m = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', url, re.I)
    if m:
        text = get_crossref_by_doi(m.group(1))
        if text:
            return text, "crossref"
    try:
        page = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if page.status_code == 200 and len(page.text) > 500:
            return page.text[:8000], "page"
    except Exception:
        pass
    return "", "none"

def write_summary(source_text, context_text="", url=""):
    prompt = f"""A member of a research community focused on severe anhedonia and reward dysfunction shared this source.

Posted text: {context_text}
URL: {url}
Source content: {source_text}

First, judge whether the "Source content" above is the actual article/study text. If it is instead a CAPTCHA page, a login or paywall wall, a cookie/consent notice, an error page, or otherwise does NOT contain the real article content, reply with EXACTLY this single token and nothing else:
SKIP

Otherwise, write a 2-4 sentence plain-language summary of what this source says. Describe the findings factually. Do NOT give medical advice, dosing, or tell anyone what to try — just explain what the source reports."""
    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text.strip()
    if text.upper().startswith("SKIP") or len(text) < 15:
        return None
    return text

def make_summary_embed(text):
    embed = discord.Embed(title="📝 Plain-Language Summary", description=text, color=0x1ABC9C)
    embed.set_footer(text="AI summary • factual only, not medical advice")
    return embed

@client.event
async def on_ready():
    print(f"Bot ready: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.startswith("!autosummary"):
        body = message.content[len("!autosummary"):].strip()
        if len(body) < 30:
            await message.channel.send("Paste the article text after the command: `!autosummary <abstract or article text>`", delete_after=10)
            return
        notice = await message.channel.send("Writing summary…")
        try:
            summary = write_summary(body)
            if summary is None:
                await notice.edit(content="Couldn't produce a summary from that text — it may not contain the actual article content.")
                return
            await notice.delete()
            await message.channel.send(embed=make_summary_embed(summary))
            try:
                await message.delete()
            except Exception:
                pass
        except Exception as e:
            await notice.edit(content=f"Error writing summary: {e}")

@client.event
async def on_thread_create(thread):
    if thread.parent_id != LINKS_FORUM_ID:
        return
    try:
        starter = await thread.fetch_message(thread.id)
    except Exception:
        starter = None
        async for m in thread.history(limit=1, oldest_first=True):
            starter = m
            break
        if starter is None:
            return
    text = starter.content or ""
    urls = re.findall(r'https?://\S+', text)
    if not urls:
        return
    source_text, method = extract_source_text(urls[0])
    if not source_text:
        print(f"Skipped (couldn't fetch): {thread.name}")
        return
    summary = write_summary(source_text, text, urls[0])
    if summary is None:
        print(f"Skipped (no accessible content): {thread.name}")
        return
    await thread.send(embed=make_summary_embed(summary))

@client.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != STAR_EMOJI:
        return
    if payload.channel_id == STARBOARD_CHANNEL_ID:
        return
    starred = load_starred()
    if payload.message_id in starred:
        return
    channel = client.get_channel(payload.channel_id) or await client.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    for reaction in message.reactions:
        if str(reaction.emoji) == STAR_EMOJI and reaction.count >= 1:
            starboard = client.get_channel(STARBOARD_CHANNEL_ID) or await client.fetch_channel(STARBOARD_CHANNEL_ID)
            if message.embeds:
                await starboard.send(f"⭐ {message.jump_url}", embed=message.embeds[0])
            else:
                embed = discord.Embed(description=message.content, color=0xFFD700, timestamp=message.created_at)
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                embed.add_field(name="Source", value=f"[Jump]({message.jump_url})")
                await starboard.send("⭐", embed=embed)
            starred.add(payload.message_id)
            save_starred(starred)
            break

client.run(BOT_TOKEN)
