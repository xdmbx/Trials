import discord
import os

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
LINKS_FORUM_ID = 1498842238082351205

# Phrases that signal a failed/low-value summary
FAIL_MARKERS = [
    "captcha", "could not access", "couldn't access", "unable to access",
    "limited info", "based on limited", "cannot access", "can't access",
    "no content", "unable to retrieve", "couldn't retrieve"
]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def check_and_delete(thread):
    deleted = 0
    try:
        async for msg in thread.history(limit=20):
            if msg.author != client.user or not msg.embeds:
                continue
            embed = msg.embeds[0]
            if "Plain-Language Summary" not in (embed.title or ""):
                continue
            desc = (embed.description or "").lower()
            if any(marker in desc for marker in FAIL_MARKERS):
                print(f"🗑️  Deleting weak summary in: {thread.name}")
                await msg.delete()
                deleted += 1
    except Exception as e:
        print(f"Error on {thread.name}: {e}")
    return deleted

@client.event
async def on_ready():
    print(f"Cleanup bot ready: {client.user}")
    forum = client.get_channel(LINKS_FORUM_ID)
    if not forum:
        print("Forum not found")
        await client.close()
        return

    total = 0
    for thread in forum.threads:
        total += await check_and_delete(thread)
    async for thread in forum.archived_threads(limit=None):
        total += await check_and_delete(thread)

    print(f"Done. Deleted {total} weak summaries.")
    await client.close()

client.run(BOT_TOKEN)
