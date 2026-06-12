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

try:
    KILL_CHANNEL = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    KILL_CHANNEL = 0
    DEATH_CHANNEL = 0

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

last_event = None
processed = set()

# --- ФУНКЦІЯ ГЕНЕРАЦІЇ КАРТОЧОК БОЮ ---
def create_battle_embed(event, title, color):
    """Генерує детальний Embed з гільдіями, шкодою та хілом усіх учасників"""
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    fame = event.get("TotalVictimKillFame", 0)
    
    killer_guild = killer.get('GuildName') or 'Без гільдії'
    victim_guild = victim.get('GuildName') or 'Без гільдії'
    
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="👑 Головний убивця", value=f"**{killer.get('Name', 'Невідомо')}**\nГільдія: [{killer_guild}]", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim.get('Name', 'Невідомо')}**\nГільдія: [{victim_guild}]", inline=True)
    embed.add_field(name="✨ Слава за вбивство", value=f"{fame:,}", inline=False)
    
    participants = event.get("Participants") or []
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name", "Невідомо")
            p_guild = p.get("GuildName") or "Без гільдії"
            damage = p.get("DamageDone", 0)
            support = p.get("SupportValue", 0)
            
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
async def scanlive(ctx):
    """Сканує глибокі 100 подій у світі, щоб точно нічого не пропустити"""
    status_msg = await ctx.send("🔍 Глибоке сканування: перевіряю 100 останніх подій в Albion Europe...")
    
    try:
        events = await get_events(limit=100)
        if not events or not isinstance(events, list):
            await status_msg.edit(content="🟡 API Альбіону повернуло порожній список подій.")
            return
        
        found_any = False
        seen_guilds = set()
        
        for event in events:
            k_guild = event.get("Killer", {}).get("GuildName")
            v_guild = event.get("Victim", {}).get("GuildName")
            if k_guild: seen_guilds.add(k_guild)
            if v_guild: seen_guilds.add(v_guild)
            
            result = is_guild_kill(event)
            if result:
                found_any = True
                title_text = "☠️ ЗНАЙДЕНО ВБИВСТВО ГІЛЬДІЇ" if result == "kill" else "💀 ЗНАЙДЕНО СМЕРТЬ СОРАТНИКА"
                color_hex = 0x2ecc71 if result == "kill" else 0xe74c3c
                
                embed = create_battle_embed(event, title_text, color_hex)
                await ctx.send(embed=embed)
        
        if found_any:
            await status_msg.edit(content="✅ Сканування завершено! Втрачені логи гільдії успішно знайдено!")
        else:
            sample_guilds = list(seen_guilds)[:4]
            guilds_str = ", ".join([f"`{g}`" for g in sample_guilds])
            await status_msg.edit(content=f"ℹ️ Проскановано топ-100 глобальних логів. У цьому глибокому списку нашої гільдії вже немає.\n\n"
                                          f"⚙️ **Фільтр працює:** бот успішно відсіяв інші гільдії, наприклад: {guilds_str}.\n"
                                          f"🟢 Тепер, зі збільшеним лімітом, моніторинг не пропустить жодного нового бою!")
    except Exception as e:
        await status_msg.edit(content=f"🔴 Помилка сканування: `{str(e)}`")

@bot.command()
async def testreal(ctx):
    """Експеримент: бере справжній останній кілл з Альбіону і шле в канал"""
    status_msg = await ctx.send("📡 Завантажую свіжий реальний лог з серверу Альбіону...")
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            real_event = events[0]
            embed = create_battle_embed(real_event, "🌐 ЕКСПЕРИМЕНТ: Реальний бій з Альбіону", 0x3498db)
            embed.set_footer(text=f"ID Події в грі: {real_event.get('EventId')}")
            
            kill_ch = bot.get_channel(KILL_CHANNEL)
            if kill_ch:
                await kill_ch.send(embed=embed)
                await status_msg.edit(content=f"✅ Справжній лог успішно отримано і надіслано в канал {kill_ch.mention}!")
            else:
                await status_msg.edit(content="❌ Помилка: Не знайдено KILL_CHANNEL_ID для відправки.")
        else:
            await status_msg.edit(content="🟡 Сервер Альбіону повернув порожній лог.")
    except Exception as e:
        await status_msg.edit(content=f"🔴 Експеримент провалився: `{str(e)}`")

@bot.command()
async def checkapi(ctx):
    """Перевірка працездатності та затримок офіційного API Albion Online"""
    status_msg = await ctx.send("🔍 Зв'язуюся з серверами Albion Online API, зачекайте...")
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            latest_event = events[0]
            event_id = latest_event.get("EventId", "Невідомо")
            timestamp = latest_event.get("TimeStamp", "Невідомо")
            clean_time = timestamp.replace("T", " ").split(".")[0] if "T" in timestamp else timestamp
            
            embed = discord.Embed(title="🌐 Status API Albion Online", color=0x2ecc71)
            embed.add_field(name="🟢 Стан серверов гри", value="Працює, відповідь отримана!", inline=False)
            embed.add_field(name="📊 ID останньої події у світі", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час цієї події (UTC / Час гри)", value=f"`{clean_time}`", inline=True)
            
            await status_msg.delete()
            await ctx.send(embed=embed)
        else:
            await status_msg.delete()
            await ctx.send("🟡 Сервер відповів порожнім списком.")
    except Exception as e:
        await status_msg.delete()
        await ctx.send(f"🔴 Помилка зв'язку: `{str(e)}`")

@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію та налаштування навколишнього середовища"""
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
    embed.add_field(name="🤝 Alliance", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', 'Без альянсу')}", inline=False)
    embed.add_field(name="⚔️ Загальний PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 Загальний PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    embed.add_field(name="⚙️ Куди бот надсилає звіти:", value=f"• ⚔️ **Вбивства:** {kill_mention}\n• 💀 **Смерті:** {death_mention}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def testkill(ctx):
    kill_ch = bot.get_channel(KILL_CHANNEL)
    if not kill_ch: return
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
    await kill_ch.send(embed=embed)

@bot.command()
async def testdeath(ctx):
    death_ch = bot.get_channel(DEATH_CHANNEL)
    if not death_ch: return
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
    await death_ch.send(embed=embed)

@bot.command()
async def help(ctx):
    msg = """**Доступні команди бота:**
`!scanlive` - ДІАГНОСТИКА: глибока перевірка 100 подій у світі через фільтр гільдії
`!testreal` - ЕКСПЕРИМЕНТ: взяти випадковий лог з Європи та надіслати в канал
`!checkapi` - Перевірити статус API Albion Online
`!guild` - Статистика гільдії
`!testkill` - Тестове вбивство
`!testdeath` - Тестова смерть
`!ping` - Перевірити пінг
`!help` - Посилання на команди"""
    await ctx.send(msg)

# --- МОНІТОРИНГ З АВТОМАТИЧНИМ ЛОГУВАННЯМ КРОКІВ ---
async def monitor():
    global last_event
    await bot.wait_until_ready()
    kill_ch = bot.get_channel(KILL_CHANNEL)
    death_ch = bot.get_channel(DEATH_CHANNEL)

    while not bot.is_closed():
        try:
            events = await get_events(limit=100)
            
            if not events or not isinstance(events, list):
                print("[MONITOR] Попередження: Сервер Альбіону повернув порожній список логів.")
            else:
                guild_activity_found = False
                
                for event in events:
                    if event["EventId"] in processed: continue
                    processed.add(event["EventId"])
                    
                    result = is_guild_kill(event)
                    if not result: continue
                    
                    guild_activity_found = True
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
                
                # Якщо за цей цикл у 100 логах не було ваших бійців, пишемо звіт у консоль
                if not guild_activity_found:
                    print(f"[MONITOR] Успішно перевірено {len(events)} подій у світі. Нових боїв гільдії x E C L I P S E x не знайдено.")
                    
        except Exception as e:
            print(f"[MONITOR ERROR] Критична помилка під час перевірки: {e}")
            
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    print(f"Бот успішно авторизований як: {bot.user}")
    bot.loop.create_task(monitor())

keep_alive()
bot.run(TOKEN)
