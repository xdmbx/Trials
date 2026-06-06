import discord
import os
import json

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
STARBOARD_CHANNEL_ID = 1512326918584668242
STAR_EMOJI = "⭐"
SEEN_FILE = "starred.json"

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

def load_starred():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_starred(starred):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(starred), f)

@client.event
async def on_ready():
    print(f"Starboard bot ready: {client.user}")

@client.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != STAR_EMOJI:
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
