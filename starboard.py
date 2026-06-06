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

def summarize(url, context_text):
    try:
        page = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        content = page.text[:8000]
    except Exception:
        content = ""

    prompt = f"""A member of a research community focused on severe anhedonia and reward dysfunction shared this link.

Posted text: {context_text}
URL: {url}
Page content (may be truncated or empty): {content}

Write a 2-4 sentence plain-language summary of what this source says. Describe the findings or content factually. Do NOT give medical advice, dosing, or tell anyone what to try — just explain what the source reports. If the page content is empty, summarize based on the URL and posted text as best you can, and note it's based on limited info."""

    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

@client.event
async def on_ready():
    print(f"Bot ready: {client.user}")

@client.event
async def on_thread_create(thread):
    if thread.parent_id != LINKS_FORUM_ID:
        return
    try:
        starter = await thread.fetch_message(thread.id)
    except Exception:
        async for m in thread.history(limit=1, oldest_first=True):
            starter = m
            break
        else:
            return

    text = starter.content or ""
    urls = re.findall(r'https?://\S+', text)
    if not urls:
        return

    summary = summarize(urls[0], text)
    embed = discord.Embed(
        title="📝 Plain-Language Summary",
        description=summary,
        color=0x1ABC9C
    )
    embed.set_footer(text="AI summary • factual only, not medical advice")
    await thread.send(embed=embed)

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
