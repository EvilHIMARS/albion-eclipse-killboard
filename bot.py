import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import get_events, get_guild_info
from tracker import is_guild_kill

# ==========================================
# 📊 НАЛАШТУВАННЯ СИСТЕМНОГО ЛОГУВАННЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AlbionBot")

# --- WEB-СЕРВЕР ДЛЯ ПІДТРИМАННЯ АКТИВНОСТІ (Uptime) ---
app = Flask('')
@app.route('/')
def home(): 
    return "Бот активний і здійснює моніторинг логів!"

def run_server():
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
    logger.info("🌐 [UPTIME] Внутрішній веб-сервер запущено на порту 10000")

# ==========================================
# ⚙️ ІНІЦІАЛІЗАЦІЯ ТА НАЛАШТУВАННЯ БОТА
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logger.info("=" * 50)
logger.info("⚙️  [INIT] Завантаження конфігурації...")
logger.info(f"⚙️  [INIT] GUILD_ID: {GUILD_ID or '❌ НЕ ЗНАЙДЕНО'}")

try:
    KILL_CHANNEL_ID = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL_ID = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    logger.error("❌ [INIT] Критична помилка: ID каналів в .env вказано некоректно!")
    KILL_CHANNEL_ID = 0
    DEATH_CHANNEL_ID = 0

logger.info(f"⚙️  [INIT] KILL_CHANNEL_ID: {KILL_CHANNEL_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] DEATH_CHANNEL_ID: {DEATH_CHANNEL_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] DISCORD_TOKEN: {'✅ Знайдено' if TOKEN else '❌ НЕ ЗНАЙДЕНО'}")
logger.info("=" * 50)

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# 🧠 ЗАХИСТ ВІД ДУБЛІВ З ОПТИМІЗАЦІЄЮ ПАМ'ЯТІ
PROCESSED_EVENTS = set()
MAX_CACHE_SIZE = 2000

# Лічильник циклів для статистики
_cycle_count = 0
_total_events_scanned = 0
_total_guild_events = 0

# ==========================================
# 🧾 ФОРМАТ EMBED-ПОВІДОМЛЕНЬ
# ==========================================
def create_battle_embed(event, title, color_hex):
    """Генерує детальну картку бою з прямими посиланнями"""
    event_id = event.get("EventId", 0)
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    fame = event.get("TotalVictimKillFame", 0)
    
    killer_name = killer.get('Name', 'Невідомо')
    killer_guild = killer.get('GuildName') or 'Без гільдії'
    victim_name = victim.get('Name', 'Невідомо')
    victim_guild = victim.get('GuildName') or 'Без гільдії'
    
    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"
    
    embed = discord.Embed(
        title=title, 
        url=killboard_url, 
        color=color_hex,
        description=f"🔗 [Відкрити цей бій на офіційному Кілборді]({killboard_url})"
    )
    
    embed.add_field(name="⚔️ Вбивця", value=f"**{killer_name}**\n`[{killer_guild}]`", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim_name}**\n`[{victim_guild}]`", inline=True)
    embed.add_field(name="✨ Слава за вбивство (Fame)", value=f"🏆 **{fame:,}**", inline=False)
    
    participants = event.get("Participants") or []
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name", "Невідомо")
            guild = p.get("GuildName") or "Без гільдії"
            dmg = p.get("DamageDone", 0)
            heal = p.get("SupportValue", 0)
            
            if dmg > 0:
                damage_list.append(f"• **{name}** `[{guild}]`: {dmg:,} DMG")
            if heal > 0:
                heal_list.append(f"• **{name}** `[{guild}]`: {heal:,} HEAL")
        
        if damage_list:
            embed.add_field(name="📈 Розподіл шкоди:", value="\n".join(damage_list[:5]), inline=False)
        if heal_list:
            embed.add_field(name="💚 Підтримка та зцілення:", value="\n".join(heal_list[:5]), inline=False)
            
    embed.set_footer(text=f"ID події: {event_id} | Розробник: EvilHIMARS")
    return embed

# ==========================================
# 🧩 МЕНЕДЖЕРИ ТА АТОМАРНІ ФУНКЦІЇ
# ==========================================
def manage_cache(event_id):
    """Контролює захист від дублікатів та очищає старий кеш при переповненні"""
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False
        
    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info(f"🧹 [КЕШ] Кеш дублікатів заповнено ({len(PROCESSED_EVENTS)} записів). Планова очистка пам'яті...")
        PROCESSED_EVENTS.clear()
        
    PROCESSED_EVENTS.add(event_id)
    return True

async def dispatch_event(event, result_type, kill_ch, death_ch):
    """Ізольована функція відправки конкретної події в потрібний канал"""
    event_id = event.get("EventId")
    killer_name = (event.get("Killer") or {}).get("Name", "?")
    victim_name = (event.get("Victim") or {}).get("Name", "?")
    fame = event.get("TotalVictimKillFame", 0)

    try:
        if result_type == "kill":
            embed = create_battle_embed(event, "☠️ НОВЕ ВБИВСТВО ГІЛЬДІЇ", 0x2ecc71)
            if kill_ch: 
                await kill_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Вбивство #{event_id}: {killer_name} вбив {victim_name} | Fame: {fame:,}")
                
        elif result_type == "death":
            embed = create_battle_embed(event, "💀 ВТРАТА В БОЮ (СМЕРТЬ)", 0xe74c3c)
            if death_ch: 
                await death_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Смерть #{event_id}: {victim_name} загинув від {killer_name} | Fame: {fame:,}")
                
        elif result_type == "assist":
            embed = create_battle_embed(event, "🤝 АСИСТ ГІЛЬДІЇ У ВБИВСТВІ", 0x3498db)
            if kill_ch: 
                await kill_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Асист #{event_id}: допомога у вбивстві {victim_name} | Fame: {fame:,}")
    except Exception as dispatch_err:
        logger.error(f"❌ [ВІДПРАВКА] Не вдалося відправити повідомлення в Discord для #{event_id}: {dispatch_err}")

# ==========================================
# 🔁 СТАБІЛЬНИЙ ЦИКЛ РОБОТИ 24/7
# ==========================================
async def monitor_loop():
    """Головний ізольований цикл моніторингу, стійкий до будь-яких помилок мережі та API"""
    global _cycle_count, _total_events_scanned, _total_guild_events

    await bot.wait_until_ready()
    
    kill_channel = bot.get_channel(KILL_CHANNEL_ID)
    death_channel = bot.get_channel(DEATH_CHANNEL_ID)

    logger.info("=" * 50)
    logger.info("🚀 [МОНІТОР] Запуск фонового моніторингу Albion API")
    logger.info(f"🚀 [МОНІТОР] Канал вбивств: {'✅ ' + kill_channel.name if kill_channel else '❌ НЕ ЗНАЙДЕНО (ID: ' + str(KILL_CHANNEL_ID) + ')'}")
    logger.info(f"🚀 [МОНІТОР] Канал смертей: {'✅ ' + death_channel.name if death_channel else '❌ НЕ ЗНАЙДЕНО (ID: ' + str(DEATH_CHANNEL_ID) + ')'}")
    logger.info(f"🚀 [МОНІТОР] Інтервал опитування: кожні 30 секунд")
    logger.info(f"🚀 [МОНІТОР] Ліміт подій за запит: 100")
    logger.info("=" * 50)

    # Тестовий запит при старті
    logger.info("🔌 [МОНІТОР] Підключення до серверів Albion Online (Europe Gateway)...")
    test_events = await get_events(limit=5)
    if test_events and isinstance(test_events, list):
        logger.info(f"✅ [МОНІТОР] З'єднання з Albion API успішне! Отримано {len(test_events)} тестових подій")
        logger.info(f"✅ [МОНІТОР] Останній EventId у світі: {test_events[0].get('EventId', '?')}")
    else:
        logger.warning("⚠️  [МОНІТОР] Albion API повернув порожню відповідь при тестовому запиті. Можливо сервер перевантажений.")

    logger.info("🔄 [МОНІТОР] Починаю безперервний моніторинг подій гільдії...")

    while not bot.is_closed():
        _cycle_count += 1
        try:
            logger.info(f"📡 [ЦИКЛ #{_cycle_count}] Відправляю запит до Albion API (limit=100)...")
            events = await get_events(limit=100)
            
            if not events or not isinstance(events, list):
                logger.warning(f"⚠️  [ЦИКЛ #{_cycle_count}] Albion API повернув порожній список. Пропуск ітерації. Наступна спроба через 30 сек.")
                await asyncio.sleep(30)
                continue

            _total_events_scanned += len(events)
            new_events_count = 0
            guild_events_in_cycle = 0
                
            for event in events:
                event_id = event.get("EventId")
                if not event_id: 
                    continue
                
                if not manage_cache(event_id):
                    continue

                new_events_count += 1
                
                result_type = is_guild_kill(event)
                if not result_type: 
                    continue
                
                guild_events_in_cycle += 1
                _total_guild_events += 1
                await dispatch_event(event, result_type, kill_channel, death_channel)
            
            duplicates_count = len(events) - new_events_count
            logger.info(
                f"📊 [ЦИКЛ #{_cycle_count}] Результат: отримано {len(events)} подій | "
                f"нових: {new_events_count} | дублікатів: {duplicates_count} | "
                f"події гільдії: {guild_events_in_cycle} | "
                f"кеш: {len(PROCESSED_EVENTS)} записів"
            )

            if guild_events_in_cycle > 0:
                logger.info(f"🎯 [ЦИКЛ #{_cycle_count}] Знайдено {guild_events_in_cycle} подій гільдії! Відправлено в Discord.")
            
            # Кожні 10 циклів (~5 хв) — загальна статистика
            if _cycle_count % 10 == 0:
                logger.info(
                    f"📈 [СТАТИСТИКА] Загалом за {_cycle_count} циклів: "
                    f"проскановано {_total_events_scanned} подій | "
                    f"знайдено {_total_guild_events} подій гільдії | "
                    f"кеш: {len(PROCESSED_EVENTS)}/{MAX_CACHE_SIZE}"
                )
                
        except asyncio.CancelledError:
            logger.info("🛑 [МОНІТОР] Цикл моніторингу зупинено адміністратором.")
            break
        except Exception as global_loop_error:
            logger.error(f"❌ [ЦИКЛ #{_cycle_count}] Критичний збій: {type(global_loop_error).__name__}: {global_loop_error}. Перезапуск через 30 сек...")
            
        await asyncio.sleep(30)

# ==========================================
# 📋 КОМАНДИ БОТА
# ==========================================
@bot.event
async def on_ready():
    logger.info("=" * 50)
    logger.info(f"✅ [DISCORD] Бот успішно авторизовано!")
    logger.info(f"✅ [DISCORD] Ім'я бота: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"✅ [DISCORD] Підключено до {len(bot.guilds)} серверів Discord")
    for g in bot.guilds:
        logger.info(f"   📌 Сервер: {g.name} (ID: {g.id}, учасників: {g.member_count})")
    logger.info("=" * 50)
    
    logger.info("🔧 [DISCORD] Доступні команди бота:")
    logger.info("   !checkapi  — Перевірка статусу API Albion Online")
    logger.info("   !guild     — Статистика гільдії")
    logger.info("   !status    — Статус моніторингу бота")
    logger.info("   !help      — Список всіх команд")
    
    bot.loop.create_task(monitor_loop())

@bot.command()
async def checkapi(ctx):
    """Перевірка доступності шлюзу Albion"""
    logger.info(f"🔧 [КОМАНДА] !checkapi від {ctx.author}")
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            event = events[0]
            event_id = event.get('EventId', '?')
            timestamp = event.get('TimeStamp', '?')
            logger.info(f"✅ [КОМАНДА] !checkapi — API відповів, EventId: {event_id}")
            
            embed = discord.Embed(title="🌐 Статус API Albion Online", color=0x2ecc71)
            embed.add_field(name="🟢 Стан серверів", value="Працює, відповідь отримано!", inline=False)
            embed.add_field(name="📊 ID останньої події", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час події (UTC)", value=f"`{timestamp}`", inline=True)
            await ctx.send(embed=embed)
        else:
            logger.warning("[КОМАНДА] !checkapi — API повернув порожній масив")
            await ctx.send("🟡 **API повернуло порожній масив даних.** Можливо сервери гри перевантажені.")
    except Exception as e:
        logger.error(f"❌ [КОМАНДА] !checkapi — збій: {e}")
        await ctx.send(f"🔴 **Помилка з'єднання з API:** `{str(e)}`")

@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію"""
    logger.info(f"🔧 [КОМАНДА] !guild від {ctx.author}")
    data = await get_guild_info(GUILD_ID)
    if not data:
        logger.warning(f"[КОМАНДА] !guild — не вдалося отримати дані для {GUILD_ID}")
        await ctx.send("❌ Не вдалося отримати дані гільдії від API Albion.")
        return
    
    kill_ch = bot.get_channel(KILL_CHANNEL_ID)
    death_ch = bot.get_channel(DEATH_CHANNEL_ID)
    kill_mention = kill_ch.mention if kill_ch else f"`ID: {KILL_CHANNEL_ID} (Не знайдено)`"
    death_mention = death_ch.mention if death_ch else f"`ID: {DEATH_CHANNEL_ID} (Не знайдено)`"
    
    guild_name = data.get('Name', 'Невідомо')
    logger.info(f"✅ [КОМАНДА] !guild — отримано дані для гільдії: {guild_name}")
    
    embed = discord.Embed(title=f"🏰 Статистика гільдії: {guild_name}", color=0x3498db)
    embed.add_field(name="👑 Лідер (Засновник)", value=data.get('FounderName', 'Немає'), inline=True)
    embed.add_field(name="👥 Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="🤝 Альянс", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', 'Без альянсу')}", inline=False)
    embed.add_field(name="⚔️ PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    embed.add_field(name="⚙️ Канали бота:", value=f"• ⚔️ **Вбивства:** {kill_mention}\n• 💀 **Смерті:** {death_mention}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def status(ctx):
    """Статус моніторингу бота"""
    logger.info(f"🔧 [КОМАНДА] !status від {ctx.author}")
    
    embed = discord.Embed(title="📊 Статус моніторингу бота", color=0x9b59b6)
    embed.add_field(name="🔄 Циклів опитування", value=f"`{_cycle_count}`", inline=True)
    embed.add_field(name="📡 Подій проскановано", value=f"`{_total_events_scanned:,}`", inline=True)
    embed.add_field(name="🎯 Подій гільдії знайдено", value=f"`{_total_guild_events}`", inline=True)
    embed.add_field(name="🧠 Кеш дублікатів", value=f"`{len(PROCESSED_EVENTS)} / {MAX_CACHE_SIZE}`", inline=True)
    embed.add_field(name="⏱️ Інтервал", value="`кожні 30 сек`", inline=True)
    embed.add_field(name="📦 Ліміт подій", value="`100 за запит`", inline=True)
    
    kill_ch = bot.get_channel(KILL_CHANNEL_ID)
    death_ch = bot.get_channel(DEATH_CHANNEL_ID)
    channels_status = (
        f"⚔️ Вбивства: {'✅ ' + kill_ch.name if kill_ch else '❌ Не знайдено'}\n"
        f"💀 Смерті: {'✅ ' + death_ch.name if death_ch else '❌ Не знайдено'}"
    )
    embed.add_field(name="📺 Канали", value=channels_status, inline=False)
    embed.set_footer(text=f"GUILD_ID: {GUILD_ID}")
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    """Список усіх команд бота"""
    logger.info(f"🔧 [КОМАНДА] !help від {ctx.author}")
    embed = discord.Embed(title="📋 Команди бота x E C L I P S E x", color=0xf39c12)
    embed.add_field(name="!checkapi", value="Перевірити статус та з'єднання з API Albion Online", inline=False)
    embed.add_field(name="!guild", value="Повна статистика гільдії: учасники, fame, альянс, канали бота", inline=False)
    embed.add_field(name="!status", value="Статус моніторингу: скільки циклів, подій, стан кешу", inline=False)
    embed.add_field(name="!help", value="Цей список команд", inline=False)
    embed.set_footer(text="Бот моніторить Albion API кожні 30 секунд | Розробник: EvilHIMARS")
    await ctx.send(embed=embed)

# Запуск всієї екосистеми
keep_alive()
bot.run(TOKEN)
