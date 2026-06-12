import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from albion_api import get_events, get_guild_info

logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)
PROCESSED_EVENTS = set()

# Uptime-сервер
app = Flask('')
@app.route('/')
def home(): return "Бот активний"
Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()

@bot.command()
async def scanlive(ctx):
    """Сканування 20 останніх подій"""
    events = await get_events(limit=20)
    if not events:
        await ctx.send("❌ API не відповіло або подій немає.")
        return
    
    for event in events:
        killer = event.get('Killer', {}).get('Name', 'Unknown')
        victim = event.get('Victim', {}).get('Name', 'Unknown')
        embed = discord.Embed(title="⚔️ Подія", color=discord.Color.blue())
        embed.add_field(name="Вбивця", value=killer, inline=True)
        embed.add_field(name="Жертва", value=victim, inline=True)
        await ctx.send(embed=embed)

@bot.command()
async def checkapi(ctx):
    """Перевірка статусу"""
    events = await get_events(limit=1)
    if events:
        await ctx.send("🟢 API працює стабільно.")
    else:
        await ctx.send("🔴 API недоступне.")

@bot.command()
async def guild(ctx):
    """Статистика гільдії"""
    data = await get_guild_info(GUILD_ID)
    if data:
        await ctx.send(f"🏰 Гільдія: {data.get('Name')} | Учасників: {data.get('MemberCount')}")
    else:
        await ctx.send("❌ Не вдалося отримати дані.")

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} готовий до роботи!")

bot.run(TOKEN)
