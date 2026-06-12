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

# Отключаем встроенный хелп, чтобы сделать свой custom
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

last_event = None
processed = set()

# --- КОМАНДЫ ---

@bot.command()
async def guild(ctx):
    """Полная информация о гильдии и настройках бота"""
    data = await get_guild_info(GUILD_ID)
    if not data:
        await ctx.send("❌ Не удалось получить данные о гильдии от API Albion.")
        return
    
    # Получаем каналы, чтобы красиво тегнуть их в дискорде
    kill_ch = bot.get_channel(KILL_CHANNEL)
    death_ch = bot.get_channel(DEATH_CHANNEL)
    
    kill_mention = kill_ch.mention if kill_ch else f"`ID: {KILL_CHANNEL} (Не найден)`"
    death_mention = death_ch.mention if death_ch else f"`ID: {DEATH_CHANNEL} (Не найден)`"
    
    embed = discord.Embed(title=f"🏰 Полная статистика гильдии: {data.get('Name')}", color=0x3498db)
    embed.add_field(name="👑 Лидер (Основатель)", value=data.get('FounderName', 'Нет'), inline=True)
    embed.add_field(name="👥 Участников", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="🤝 Альянс", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', 'Без альянса')}", inline=False)
    embed.add_field(name="⚔️ Общий PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 Общий PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    
    # Блок с инфой о распределении логов
    embed.add_field(
        name="⚙️ Куда бот отправляет логи:", 
        value=f"• ⚔️ **Убийства и Ассисты:** {kill_mention}\n• 💀 **Смерти согильдийцев:** {death_mention}", 
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def testkill(ctx):
    """Симуляция успешного убийства"""
    kill_ch = bot.get_channel(KILL_CHANNEL)
    if not kill_ch:
        await ctx.send("❌ Ошибка: Канал для убийств не найден в кэше бота. Проверьте ID.")
        return
    
    embed = discord.Embed(title="⚔️ ТЕСТОВОЕ УБИЙСТВО (Симуляция)", color=0x2ecc71)
    embed.add_field(name="Killer (Наш боец)", value=f"Убийца_Из_Eclipse [{GUILD_ID[:6]}...]", inline=False)
    embed.add_field(name="Victim (Враг)", value="КакойТоБедолага [MOCK_GUILD]", inline=False)
    embed.add_field(name="Fame", value="250,000", inline=False)
    embed.set_footer(text="Тестовый вызов команды !testkill")
    
    await kill_ch.send(embed=embed)
    await ctx.send(f"✅ Тестовая карточка убийства отправлена в канал {kill_ch.mention}!")

@bot.command()
async def testdeath(ctx):
    """Симуляция смерти нашего бойца"""
    death_ch = bot.get_channel(DEATH_CHANNEL)
    if not death_ch:
        await ctx.send("❌ Ошибка: Канал для смертей не найден в кэше бота. Проверьте ID.")
        return
    
    embed = discord.Embed(title="💀 ТЕСТОВАЯ СМЕРТЬ (Симуляция)", color=0xe74c3c)
    embed.add_field(name="Killer (Враг)", value="ЗлобныйГанкер [ARCH]", inline=False)
    embed.add_field(name="Victim (Наш боец)", value=f"НеудачливыйСогильдиец [{GUILD_ID[:6]}...]", inline=False)
    embed.add_field(name="Fame", value="120,000", inline=False)
    embed.set_footer(text="Тестовый вызов команды !testdeath")
    
    await death_ch.send(embed=embed)
    await ctx.send(f"✅ Тестовая карточка смерти отправлена в канал {death_ch.mention}!")

@bot.command()
async def last(ctx):
    """Последнее реальное событие из мониторинга"""
    if not last_event:
        await ctx.send("Реальных событий с момента запуска бота ещё не зафиксировано.")
        return
    
    e = last_event
    title = "☠️ Убийство" if e.get("Killer", {}).get("GuildId") == GUILD_ID else "💀 Смерть"
    embed = discord.Embed(title=title, color=0x8e44ad)
    embed.add_field(name="Killer", value=e.get("Killer", {}).get("Name", "Unknown"), inline=False)
    embed.add_field(name="Victim", value=e.get("Victim", {}).get("Name", "Unknown"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """Проверка задержки бота"""
    await ctx.send(f"Понг! Задержка: {round(bot.latency * 1000)}мс")

@bot.command()
async def kb(ctx):
    """Ссылка на киллборд гильдии"""
    url = f"https://albiononline.com/en/killboard/guild/{GUILD_ID}?server=live_ams"
    await ctx.send(f"Киллборд гильдии (Европа): {url}")

@bot.command()
async def help(ctx):
    """Список всех команд"""
    msg = """**Доступные команды бота:**
`!guild` - Полная статистика гильдии + настройки каналов
`!testkill` - Отправить тестовое убийство в килл-борд
`!testdeath` - Отправить тестовую смерть в дед-борд
`!last` - Показать последнее реальное событие из игры
`!kb` - Ссылка на официальный киллборд
`!ping` - Проверить, живой ли бот
`!help` - Показать это сообщение"""
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
            print(f"Ошибка в мониторинге: {e}")
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    print(f"Запущен как {bot.user}")
    bot.loop.create_task(monitor())

keep_alive()
bot.run(TOKEN)
