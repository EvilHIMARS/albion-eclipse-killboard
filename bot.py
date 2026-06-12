import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import get_events, get_guild_info
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
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# Удаляем стандартный хелп, чтобы не было конфликта
bot.remove_command('help')

last_event = None
processed = set()

# --- КОМАНДЫ ---

@bot.command()
async def guild(ctx):
    """Показывает информацию о гильдии"""
    data = await get_guild_info(GUILD_ID)
    if not data:
        await ctx.send("Не удалось получить данные о гильдии.")
        return
    
    embed = discord.Embed(title=f"Информация: {data.get('Name')}", color=0x3498db)
    embed.add_field(name="Лидер", value=data.get('FounderName', 'Нет'), inline=True)
    embed.add_field(name="Участников", value=data.get('MemberCount', 0), inline=True)
    embed.add_field(name="Альянс", value=data.get('AllianceName', 'Без альянса'), inline=False)
    embed.add_field(name="Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def last(ctx):
    """Последнее событие"""
    if not last_event:
        await ctx.send("Событий пока не было.")
        return
    
    e = last_event
    title = "☠️ Убийство" if e.get("Killer", {}).get("GuildId") == GUILD_ID else "💀 Смерть"
    embed = discord.Embed(title=title, color=0x8e44ad)
    embed.add_field(name="Killer", value=e.get("Killer", {}).get("Name", "Unknown"), inline=False)
    embed.add_field(name="Victim", value=e.get("Victim", {}).get("Name", "Unknown"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """Проверка бота"""
    await ctx.send(f"Понг! Задержка: {round(bot.latency * 1000)}мс")

@bot.command()
async def kb(ctx):
    """Ссылка на киллборд"""
    url = f"https://albiononline.com/en/killboard/guild/{GUILD_ID}"
    await ctx.send(f"Киллборд гильдии: {url}")

@bot.command()
async def help(ctx):
    """Список команд"""
    msg = """**Команды бота:**
`!guild` - Статистика гильдии
`!last` - Последнее событие
`!ping` - Задержка бота
`!kb` - Ссылка на киллборд
`!help` - Эта справка"""
    await ctx.send(msg)

# --- МОНИТОРИНГ ---
async def monitor():
    global last_event
    await bot.wait_until_ready()
    kill_ch = bot.get_channel(KILL_CHANNEL)
    death_ch = bot.get_channel(DEATH_CHANNEL)

    while not bot.is_closed():
        try:
            events = await get_events(limit=5)
            for event in events:
                if event["EventId"] in processed: continue
                processed.add(event["EventId"])
                
                result = is_guild_kill(event)
                if not result: continue
                
                last_event = event
                
                killer = event.get("Killer", {})
                victim = event.get("Victim", {})
                fame = event.get("TotalVictimKillFame", 0)
                
                embed = discord.Embed(color=0x8e44ad)
                embed.add_field(name="Killer", value=killer.get("Name", "Unknown"), inline=False)
                embed.add_field(name="Victim", value=victim.get("Name", "Unknown"), inline=False)
                embed.add_field(name="Fame", value=f"{fame:,}", inline=False)

                if result == "kill":
                    embed.title = "☠️ УБИЙСТВО"
                    if kill_ch: await kill_ch.send(embed=embed)
                elif result == "death":
                    embed.title = "💀 СМЕРТЬ"
                    if death_ch: await death_ch.send(embed=embed)
                elif result == "assist":
                    embed.title = "🤝 АССИСТ"
                    if kill_ch: await kill_ch.send(embed=embed)
        except Exception as e:
            print(f"Ошибка: {e}")
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    print(f"Запущен как {bot.user}")
    bot.loop.create_task(monitor())

keep_alive()
bot.run(TOKEN)
