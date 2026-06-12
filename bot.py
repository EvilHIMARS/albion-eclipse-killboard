import os
import asyncio
import discord
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import get_events
from tracker import is_guild_kill

# --- НАСТРОЙКА WEB-СЕРВЕРА ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Бот активен!"

def run_server():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_server)
    t.start()
# ----------------------------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
KILL_CHANNEL = int(os.getenv("KILL_CHANNEL_ID"))
DEATH_CHANNEL = int(os.getenv("DEATH_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)
processed = set()

async def monitor():
    await client.wait_until_ready()
    kill_channel = client.get_channel(KILL_CHANNEL)
    death_channel = client.get_channel(DEATH_CHANNEL)

    while not client.is_closed():
        try:
            events = await get_events()
            for event in events:
                event_id = event["EventId"]
                if event_id in processed:
                    continue
                processed.add(event_id)
                
                result = is_guild_kill(event)
                if not result:
                    continue

                killer = event.get("Killer", {})
                victim = event.get("Victim", {})
                fame = event.get("TotalVictimKillFame", 0)

                embed = discord.Embed(color=0x8e44ad)
                embed.set_author(name="ECLIPSE Killboard")
                embed.add_field(name="Killer", value=killer.get("Name", "Unknown"), inline=False)
                embed.add_field(name="Victim", value=victim.get("Name", "Unknown"), inline=False)
                embed.add_field(name="Fame", value=f"{fame:,}", inline=False)

                if result == "kill":
                    embed.title = "☠️ УБИЙСТВО"
                    await kill_channel.send(embed=embed)
                elif result == "death":
                    embed.title = "💀 СМЕРТЬ"
                    await death_channel.send(embed=embed)
                elif result == "assist":
                    embed.title = "🤝 АССИСТ"
                    await kill_channel.send(embed=embed)
        except Exception as e:
            print(f"Ошибка мониторинга: {e}")
        await asyncio.sleep(20)

@client.event
async def on_ready():
    print(f"Запущен как {client.user}")
    asyncio.create_task(monitor())

# Запуск веб-сервера перед ботом
keep_alive()
client.run(TOKEN)
