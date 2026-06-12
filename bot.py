import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import get_events
from tracker import is_guild_kill

# --- WEB-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "Бот активен!"
def run_server(): app.run(host='0.0.0.0', port=10000)
def keep_alive():
    t = Thread(target=run_server)
    t.start()

# --- НАСТРОЙКИ ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
KILL_CHANNEL = int(os.getenv("KILL_CHANNEL_ID"))
DEATH_CHANNEL = int(os.getenv("DEATH_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True # Нужно для команд
bot = commands.Bot(command_prefix="!", intents=intents)

# Хранилище последних событий
last_events = {"kill": None, "death": None}
processed = set()

# --- КОМАНДЫ ---
@bot.command()
async def status(ctx):
    await ctx.send(f"🤖 Бот отслеживает гильдию с ID: `{GUILD_ID}`")

@bot.command()
async def last(ctx):
    # Создаем эмбед для вывода последнего события
    for event_type, event in last_events.items():
        if not event:
            await ctx.send(f"Последнее событие '{event_type}' еще не было зафиксировано.")
            continue
        
        embed = discord.Embed(title=f"Последнее событие: {event_type.upper()}", color=0x8e44ad)
        embed.add_field(name="Killer", value=event.get("Killer", {}).get("Name", "Unknown"), inline=False)
        embed.add_field(name="Victim", value=event.get("Victim", {}).get("Name", "Unknown"), inline=False)
        embed.add_field(name="Fame", value=f"{event.get('TotalVictimKillFame', 0):,}", inline=False)
        await ctx.send(embed=embed)

# --- ЛОГИКА БОТА ---
async def monitor():
    await bot.wait_until_ready()
    kill_channel = bot.get_channel(KILL_CHANNEL)
    death_channel = bot.get_channel(DEATH_CHANNEL)

    while not bot.is_closed():
        try:
            events = await get_events()
            for event in events:
                event_id = event["EventId"]
                if event_id in processed: continue
                processed.add(event_id)
                
                result = is_guild_kill(event)
                if not result: continue

                # Сохраняем в память
                if result in last_events:
                    last_events[result] = event

                # (Код отправки Embed остался прежним)
                killer = event.get("Killer", {})
                victim = event.get("Victim", {})
                fame = event.get("TotalVictimKillFame", 0)
                embed = discord.Embed(color=0x8e44ad)
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
            print(f"Ошибка: {e}")
        await asyncio.sleep(20)

@bot.event
async def on_ready():
    print(f"Запущен как {bot.user}")
    bot.loop.create_task(monitor())

keep_alive()
bot.run(TOKEN)
