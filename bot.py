import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import get_events, get_guild_info
from tracker import is_guild_kill

# --- WEB-СЕРВЕР ДЛЯ ПОДДЕРЖАНИЯ АКТИВНОСТИ ---
app = Flask('')
@app.route('/')
def home(): return "Бот активний!"
def run_server(): app.run(host='0.0.0.0', port=10000)
def keep_alive():
    t = Thread(target=run_server)
    t.start()

# --- НАЛАШТУВАННЯ ---
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

# --- ФУНКЦІЯ ГЕНЕРАЦІЇ КАРТОЧОК БОЮ ---
def create_battle_embed(event, title, color):
    """Генерує детальний Embed з гільдіями, шкодою та хілом усіх учасників"""
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})
    fame = event.get("TotalVictimKillFame", 0)
    
    killer_guild = killer.get('GuildName') or 'Без гільдії'
    victim_guild = victim.get('GuildName') or 'Без гільдії'
    
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="👑 Головний убивця", value=f"**{killer.get('Name', 'Невідомо')}**\nГільдія: [{killer_guild}]", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim.get('Name', 'Невідомо')}**\nГільдія: [{victim_guild}]", inline=True)
    embed.add_field(name="✨ Слава за вбивство", value=f"{fame:,}", inline=False)
    
    # Парсинг усіх учасників бою (хто наносив шкоду чи лікував)
    participants = event.get("Participants", [])
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name", "Невідомо")
            p_guild = p.get("GuildName") or "Без гільдії"
            damage = p.get("DamageDone", 0)
            support = p.get("SupportValue", 0) # Хіл та асисти в Albion API
            
            # Форматуємо рядок: Гравець [Гільдія]: значення
            if damage > 0:
                damage_list.append(f"⚔️ **{name}** [{p_guild}]: {damage:,} DMG")
            if support > 0:
                heal_list.append(f"🧪 **{name}** [{p_guild}]: {support:,} HEAL")
        
        if damage_list:
            embed.add_field(name="📈 Нанесена шкода (Учасники):", value="\n".join(damage_list), inline=False)
        if heal_list:
            embed.add_field(name="💚 Інтенсивність зцілення / Підтримка:", value="\n".join(heal_list), inline=False)
    else:
        embed.add_field(name="📊 Статистика учасників", value="Немає детальних даних про шкоду чи хіл.", inline=False)
        
    return embed

# --- КОМАНДЫ БОТА ---

@bot.command()
async def checkapi(ctx):
    """Перевірка працездатності та затримок офіційного API Albion Online"""
    status_msg = await ctx.send("🔍 Зв'язуюся з серверами Albion Online API, зачекайте...")
    
    try:
        # Робимо запит на отримання 1 найсвіжішої події у грі
        events = await get_events(limit=1)
        
        if events and isinstance(events, list):
            latest_event = events[0]
            event_id = latest_event.get("EventId", "Невідомо")
            timestamp = latest_event.get("TimeStamp", "Невідомо")
            
            # Очищаємо хвостик часу для красивого відображення (зазвичай там йде YYYY-MM-DDTHH:MM:SS)
            clean_time = timestamp.replace("T", " ").split(".")[0] if "T" in timestamp else timestamp
            
            embed = discord.Embed(title="🌐 Статус API Albion Online", color=0x2ecc71)
            embed.add_field(name="🟢 Стан серверов гри", value="Працює, відповідь отримана!", inline=False)
            embed.add_field(name="📊 ID останньої події у світі", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час цієї події (UTC / Час гри)", value=f"`{clean_time}`", inline=True)
            embed.set_footer(text="💡 Порівняй час гри з поточним. Якщо різниця велика — API працює із затримкою.")
            
            await status_msg.delete()
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="🌐 Статус API Albion Online", color=0xf1c40f)
            embed.add_field(name="🟡 Попередження", value="Сервер відповів, але надіслав порожній список подій. Можливо, ведуться технічні роботи.", inline=False)
            await status_msg.delete()
            await ctx.send(embed=embed)
            
    except Exception as e:
        embed = discord.Embed(title="🌐 Статус API Albion Online", color=0xe74c3c)
        embed.add_field(name="🔴 Помилка зв'язку", value="Офіційне API Альбіону зараз **ПОВНІСТЮ ЛЕЖИТЬ** або скидає з'єднання через перевантаження серверів.", inline=False)
        embed.add_field(name="🪲 Технічна помилка", value=f"`{str(e)}`", inline=False)
        embed.set_footer(text="Бот автоматично продовжить роботу, щойно сервери Albion відновлять роботу.")
        
        await status_msg.delete()
        await ctx.send(embed=embed)

@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію та налаштування каналів бота"""
    data = await get_guild_info(GUILD_ID)
    if not data:
        await ctx.send("❌ Не вдалося отримати дані гільдії від API Albion.")
        return
    
    kill_ch = bot.get_channel(KILL_CHANNEL)
    death_ch = bot.get_channel(DEATH_CHANNEL)
    
    kill_mention = kill_ch.mention if kill_ch else f"`ID: {KILL_CHANNEL} (Не знайдено)`"
    death_mention = death_ch.mention if death_ch else f"`ID: {DEATH_CHANNEL} (Не знайдено)`"
    
    embed = discord.Embed(title=f"🏰 Повна статистика гільдії: {data.get('Name')}", color=0x3498db)
    embed.add_field(name="👑 Лідер (Засновник)", value=data.get('FounderName', 'Немає'), inline=True)
    embed.add_field(name="👥 Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="🤝 Альянс", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', 'Без альянсу')}", inline=False)
    embed.add_field(name="⚔️ Загальний PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 Загальний PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    
    embed.add_field(
        name="⚙️ Куди бот надсилає звіти:", 
        value=f"• ⚔️ **Вбивства та Асисти:** {kill_mention}\n• 💀 **Смерті соратників:** {death_mention}", 
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def testkill(ctx):
    """Симуляція вбивства ворога з відображенням гільдій та урону"""
    kill_ch = bot.get_channel(KILL_CHANNEL)
    if not kill_ch:
        await ctx.send("❌ Помилка: Канал для вбивств не знайдено.")
        return
    
    mock_event = {
        "TotalVictimKillFame": 350000,
        "Killer": {"Name": "Вбивця_з_Eclipse", "GuildName": "x E C L I P S E x"},
        "Victim": {"Name": "Невдаха_Ворог", "GuildName": "Ворожа_Гільдія"},
        "Participants": [
            {"Name": "Вбивця_з_Eclipse", "GuildName": "x E C L I P S E x", "DamageDone": 4500, "SupportValue": 0},
            {"Name": "Наш_ДД_Боєць", "GuildName": "x E C L I P S E x", "DamageDone": 3200, "SupportValue": 0},
            {"Name": "Наш_Хілер", "GuildName": "x E C L I P S E x", "DamageDone": 0, "SupportValue": 5400}
        ]
    }
    
    embed = create_battle_embed(mock_event, "⚔️ ТЕСТОВЕ ВБИВСТВО (Демонстрація логів)", 0x2ecc71)
    embed.set_footer(text="Тестовий виклик команди !testkill")
    
    await kill_ch.send(embed=embed)
    await ctx.send(f"✅ Тестова картка з гільдіями та шкодою надіслана в канал {kill_ch.mention}!")

@bot.command()
async def testdeath(ctx):
    """Симуляція смерті нашого бійця (хто вбив, хто допомагав з ворогів)"""
    death_ch = bot.get_channel(DEATH_CHANNEL)
    if not death_ch:
        await ctx.send("❌ Помилка: Канал для смертей не знайдено.")
        return
    
    mock_event = {
        "TotalVictimKillFame": 185000,
        "Killer": {"Name": "ЖорстокийГанкер", "GuildName": "ARCH"},
        "Victim": {"Name": "Наш_Хтось_Приліг", "GuildName": "x E C L I P S E x"},
        "Participants": [
            {"Name": "ЖорстокийГанкер", "GuildName": "ARCH", "DamageDone": 2800, "SupportValue": 0},
            {"Name": "ДругийВорог", "GuildName": "ARCH", "DamageDone": 1900, "SupportValue": 0},
            {"Name": "ВорожийХілер", "GuildName": "Помічники_ARCH", "DamageDone": 0, "SupportValue": 3100}
        ]
    }
    
    embed = create_battle_embed(mock_event, "💀 ТЕСТОВА СМЕРТЬ (Аналіз отриманої шкоди)", 0xe74c3c)
    embed.set_footer(text="Тестовий виклик команди !testdeath")
    
    await death_ch.send(embed=embed)
    await ctx.send(f"✅ Тестова картка смерті надіслана в канал {death_ch.mention}!")

@bot.command()
async def last(ctx):
    """Остання реальна подія зафіксована ботом"""
    if not last_event:
        await ctx.send("Реальних подій з моменту запуска бота ще не було зафіксовано.")
        return
    
    title = "☠️ Вбивство" if last_event.get("Killer", {}).get("GuildId") == GUILD_ID else "💀 Смерть"
    embed = create_battle_embed(last_event, title, 0x8e44ad)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """Перевірка пінгу бота"""
    await ctx.send(f"Понг! Затримка бота: {round(bot.latency * 1000)}мс")

@bot.command()
async def kb(ctx):
    """Посилання на кіллборд гільдії"""
    url = f"https://albiononline.com/en/killboard/guild/{GUILD_ID}?server=live_ams"
    await ctx.send(f"🔗 Офіційний кіллборд гільдії (Європа): {url}")

@bot.command()
async def help(ctx):
    """Список усіх доступних команд"""
    msg = """**Доступні команди бота (Українською):**
`!checkapi` - Перевірити, чи працює зараз API Альбіону (чи є затримки серверов)
`!guild` - Повна статистика нашої гільдії та налаштування каналів
`!testkill` - Тестове вбивство (перевірка відображення гільдій учасників)
`!testdeath` - Тестова смерть (перевірка логу шкоди від ворогів)
`!last` - Показати останню реальну пвп подію з DMG/HEAL
`!kb` - Посилання на сторінку кіллборду гільдії
`!ping` - Перевірити швидкість відгуку бота
`!help` - Показати це інформаційне повідомлення"""
    await ctx.send(msg)

# --- ЦИКЛ МОНІТОРИНГУ API АЛБІОНУ ---
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
                    embed = create_battle_embed(event, "☠️ ВБИВСТВО", 0x2ecc71)
                    if kill_ch: await kill_ch.send(embed=embed)
                elif result == "death":
                    embed = create_battle_embed(event, "💀 СМЕРТЬ", 0xe74c3c)
                    if death_ch: await death_ch.send(embed=embed)
                elif result == "assist":
                    embed = create_battle_embed(event, "🤝 АСИСТ ГІЛЬДІЇ", 0x3498db)
                    if kill_ch: await kill_ch.send(embed=embed)
        except Exception as e:
            print(f"Помилка під час моніторингу API: {e}")
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    print(f"Бот успішно авторизований як: {bot.user}")
    bot.loop.create_task(monitor())

keep_alive()
bot.run(TOKEN)
