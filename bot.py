import os
import sys
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from albion_api import get_events, get_guild_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlbionBot")

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# --- Валідація обов'язкових змінних оточення ---
_missing_env = []
if not TOKEN:
    _missing_env.append("DISCORD_TOKEN")
if not GUILD_ID:
    _missing_env.append("GUILD_ID")
if _missing_env:
    logger.critical(
        "Відсутні обов'язкові змінні оточення: %s. Бот не може бути запущений.",
        ", ".join(_missing_env),
    )
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
PROCESSED_EVENTS = set()

# Uptime-сервер
app = Flask('')
@app.route('/')
def home(): return "Бот активний"

def run_server():
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=10000)

Thread(target=run_server, daemon=True).start()

@bot.command()
async def scanlive(ctx):
    """Сканування 20 останніх подій"""
    try:
        events = await get_events(limit=20)
    except Exception as e:
        logger.exception("Помилка при виклику get_events у !scanlive: %s", e)
        try:
            await ctx.send(f"🔴 **Помилка з'єднання з API:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")
        return

    if not events:
        await ctx.send("❌ API не відповіло або подій немає.")
        return

    for event in events:
        killer = (event.get('Killer') or {}).get('Name', 'Unknown')
        victim = (event.get('Victim') or {}).get('Name', 'Unknown')
        embed = discord.Embed(title="⚔ Подія", color=discord.Color.blue())
        embed.add_field(name="Вбивця", value=killer, inline=True)
        embed.add_field(name="Жертва", value=victim, inline=True)

        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            logger.error("Немає прав для надсилання повідомлення в канал %s", ctx.channel.id)
            return
        except discord.HTTPException as e:
            logger.error("HTTP помилка Discord при відправленні embed: %s", e)
            return

@bot.command()
async def checkapi(ctx):
    """Перевірка статусу"""
    try:
        events = await get_events(limit=1)
        if events:
            await ctx.send("🟢 API працює стабільно.")
        else:
            await ctx.send("🔴 API недоступне.")
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити відповідь на !checkapi: %s", e)
    except Exception as e:
        logger.exception("Команда !checkapi викликала збій: %s", e)
        try:
            await ctx.send(f"🔴 **Помилка з'єднання з API:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def guild(ctx):
    """Статистика гільдії"""
    try:
        data = await get_guild_info(GUILD_ID)
        if data:
            await ctx.send(f"🏰 Гільдія: {data.get('Name')} | Учасників: {data.get('MemberCount')}")
        else:
            await ctx.send("❌ Не вдалося отримати дані.")
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити відповідь на !guild: %s", e)
    except Exception as e:
        logger.exception("Команда !guild викликала збій: %s", e)
        try:
            await ctx.send(f"🔴 **Помилка:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.event
async def on_ready():
    logger.info("Бот %s готовий до роботи! (ID: %s)", bot.user.name, bot.user.id)

bot.run(TOKEN)
