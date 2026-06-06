import discord
import os
import re
import requests
import anthropic

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LINKS_FORUM_ID = 1498842238082351205

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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

Write a 2-4 sentence plain-language summary of what this source says. Describe the findings or content factually. Do NOT give medical advice, dosing, or tell anyone what to try — just explain what the source reports."""
    msg = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

async def process_thread(thread):
    try:
        starter = await thread.fetch_message(thread.id)
        text = starter.content or ""
        urls = re.findall(r'https?://\S+', text)
        if not urls:
            return False
        async for msg in thread.history(limit=10):
            if msg.author == client.user and msg.embeds and "Plain-Language Summary" in (msg.embeds[0].title or ""):
                print(f"⏭️  {thread.name} — already has summary")
                return False
        print(f"📝 Summarizing: {thread.name}")
        summary = summarize(urls[0], text)
        embed = discord.Embed(title="📝 Plain-Language Summary", description=summary, color=0x1ABC9C)
        embed.set_footer(text="AI summary • factual only, not medical advice")
        await thread.send(embed=embed)
        return True
    except Exception as e:
        print(f"Error on {thread.name}: {e}")
        return False

@client.event
async def on_ready():
    print(f"Backfill bot ready: {client.user}")
    forum = client.get_channel(LINKS_FORUM_ID)
    if not forum:
        print(f"Forum {LINKS_FORUM_ID} not found")
        await client.close()
        return

    count = 0
    # Active threads
    for thread in forum.threads:
        if await process_thread(thread):
            count += 1
    # Archived threads
    async for thread in forum.archived_threads(limit=None):
        if await process_thread(thread):
            count += 1

    print(f"Done. Added {count} summaries.")
    await client.close()

client.run(BOT_TOKEN)
