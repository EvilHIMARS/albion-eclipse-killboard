import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from albion_api import get_events

# Налаштування логування
logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# WEB-сервер для Uptime (щоб Render не "засинав")
app = Flask('')
@app.route('/')
def home(): return "Бот працює!"
def run_server(): app.run(host='0.0.0.0', port=10000)
Thread(target=run_server, daemon=True).start()

@bot.command()
async def scanlive(ctx):
    """Повноцінне сканування з гарним оформленням"""
    await ctx.send("🔍 Починаю глибоке сканування API Альбіону...")
    
    events = await get_events(limit=20)
    if not events:
        await ctx.send("❌ Не вдалося отримати дані від API.")
        return

    count = 0
    for event in events:
        # Створюємо Embed-картку для кожного бою
        killer = event.get('Killer', {})
        victim = event.get('Victim', {})
        
        embed = discord.Embed(
            title="⚔️ Нова подія в Альбіоні",
            color=discord.Color.red(),
            description=f"**Вбивця:** {killer.get('Name')}\n**Жертва:** {victim.get('Name')}"
        )
        embed.add_field(name="Слава", value=f"{event.get('TotalVictimKillFame', 0):,}", inline=True)
        
        await ctx.send(embed=embed)
        count += 1
        if count >= 3: break # Показуємо перші 3, щоб не спамити

@bot.event
async def on_ready():
    print(f"✅ xECLIPSEx авторизовано як {bot.user}")

bot.run(TOKEN)
