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

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

last_event = None
processed = set()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ КАРТОЧЕК БОЯ ---
def create_battle_embed(event, title, color):
    """Генерирует подробный Embed с уроном и отхилом участников"""
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})
    fame = event.get("TotalVictimKillFame", 0)
    
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="👑 Главный убийца", value=f"**{killer.get('Name', 'Unknown')}**\nGuild: [{killer.get('GuildName', 'Без гильдии')}]", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim.get('Name', 'Unknown')}**\nGuild: [{victim.get('GuildName', 'Без гильдии')}]", inline=True)
    embed.add_field(name="✨ Слава за убийство", value=f"{fame:,}", inline=False)
    
    # Парсим участников (нанесённый урон и отхил)
    participants = event.get("Participants", [])
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name", "Unknown")
            damage = p.get("DamageDone", 0)
            support = p.get("SupportValue", 0) # Отхил и ассисты в игре
            
            if damage > 0:
                damage_list.append(f"⚔️ **{name}**: {damage:,} DMG")
            if support > 0:
                heal_list.append(f"🧪 **{name}**: {support:,} HEAL")
        
        if damage_list:
            embed.add_field(name="📈 Нанесённый урон:", value="\n".join(damage_list), inline=False)
        if heal_list:
            embed.add_field(name="💚 Исцеление / Поддержка:", value="\n".join(heal_list), inline=False)
    else:
        embed.add_field(name="📊 Статистика участников", value="Нет данных об уроне.", inline=False)
        
    return embed

# --- КОМАНДЫ ---

@bot.command()
async def guild(ctx):
    """Полная информация о гильдии и настройках бота"""
    data = await get_guild_info(GUILD_ID)
    if not data:
        await ctx.send("❌ Не удалось получить данные о гильдии от API Albion.")
        return
    
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
    
    embed.add_field(
        name="⚙️ Куда бот отправляет логи:", 
        value=f"• ⚔️ **Убийства и Ассисты:** {kill_mention}\n• 💀 **Смерти согильдийцев:** {death_mention}", 
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def testkill(ctx):
    """Симуляция убийства с демонстрацией урона и отхила"""
    kill_ch = bot.get_channel(KILL_CHANNEL)
    if not kill_ch:
        await ctx.send("❌ Ошибка: Канал для убийств не найден.")
        return
    
    # Создаем фейковый лог боя
    mock_event = {
        "TotalVictimKillFame": 350000,
        "Killer": {"Name": "Убийца_Из_Eclipse", "GuildName": "x E C L I P S E x"},
        "Victim": {"Name": "Бедолага_Враг", "GuildName": "Забор"},
        "Participants": [
            {"Name": "Убийца_Из_Eclipse", "DamageDone": 4500, "SupportValue": 0},
            {"Name": "ТвойДДСогильдиец", "DamageDone": 3200, "SupportValue": 0},
            {"Name": "НашХилер", "DamageDone": 0, "SupportValue": 5400}
        ]
    }
    
    embed = create_battle_embed(mock_event, "⚔️ ТЕСТОВОЕ УБИЙСТВО (Симуляция урона)", 0x2ecc71)
    embed.set_footer(text="Тестовый вызов команды !testkill")
    
    await kill_ch.send(embed=embed)
    await ctx.send(f"✅ Тестовая карточка с уроном отправлена в канал {kill_ch.mention}!")

@bot.command()
async def testdeath(ctx):
    """Симуляция смерти нашего бойца с демонстрацией урона врагов"""
    death_ch = bot.get_channel(DEATH_CHANNEL)
    if not death_ch:
        await ctx.send("❌ Ошибка: Канал для смертей не найден.")
        return
    
    mock_event = {
        "TotalVictimKillFame": 185000,
        "Killer": {"Name": "ЖестокийГанкер", "GuildName": "ARCH"},
        "Victim": {"Name": "НеудачливыйСогильдиец", "GuildName": "x E C L I P S E x"},
        "Participants": [
            {"Name": "ЖестокийГанкер", "DamageDone": 2800, "SupportValue": 0},
            {"Name": "ВторойВраг", "DamageDone": 1900, "SupportValue": 0},
            {"Name": "ВражескийХил", "DamageDone": 0, "SupportValue": 3100}
        ]
    }
    
    embed = create_battle_embed(mock_event, "💀 ТЕСТОВАЯ СМЕРТЬ (Симуляция урона врагов)", 0xe74c3c)
    embed.set_footer(text="Тестовый вызов команды !testdeath")
    
    await death_ch.send(embed=embed)
    await ctx.send(f"✅ Тестовая карточка смерти отправлена в канал {death_ch.mention}!")

@bot.command()
async def last(ctx):
    """Последнее реальное событие"""
    if not last_event:
        await ctx.send("Реальных событий с момента запуска бота ещё не зафиксировано.")
        return
    
    title = "☠️ Убийство" if last_event.get("Killer", {}).get("GuildId") == GUILD_ID else "💀 Смерть"
    embed = create_battle_embed(last_event, title, 0x8e44ad)
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
`!testkill` - Тестовое убийство (проверка урона/отхила)
`!testdeath` - Тестовая смерть (проверка урона врагов)
`!last` - Показать последнее реальное событие с DMG/HEAL
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
                
                if result == "kill":
                    embed = create_battle_embed(event, "☠️ УБИЙСТВО", 0x2ecc71)
                    if kill_ch: await kill_ch.send(embed=embed)
                elif result == "death":
                    embed = create_battle_embed(event, "💀 СМЕРТЬ", 0xe74c3c)
                    if death_ch: await death_ch.send(embed=embed)
                elif result == "assist":
                    embed = create_battle_embed(event, "🤝 АССИСТ", 0x3498db)
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
