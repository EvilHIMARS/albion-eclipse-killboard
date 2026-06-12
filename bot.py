import os
import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from albion_api import (
    get_events, get_guild_info, get_guild_top,
    search_player, get_player_info, get_player_kills, get_player_deaths,
    get_event_details, get_guild_members
)
from tracker import is_guild_kill

# ==========================================
# 🌐 МУЛЬТИМОВНА СИСТЕМА (UA/RU/EN)
# ==========================================
TRANSLATIONS = {
    "ua": {
        "kill_title": "☠️ НОВЕ ВБИВСТВО ГІЛЬДІЇ",
        "death_title": "💀 ВТРАТА В БОЮ (СМЕРТЬ)",
        "assist_title": "🤝 АСИСТ ГІЛЬДІЇ У ВБИВСТВІ",
        "killer": "⚔️ Вбивця",
        "victim": "💀 Жертва",
        "fame": "✨ Слава (Fame)",
        "no_guild": "Без гільдії",
        "unknown": "Невідомо",
        "damage": "📈 Розподіл шкоди:",
        "healing": "💚 Підтримка та зцілення:",
        "equipment": "🛡️ Екіпіровка",
        "killer_gear": "⚔️ Спорядження вбивці",
        "victim_gear": "💀 Спорядження жертви",
        "weapon": "Зброя",
        "armor": "Броня",
        "shoes": "Взуття",
        "head": "Шолом",
        "cape": "Плащ",
        "mount": "Маунт",
        "ip": "IP",
        "big_kill_alert": "🔥💀 ЕПІЧНЕ ВБИВСТВО! Fame: {fame:,} 🔥",
        "open_killboard": "🔗 Відкрити на Кілборді",
        "daily_report_title": "📊 Щоденний звіт гільдії",
        "weekly_report": "тижневий",
        "kills_count": "⚔️ Вбивств",
        "deaths_count": "💀 Смертей",
        "guild_events_found": "🎯 Подій гільдії",
        "top_killers": "🏆 Топ кілери",
        "scanned_events": "📡 Проскановано подій",
        "lang_set": "✅ Мова бота змінена на: **Українська** 🇺🇦",
    },
    "ru": {
        "kill_title": "☠️ НОВОЕ УБИЙСТВО ГИЛЬДИИ",
        "death_title": "💀 ПОТЕРЯ В БОЮ (СМЕРТЬ)",
        "assist_title": "🤝 АССИСТ ГИЛЬДИИ В УБИЙСТВЕ",
        "killer": "⚔️ Убийца",
        "victim": "💀 Жертва",
        "fame": "✨ Слава (Fame)",
        "no_guild": "Без гильдии",
        "unknown": "Неизвестно",
        "damage": "📈 Распределение урона:",
        "healing": "💚 Поддержка и исцеление:",
        "equipment": "🛡️ Экипировка",
        "killer_gear": "⚔️ Снаряжение убийцы",
        "victim_gear": "💀 Снаряжение жертвы",
        "weapon": "Оружие",
        "armor": "Броня",
        "shoes": "Обувь",
        "head": "Шлем",
        "cape": "Плащ",
        "mount": "Маунт",
        "ip": "IP",
        "big_kill_alert": "🔥💀 ЭПИЧЕСКОЕ УБИЙСТВО! Fame: {fame:,} 🔥",
        "open_killboard": "🔗 Открыть на Килборде",
        "daily_report_title": "📊 Ежедневный отчёт гильдии",
        "weekly_report": "недельный",
        "kills_count": "⚔️ Убийств",
        "deaths_count": "💀 Смертей",
        "guild_events_found": "🎯 Событий гильдии",
        "top_killers": "🏆 Топ киллеры",
        "scanned_events": "📡 Просканировано событий",
        "lang_set": "✅ Язык бота изменён на: **Русский** 🇷🇺",
    },
    "en": {
        "kill_title": "☠️ NEW GUILD KILL",
        "death_title": "💀 GUILD MEMBER DEATH",
        "assist_title": "🤝 GUILD ASSIST IN KILL",
        "killer": "⚔️ Killer",
        "victim": "💀 Victim",
        "fame": "✨ Kill Fame",
        "no_guild": "No guild",
        "unknown": "Unknown",
        "damage": "📈 Damage breakdown:",
        "healing": "💚 Support & healing:",
        "equipment": "🛡️ Equipment",
        "killer_gear": "⚔️ Killer's gear",
        "victim_gear": "💀 Victim's gear",
        "weapon": "Weapon",
        "armor": "Armor",
        "shoes": "Shoes",
        "head": "Helmet",
        "cape": "Cape",
        "mount": "Mount",
        "ip": "IP",
        "big_kill_alert": "🔥💀 EPIC KILL! Fame: {fame:,} 🔥",
        "open_killboard": "🔗 Open on Killboard",
        "daily_report_title": "📊 Daily Guild Report",
        "weekly_report": "weekly",
        "kills_count": "⚔️ Kills",
        "deaths_count": "💀 Deaths",
        "guild_events_found": "🎯 Guild events",
        "top_killers": "🏆 Top killers",
        "scanned_events": "📡 Events scanned",
        "lang_set": "✅ Bot language changed to: **English** 🇬🇧",
    }
}

# Поточна мова (за замовчуванням UA)
_current_lang = "ua"

def t(key, **kwargs):
    """Отримати переклад за ключем"""
    text = TRANSLATIONS.get(_current_lang, TRANSLATIONS["ua"]).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

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
    thread = Thread(target=run_server)
    thread.daemon = True
    thread.start()
    logger.info("🌐 [UPTIME] Внутрішній веб-сервер запущено на порту 10000")

# ==========================================
# ⚙️ ІНІЦІАЛІЗАЦІЯ ТА НАЛАШТУВАННЯ БОТА
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
BIG_KILL_FAME = int(os.getenv("BIG_KILL_FAME", "100000"))
BIG_KILL_ROLE_ID = int(os.getenv("BIG_KILL_ROLE_ID", "0"))

logger.info("=" * 50)
logger.info("⚙️  [INIT] Завантаження конфігурації...")
logger.info(f"⚙️  [INIT] GUILD_ID: {GUILD_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] BIG_KILL_FAME поріг: {BIG_KILL_FAME:,}")
logger.info(f"⚙️  [INIT] BIG_KILL_ROLE_ID: {BIG_KILL_ROLE_ID or 'Не налаштовано (пінг @everyone)'}")

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

# Лічильники для статистики та щоденного звіту
_cycle_count = 0
_total_events_scanned = 0
_total_guild_events = 0
_daily_kills = 0
_daily_deaths = 0
_daily_assists = 0
_daily_fame = 0
_daily_top_killers = {}  # {player_name: fame}

# ==========================================
# 🛡️ УТИЛІТА: ФОРМАТУВАННЯ ЕКІПІРОВКИ
# ==========================================
def _format_item_name(item_type):
    """Конвертує внутрішню назву предмету в читабельну"""
    if not item_type:
        return "—"
    # T4_2H_BOW_KEEPER@3 -> T4 Keeper Bow (Enchant 3)
    parts = item_type.split("@")
    name = parts[0]
    enchant = parts[1] if len(parts) > 1 else ""
    
    # Видаляємо технічні префікси
    name = name.replace("_", " ")
    # Видаляємо "2H " та "MAIN " та "OFF "
    for prefix in ["2H ", "MAIN ", "OFF "]:
        name = name.replace(prefix, "")
    
    enchant_str = f" .{enchant}" if enchant and enchant != "0" else ""
    return f"`{name}{enchant_str}`"


def _get_equipment_text(equipment):
    """Формує текст екіпіровки з об'єкта Equipment"""
    if not equipment or not isinstance(equipment, dict):
        return "—"
    
    slots = {
        "MainHand": t("weapon"),
        "Armor": t("armor"),
        "Head": t("head"),
        "Shoes": t("shoes"),
        "Cape": t("cape"),
        "Mount": t("mount"),
    }
    
    lines = []
    for slot_key, slot_name in slots.items():
        item = equipment.get(slot_key)
        if item and isinstance(item, dict) and item.get("Type"):
            lines.append(f"• **{slot_name}:** {_format_item_name(item['Type'])}")
    
    return "\n".join(lines) if lines else "—"


# ==========================================
# 🧾 ФОРМАТ EMBED-ПОВІДОМЛЕНЬ (з екіпіровкою)
# ==========================================
def create_battle_embed(event, title, color_hex):
    """Генерує детальну картку бою з екіпіровкою та посиланнями"""
    event_id = event.get("EventId", 0)
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    fame = event.get("TotalVictimKillFame", 0)
    
    killer_name = killer.get('Name') or t("unknown")
    killer_guild = killer.get('GuildName') or t("no_guild")
    victim_name = victim.get('Name') or t("unknown")
    victim_guild = victim.get('GuildName') or t("no_guild")
    
    killer_ip = killer.get('AverageItemPower', 0)
    victim_ip = victim.get('AverageItemPower', 0)
    
    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"
    
    embed = discord.Embed(
        title=title, 
        url=killboard_url, 
        color=color_hex,
        description=f"{t('open_killboard')}({killboard_url})"
    )
    
    embed.add_field(
        name=t("killer"), 
        value=f"**{killer_name}**\n`[{killer_guild}]`\n{t('ip')}: **{killer_ip:.0f}**", 
        inline=True
    )
    embed.add_field(
        name=t("victim"), 
        value=f"**{victim_name}**\n`[{victim_guild}]`\n{t('ip')}: **{victim_ip:.0f}**", 
        inline=True
    )
    embed.add_field(name=t("fame"), value=f"🏆 **{fame:,}**", inline=False)
    
    # Екіпіровка вбивці
    killer_eq = killer.get("Equipment")
    if killer_eq:
        eq_text = _get_equipment_text(killer_eq)
        if eq_text != "—":
            embed.add_field(name=t("killer_gear"), value=eq_text, inline=True)
    
    # Екіпіровка жертви
    victim_eq = victim.get("Equipment")
    if victim_eq:
        eq_text = _get_equipment_text(victim_eq)
        if eq_text != "—":
            embed.add_field(name=t("victim_gear"), value=eq_text, inline=True)
    
    # Учасники
    participants = event.get("Participants") or []
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name") or t("unknown")
            guild = p.get("GuildName") or t("no_guild")
            dmg = p.get("DamageDone", 0)
            heal = p.get("SupportValue", 0)
            
            if dmg > 0:
                damage_list.append(f"• **{name}** `[{guild}]`: {dmg:,} DMG")
            if heal > 0:
                heal_list.append(f"• **{name}** `[{guild}]`: {heal:,} HEAL")
        
        if damage_list:
            embed.add_field(name=t("damage"), value="\n".join(damage_list[:5]), inline=False)
        if heal_list:
            embed.add_field(name=t("healing"), value="\n".join(heal_list[:5]), inline=False)
            
    embed.set_footer(text=f"ID: {event_id} | Dev: EvilHIMARS")
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
        logger.info(f"🧹 [КЕШ] Очистка ({len(PROCESSED_EVENTS)} записів)...")
        PROCESSED_EVENTS.clear()
        
    PROCESSED_EVENTS.add(event_id)
    return True

async def dispatch_event(event, result_type, kill_ch, death_ch):
    """Відправка події в потрібний канал + пінг при великому кілі"""
    global _daily_kills, _daily_deaths, _daily_assists, _daily_fame, _daily_top_killers
    
    event_id = event.get("EventId")
    killer_name = (event.get("Killer") or {}).get("Name", "?")
    victim_name = (event.get("Victim") or {}).get("Name", "?")
    fame = event.get("TotalVictimKillFame", 0)
    
    # Статистика для щоденного звіту
    _daily_fame += fame

    try:
        if result_type == "kill":
            _daily_kills += 1
            _daily_top_killers[killer_name] = _daily_top_killers.get(killer_name, 0) + fame
            embed = create_battle_embed(event, t("kill_title"), 0x2ecc71)
            if kill_ch: 
                # Пінг при великому кілі
                if fame >= BIG_KILL_FAME:
                    ping_text = _get_ping_text(kill_ch)
                    await kill_ch.send(
                        content=f"{ping_text}\n{t('big_kill_alert', fame=fame)}",
                        embed=embed
                    )
                else:
                    await kill_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Вбивство #{event_id}: {killer_name} вбив {victim_name} | Fame: {fame:,}")
                
        elif result_type == "death":
            _daily_deaths += 1
            embed = create_battle_embed(event, t("death_title"), 0xe74c3c)
            if death_ch: 
                await death_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Смерть #{event_id}: {victim_name} загинув від {killer_name} | Fame: {fame:,}")
                
        elif result_type == "assist":
            _daily_assists += 1
            _daily_top_killers[killer_name] = _daily_top_killers.get(killer_name, 0) + fame
            embed = create_battle_embed(event, t("assist_title"), 0x3498db)
            if kill_ch: 
                if fame >= BIG_KILL_FAME:
                    ping_text = _get_ping_text(kill_ch)
                    await kill_ch.send(
                        content=f"{ping_text}\n{t('big_kill_alert', fame=fame)}",
                        embed=embed
                    )
                else:
                    await kill_ch.send(embed=embed)
                logger.info(f"📤 [ВІДПРАВКА] Асист #{event_id}: допомога у вбивстві {victim_name} | Fame: {fame:,}")
    except Exception as dispatch_err:
        logger.error(f"❌ [ВІДПРАВКА] Помилка для #{event_id}: {dispatch_err}")


def _get_ping_text(channel):
    """Генерує текст пінгу: роль якщо налаштовано, інакше @everyone"""
    if BIG_KILL_ROLE_ID:
        return f"<@&{BIG_KILL_ROLE_ID}>"
    return "@everyone"

# ==========================================
# 🔁 АВТОМАТИЧНИЙ МОНІТОРИНГ 24/7
# ==========================================
async def monitor_loop():
    """Головний цикл моніторингу"""
    global _cycle_count, _total_events_scanned, _total_guild_events

    await bot.wait_until_ready()
    
    kill_channel = bot.get_channel(KILL_CHANNEL_ID)
    death_channel = bot.get_channel(DEATH_CHANNEL_ID)

    logger.info("=" * 50)
    logger.info("🚀 [МОНІТОР] Запуск фонового моніторингу Albion API")
    logger.info(f"🚀 [МОНІТОР] Канал вбивств: {'✅ ' + kill_channel.name if kill_channel else '❌ НЕ ЗНАЙДЕНО'}")
    logger.info(f"🚀 [МОНІТОР] Канал смертей: {'✅ ' + death_channel.name if death_channel else '❌ НЕ ЗНАЙДЕНО'}")
    logger.info(f"🚀 [МОНІТОР] Інтервал: 30 сек | Ліміт: 51 | Пінг при fame >= {BIG_KILL_FAME:,}")
    logger.info("=" * 50)

    # Тестовий запит
    logger.info("🔌 [МОНІТОР] Підключення до серверів Albion Online (Europe Gateway)...")
    test_events = await get_events(limit=5)
    if test_events and isinstance(test_events, list):
        logger.info(f"✅ [МОНІТОР] З'єднання успішне! Отримано {len(test_events)} тестових подій")
        logger.info(f"✅ [МОНІТОР] Останній EventId: {test_events[0].get('EventId', '?')}")
    else:
        logger.warning("⚠️  [МОНІТОР] Порожня відповідь. Можливо сервер перевантажений.")

    logger.info("🔄 [МОНІТОР] Починаю безперервний моніторинг...")

    while not bot.is_closed():
        _cycle_count += 1
        try:
            logger.info(f"📡 [ЦИКЛ #{_cycle_count}] Запит до Albion API (limit=51)...")
            events = await get_events(limit=51)
            
            if not events or not isinstance(events, list):
                logger.warning(f"⚠️  [ЦИКЛ #{_cycle_count}] Порожній список. Наступна спроба через 30 сек.")
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
                f"📊 [ЦИКЛ #{_cycle_count}] Отримано {len(events)} | "
                f"нових: {new_events_count} | дублікатів: {duplicates_count} | "
                f"гільдія: {guild_events_in_cycle} | кеш: {len(PROCESSED_EVENTS)}"
            )

            if guild_events_in_cycle > 0:
                logger.info(f"🎯 [ЦИКЛ #{_cycle_count}] Знайдено {guild_events_in_cycle} подій гільдії!")
            
            if _cycle_count % 10 == 0:
                logger.info(
                    f"📈 [СТАТИСТИКА] {_cycle_count} циклів | "
                    f"{_total_events_scanned} подій | "
                    f"{_total_guild_events} гільдії | "
                    f"кеш: {len(PROCESSED_EVENTS)}/{MAX_CACHE_SIZE}"
                )
                
        except asyncio.CancelledError:
            logger.info("🛑 [МОНІТОР] Зупинено.")
            break
        except Exception as e:
            logger.error(f"❌ [ЦИКЛ #{_cycle_count}] Збій: {type(e).__name__}: {e}")
            
        await asyncio.sleep(30)

# ==========================================
# 📅 ЩОДЕННИЙ ЗВІТ О 22:00 UTC
# ==========================================
async def daily_report_loop():
    """Надсилає щоденний звіт о 22:00 UTC"""
    global _daily_kills, _daily_deaths, _daily_assists, _daily_fame, _daily_top_killers
    
    await bot.wait_until_ready()
    logger.info("📅 [ЗВІТ] Запущено планувальник щоденних звітів (22:00 UTC)")
    
    while not bot.is_closed():
        now = datetime.now(timezone.utc)
        # Розрахунок часу до 22:00 UTC
        target = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        logger.info(f"📅 [ЗВІТ] Наступний звіт через {wait_seconds/3600:.1f} годин")
        
        await asyncio.sleep(wait_seconds)
        
        # Час звіту!
        try:
            kill_channel = bot.get_channel(KILL_CHANNEL_ID)
            if not kill_channel:
                logger.warning("📅 [ЗВІТ] Канал вбивств не знайдено")
                continue
            
            embed = discord.Embed(
                title=t("daily_report_title"),
                description=f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y')}",
                color=0xf1c40f
            )
            
            embed.add_field(name=t("kills_count"), value=f"**{_daily_kills}**", inline=True)
            embed.add_field(name=t("deaths_count"), value=f"**{_daily_deaths}**", inline=True)
            embed.add_field(name="🤝 Асисти", value=f"**{_daily_assists}**", inline=True)
            embed.add_field(name=t("fame") + " за день", value=f"🏆 **{_daily_fame:,}**", inline=False)
            embed.add_field(name=t("scanned_events"), value=f"`{_total_events_scanned:,}`", inline=True)
            embed.add_field(name=t("guild_events_found"), value=f"`{_total_guild_events}`", inline=True)
            
            # Топ кілери за день
            if _daily_top_killers:
                sorted_killers = sorted(_daily_top_killers.items(), key=lambda x: x[1], reverse=True)[:5]
                top_text = "\n".join([
                    f"**{i+1}.** {name} — {fame:,} fame" 
                    for i, (name, fame) in enumerate(sorted_killers)
                ])
                embed.add_field(name=t("top_killers") + " (за день)", value=top_text, inline=False)
            
            # Топ з API
            api_top = await get_guild_top(GUILD_ID, range_type="week", limit=5)
            if api_top:
                api_top_text = []
                for i, event in enumerate(api_top[:5]):
                    k = (event.get("Killer") or {}).get("Name", "?")
                    v = (event.get("Victim") or {}).get("Name", "?")
                    f_val = event.get("TotalVictimKillFame", 0)
                    api_top_text.append(f"**{i+1}.** {k} ☠️ {v} — {f_val:,} fame")
                embed.add_field(
                    name=t("top_killers") + f" ({t('weekly_report')})", 
                    value="\n".join(api_top_text), 
                    inline=False
                )
            
            embed.set_footer(text="Автоматичний звіт | Dev: EvilHIMARS")
            await kill_channel.send(embed=embed)
            logger.info(f"📅 [ЗВІТ] Надіслано: kills={_daily_kills}, deaths={_daily_deaths}, fame={_daily_fame:,}")
            
            # Скидання лічильників
            _daily_kills = 0
            _daily_deaths = 0
            _daily_assists = 0
            _daily_fame = 0
            _daily_top_killers = {}
            
        except Exception as e:
            logger.error(f"❌ [ЗВІТ] Помилка: {e}")

# ==========================================
# 📋 КОМАНДИ БОТА
# ==========================================
@bot.event
async def on_ready():
    logger.info("=" * 50)
    logger.info(f"✅ [DISCORD] Бот: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"✅ [DISCORD] Серверів: {len(bot.guilds)}")
    for g in bot.guilds:
        logger.info(f"   📌 {g.name} (ID: {g.id}, учасників: {g.member_count})")
    logger.info("=" * 50)
    
    cmds = [
        "!info", "!scan", "!scanlive", "!lastkills", "!checkapi",
        "!guild", "!status", "!top", "!player", "!battleboard", "!lang", "!help"
    ]
    logger.info(f"🔧 [DISCORD] Команди: {', '.join(cmds)}")
    
    bot.loop.create_task(monitor_loop())
    bot.loop.create_task(daily_report_loop())

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
            
            embed = discord.Embed(title="🌐 Статус API Albion Online", color=0x2ecc71)
            embed.add_field(name="🟢 Стан", value="Працює!", inline=False)
            embed.add_field(name="📊 Остання подія", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час (UTC)", value=f"`{timestamp}`", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("🟡 **API повернуло порожній масив.**")
    except Exception as e:
        await ctx.send(f"🔴 **Помилка:** `{str(e)}`")

@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію"""
    logger.info(f"🔧 [КОМАНДА] !guild від {ctx.author}")
    data = await get_guild_info(GUILD_ID)
    if not data:
        await ctx.send("❌ Не вдалося отримати дані гільдії.")
        return
    
    guild_name = data.get('Name', '?')
    embed = discord.Embed(title=f"🏰 {guild_name}", color=0x3498db)
    embed.add_field(name="👑 Лідер", value=data.get('FounderName', '—'), inline=True)
    embed.add_field(name="👥 Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="🤝 Альянс", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', '—')}", inline=False)
    embed.add_field(name="⚔️ Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    
    kill_ch = bot.get_channel(KILL_CHANNEL_ID)
    death_ch = bot.get_channel(DEATH_CHANNEL_ID)
    embed.add_field(
        name="📺 Канали", 
        value=f"⚔️ {kill_ch.mention if kill_ch else '—'}\n💀 {death_ch.mention if death_ch else '—'}", 
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def status(ctx):
    """Статус моніторингу"""
    logger.info(f"🔧 [КОМАНДА] !status від {ctx.author}")
    
    embed = discord.Embed(title="📊 Статус моніторингу", color=0x9b59b6)
    embed.add_field(name="🔄 Циклів", value=f"`{_cycle_count}`", inline=True)
    embed.add_field(name="📡 Подій", value=f"`{_total_events_scanned:,}`", inline=True)
    embed.add_field(name="🎯 Гільдія", value=f"`{_total_guild_events}`", inline=True)
    embed.add_field(name="🧠 Кеш", value=f"`{len(PROCESSED_EVENTS)}/{MAX_CACHE_SIZE}`", inline=True)
    embed.add_field(name="⏱️ Інтервал", value="`30 сек`", inline=True)
    embed.add_field(name="🔔 Пінг поріг", value=f"`{BIG_KILL_FAME:,} fame`", inline=True)
    embed.add_field(name="🌐 Мова", value=f"`{_current_lang.upper()}`", inline=True)
    
    # Денна статистика
    embed.add_field(
        name="📅 Сьогодні", 
        value=f"⚔️ {_daily_kills} kills | 💀 {_daily_deaths} deaths | 🤝 {_daily_assists} assists\n🏆 Fame: {_daily_fame:,}", 
        inline=False
    )
    embed.set_footer(text=f"GUILD_ID: {GUILD_ID}")
    await ctx.send(embed=embed)

@bot.command()
async def top(ctx, period: str = "week"):
    """Топ-10 кілерів гільдії за період"""
    logger.info(f"🔧 [КОМАНДА] !top (period={period}) від {ctx.author}")
    
    valid_periods = ["week", "month", "lastWeek", "lastMonth"]
    if period not in valid_periods:
        await ctx.send(f"❌ Невідомий період. Доступні: {', '.join(valid_periods)}")
        return
    
    status_msg = await ctx.send(f"🔍 Завантажую топ кілерів за **{period}**...")
    
    top_events = await get_guild_top(GUILD_ID, range_type=period, limit=10)
    if not top_events:
        await status_msg.edit(content="ℹ️ Немає даних за цей період.")
        return
    
    embed = discord.Embed(
        title=f"🏆 Топ-10 кілерів гільдії ({period})",
        color=0xf1c40f
    )
    
    for i, event in enumerate(top_events[:10]):
        killer = (event.get("Killer") or {}).get("Name", "?")
        victim = (event.get("Victim") or {}).get("Name", "?")
        k_guild = (event.get("Killer") or {}).get("GuildName") or "—"
        v_guild = (event.get("Victim") or {}).get("GuildName") or "—"
        fame = event.get("TotalVictimKillFame", 0)
        event_id = event.get("EventId", "?")
        ip = (event.get("Killer") or {}).get("AverageItemPower", 0)
        
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
        
        embed.add_field(
            name=f"{medal} {killer} ☠️ {victim}",
            value=f"Fame: **{fame:,}** | IP: {ip:.0f}\n`[{k_guild}]` vs `[{v_guild}]`\n[Killboard](https://albiononline.com/killboard/kill/{event_id})",
            inline=False
        )
    
    embed.set_footer(text=f"!top week | !top month | !top lastWeek | !top lastMonth")
    await status_msg.edit(content=None, embed=embed)

@bot.command()
async def player(ctx, *, name: str = None):
    """Статистика гравця: K/D, fame, останні бої"""
    if not name:
        await ctx.send("❌ Вкажи ім'я гравця: `!player EvilHIMARS`")
        return
    
    logger.info(f"🔧 [КОМАНДА] !player {name} від {ctx.author}")
    status_msg = await ctx.send(f"🔍 Шукаю гравця **{name}**...")
    
    # Пошук гравця
    results = await search_player(name)
    if not results:
        await status_msg.edit(content=f"❌ Гравця **{name}** не знайдено в Albion Online.")
        return
    
    # Беремо першого з результатів
    player_data = results[0]
    player_id = player_data.get("Id")
    player_name = player_data.get("Name", "?")
    
    # Детальна інфо
    info = await get_player_info(player_id)
    if not info:
        await status_msg.edit(content=f"❌ Не вдалося отримати дані гравця **{player_name}**.")
        return
    
    kill_fame = info.get("KillFame", 0)
    death_fame = info.get("DeathFame", 0)
    fame_ratio = info.get("FameRatio", 0)
    guild_name = info.get("GuildName") or t("no_guild")
    alliance = info.get("AllianceName") or "—"
    
    # PvE статистика
    lifetime = info.get("LifetimeStatistics", {})
    pve = lifetime.get("PvE", {})
    pve_total = pve.get("Total", 0)
    
    embed = discord.Embed(
        title=f"👤 {player_name}",
        url=f"https://albiononline.com/killboard/player/{player_id}",
        color=0x3498db
    )
    
    embed.add_field(name="🏰 Гільдія", value=guild_name, inline=True)
    embed.add_field(name="🤝 Альянс", value=alliance, inline=True)
    embed.add_field(name="📊 Fame Ratio", value=f"**{fame_ratio:.2f}**", inline=True)
    embed.add_field(name="⚔️ Kill Fame", value=f"**{kill_fame:,}**", inline=True)
    embed.add_field(name="💀 Death Fame", value=f"**{death_fame:,}**", inline=True)
    embed.add_field(name="🌿 PvE Fame", value=f"**{pve_total:,}**", inline=True)
    
    # Останні кіли
    kills = await get_player_kills(player_id, limit=3)
    if kills:
        kills_text = []
        for k in kills[:3]:
            v_name = (k.get("Victim") or {}).get("Name", "?")
            k_fame = k.get("TotalVictimKillFame", 0)
            kills_text.append(f"☠️ {v_name} — {k_fame:,} fame")
        embed.add_field(name="🗡️ Останні кіли", value="\n".join(kills_text), inline=False)
    
    # Останні смерті
    deaths = await get_player_deaths(player_id, limit=3)
    if deaths:
        deaths_text = []
        for d in deaths[:3]:
            k_name = (d.get("Killer") or {}).get("Name", "?")
            d_fame = d.get("TotalVictimKillFame", 0)
            deaths_text.append(f"💀 від {k_name} — {d_fame:,} fame")
        embed.add_field(name="☠️ Останні смерті", value="\n".join(deaths_text), inline=False)
    
    # Поточне спорядження
    equipment = info.get("Equipment")
    if equipment:
        eq_text = _get_equipment_text(equipment)
        if eq_text != "—":
            embed.add_field(name=t("equipment"), value=eq_text, inline=False)
    
    embed.set_footer(text=f"ID: {player_id}")
    await status_msg.edit(content=None, embed=embed)

@bot.command()
async def battleboard(ctx, event_id: int = None):
    """Деталі конкретного бою за EventId"""
    if not event_id:
        await ctx.send("❌ Вкажи ID бою: `!battleboard 384948794`")
        return
    
    logger.info(f"🔧 [КОМАНДА] !battleboard {event_id} від {ctx.author}")
    status_msg = await ctx.send(f"🔍 Завантажую деталі бою **#{event_id}**...")
    
    event = await get_event_details(event_id)
    if not event:
        await status_msg.edit(content=f"❌ Бій **#{event_id}** не знайдено.")
        return
    
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    fame = event.get("TotalVictimKillFame", 0)
    timestamp = event.get("TimeStamp", "?")
    participants = event.get("Participants") or []
    num_participants = event.get("numberOfParticipants", len(participants))
    group_size = event.get("groupMemberCount", 1)
    
    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"
    
    embed = discord.Embed(
        title=f"⚔️ Бій #{event_id}",
        url=killboard_url,
        color=0xe67e22,
        description=f"[{t('open_killboard')}]({killboard_url})"
    )
    
    # Основна інфа
    k_name = killer.get("Name", "?")
    k_guild = killer.get("GuildName") or t("no_guild")
    k_alliance = killer.get("AllianceName") or "—"
    k_ip = killer.get("AverageItemPower", 0)
    
    v_name = victim.get("Name", "?")
    v_guild = victim.get("GuildName") or t("no_guild")
    v_alliance = victim.get("AllianceName") or "—"
    v_ip = victim.get("AverageItemPower", 0)
    
    embed.add_field(
        name=t("killer"),
        value=f"**{k_name}**\n`[{k_guild}]` `{k_alliance}`\nIP: **{k_ip:.0f}**",
        inline=True
    )
    embed.add_field(
        name=t("victim"),
        value=f"**{v_name}**\n`[{v_guild}]` `{v_alliance}`\nIP: **{v_ip:.0f}**",
        inline=True
    )
    
    embed.add_field(name=t("fame"), value=f"🏆 **{fame:,}**", inline=False)
    embed.add_field(name="👥 Учасників", value=f"**{num_participants}** (група: {group_size})", inline=True)
    embed.add_field(name="🕒 Час (UTC)", value=f"`{timestamp[:19]}`", inline=True)
    
    # Екіпіровка
    k_eq = killer.get("Equipment")
    if k_eq:
        eq_text = _get_equipment_text(k_eq)
        if eq_text != "—":
            embed.add_field(name=t("killer_gear"), value=eq_text, inline=True)
    
    v_eq = victim.get("Equipment")
    if v_eq:
        eq_text = _get_equipment_text(v_eq)
        if eq_text != "—":
            embed.add_field(name=t("victim_gear"), value=eq_text, inline=True)
    
    # Учасники з DMG/HEAL
    if participants:
        damage_list = []
        for p in sorted(participants, key=lambda x: x.get("DamageDone", 0), reverse=True)[:8]:
            p_name = p.get("Name", "?")
            p_guild = p.get("GuildName") or "—"
            dmg = p.get("DamageDone", 0)
            heal = p.get("SupportValue", 0)
            p_ip = p.get("AverageItemPower", 0)
            if dmg > 0 or heal > 0:
                damage_list.append(f"• **{p_name}** `[{p_guild}]` IP:{p_ip:.0f} — {dmg:,} DMG / {heal:,} HEAL")
        
        if damage_list:
            embed.add_field(name="📊 Учасники бою", value="\n".join(damage_list[:8]), inline=False)
    
    embed.set_footer(text=f"Dev: EvilHIMARS")
    await status_msg.edit(content=None, embed=embed)

@bot.command()
async def scan(ctx):
    """Глибоке сканування 51 останньої подій"""
    logger.info(f"🔧 [КОМАНДА] !scan від {ctx.author}")
    status_msg = await ctx.send("🔍 **Глибоке сканування:** перевіряю 51 останню подій...")

    try:
        events = await get_events(limit=51)
        if not events or not isinstance(events, list):
            await status_msg.edit(content="🟡 API повернув порожній список.")
            return

        found_kills = 0
        found_deaths = 0
        found_assists = 0
        seen_guilds = set()

        for event in events:
            k_guild = (event.get("Killer") or {}).get("GuildName")
            v_guild = (event.get("Victim") or {}).get("GuildName")
            if k_guild: seen_guilds.add(k_guild)
            if v_guild: seen_guilds.add(v_guild)

            result = is_guild_kill(event)
            if not result:
                continue

            if result == "kill":
                found_kills += 1
                embed = create_battle_embed(event, "☠️ ЗНАЙДЕНО ВБИВСТВО (СКАН)", 0x2ecc71)
            elif result == "death":
                found_deaths += 1
                embed = create_battle_embed(event, "💀 ЗНАЙДЕНО СМЕРТЬ (СКАН)", 0xe74c3c)
            elif result == "assist":
                found_assists += 1
                embed = create_battle_embed(event, "🤝 ЗНАЙДЕНО АСИСТ (СКАН)", 0x3498db)
            else:
                continue
            await ctx.send(embed=embed)

        total_found = found_kills + found_deaths + found_assists
        if total_found > 0:
            await status_msg.edit(
                content=f"✅ Знайдено **{total_found}** подій: ⚔️ {found_kills} | 💀 {found_deaths} | 🤝 {found_assists}"
            )
        else:
            sample = ", ".join([f"`{g}`" for g in list(seen_guilds)[:5]]) if seen_guilds else "—"
            await status_msg.edit(
                content=f"ℹ️ Проскановано **{len(events)}** подій. Подій гільдії не знайдено.\nГільдії у логах: {sample}"
            )
    except Exception as e:
        await status_msg.edit(content=f"🔴 **Помилка:** `{str(e)}`")

@bot.command()
async def scanlive(ctx):
    """Швидкий скан 20 подій"""
    logger.info(f"🔧 [КОМАНДА] !scanlive від {ctx.author}")
    events = await get_events(limit=20)
    if not events:
        await ctx.send("❌ API не відповіло.")
        return
    
    for event in events:
        killer = (event.get('Killer') or {}).get('Name', '?')
        victim = (event.get('Victim') or {}).get('Name', '?')
        fame = event.get('TotalVictimKillFame', 0)
        event_id = event.get('EventId', '?')
        embed = discord.Embed(title=f"⚔️ #{event_id}", color=discord.Color.blue())
        embed.add_field(name="Killer", value=killer, inline=True)
        embed.add_field(name="Victim", value=victim, inline=True)
        embed.add_field(name="Fame", value=f"{fame:,}", inline=True)
        await ctx.send(embed=embed)

@bot.command()
async def lastkills(ctx, count: int = 10):
    """Останні кіли зі світового логу"""
    logger.info(f"🔧 [КОМАНДА] !lastkills ({count}) від {ctx.author}")
    count = max(1, min(count, 20))

    try:
        events = await get_events(limit=count)
        if not events:
            await ctx.send("🟡 Порожній список.")
            return

        await ctx.send(f"🌍 **Останні {len(events)} подій:**")
        for event in events[:count]:
            killer = (event.get("Killer") or {}).get("Name", "?")
            k_guild = (event.get("Killer") or {}).get("GuildName") or "—"
            victim = (event.get("Victim") or {}).get("Name", "?")
            v_guild = (event.get("Victim") or {}).get("GuildName") or "—"
            fame = event.get("TotalVictimKillFame", 0)
            eid = event.get("EventId", "?")

            embed = discord.Embed(
                title=f"🌐 #{eid}",
                url=f"https://albiononline.com/killboard/kill/{eid}",
                color=0x95a5a6
            )
            embed.add_field(name="⚔️", value=f"**{killer}** `[{k_guild}]`", inline=True)
            embed.add_field(name="💀", value=f"**{victim}** `[{v_guild}]`", inline=True)
            embed.add_field(name="✨", value=f"**{fame:,}**", inline=True)
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"🔴 **Помилка:** `{str(e)}`")

@bot.command()
async def lang(ctx, language: str = None):
    """Перемикач мови: !lang ua / !lang ru / !lang en"""
    global _current_lang
    
    if not language or language.lower() not in TRANSLATIONS:
        embed = discord.Embed(title="🌐 Мова / Language / Язык", color=0xf39c12)
        embed.add_field(name="🇺🇦 Українська", value="`!lang ua`", inline=True)
        embed.add_field(name="🇷🇺 Русский", value="`!lang ru`", inline=True)
        embed.add_field(name="🇬🇧 English", value="`!lang en`", inline=True)
        embed.add_field(name="Поточна / Current", value=f"**{_current_lang.upper()}**", inline=False)
        await ctx.send(embed=embed)
        return
    
    _current_lang = language.lower()
    logger.info(f"🌐 [МОВА] Змінено на: {_current_lang.upper()} (від {ctx.author})")
    await ctx.send(t("lang_set"))

@bot.command()
async def info(ctx):
    """Повний список команд"""
    logger.info(f"🔧 [КОМАНДА] !info від {ctx.author}")
    embed = discord.Embed(
        title="📖 x E C L I P S E x — Killboard Bot",
        description="Автоматичний моніторинг Albion API кожні 30 секунд. Кіли, смерті, асисти гільдії відправляються в канали Discord.",
        color=0xf39c12
    )

    embed.add_field(name="🔍 !scan", value="Глибокий скан 51 подій — пошук кілів/смертей/асистів гільдії з екіпіровкою", inline=False)
    embed.add_field(name="⚔️ !scanlive", value="Швидкий скан 20 подій (компактний)", inline=False)
    embed.add_field(name="🌍 !lastkills [n]", value="Останні n кілів зі світового логу (макс 20). Приклад: `!lastkills 5`", inline=False)
    embed.add_field(name="🏆 !top [період]", value="Топ-10 кілерів гільдії. Періоди: `week`, `month`, `lastWeek`, `lastMonth`", inline=False)
    embed.add_field(name="👤 !player [ім'я]", value="Статистика гравця: K/D fame, ratio, PvE, останні бої, екіпіровка. Приклад: `!player EvilHIMARS`", inline=False)
    embed.add_field(name="⚔️ !battleboard [ID]", value="Детальна картка конкретного бою з екіпіровкою всіх учасників. Приклад: `!battleboard 384948794`", inline=False)
    embed.add_field(name="🌐 !checkapi", value="Перевірка з'єднання з API Albion Online", inline=False)
    embed.add_field(name="🏰 !guild", value="Статистика гільдії: учасники, fame, альянс, канали", inline=False)
    embed.add_field(name="📊 !status", value="Статус моніторингу: цикли, події, кеш, денна статистика", inline=False)
    embed.add_field(name="🌐 !lang [ua/ru/en]", value="Перемикач мови для embed'ів бота", inline=False)
    embed.add_field(name="📋 !help", value="Короткий список команд", inline=False)

    embed.add_field(
        name="⚙️ Автоматичні функції",
        value="• **Моніторинг 24/7** — кожні 30 сек перевіряє 51 подію\n"
              "• **🔔 Пінг при великому кілі** — якщо fame ≥ 100,000 → пінг ролі або @everyone\n"
              "• **📅 Щоденний звіт** — о 22:00 UTC автоматичний підсумок дня\n"
              "• **🛡️ Екіпіровка** — в кожній картці бою показується спорядження\n"
              "• **🌐 Мультимова** — UA/RU/EN перемикач для всіх повідомлень",
        inline=False
    )

    embed.set_footer(text="Бот моніторить Albion API 24/7 | Dev: EvilHIMARS")
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    """Короткий список команд"""
    logger.info(f"🔧 [КОМАНДА] !help від {ctx.author}")
    embed = discord.Embed(title="📋 Команди бота x E C L I P S E x", color=0xf39c12)
    embed.add_field(name="!info", value="📖 Повний опис команд", inline=False)
    embed.add_field(name="!scan", value="🔍 Скан 51 подій — кіли/смерті гільдії", inline=False)
    embed.add_field(name="!scanlive", value="⚔️ Швидкий скан 20 подій", inline=False)
    embed.add_field(name="!lastkills [n]", value="🌍 Світовий лог (макс 20)", inline=False)
    embed.add_field(name="!top [період]", value="🏆 Топ-10 кілерів гільдії", inline=False)
    embed.add_field(name="!player [ім'я]", value="👤 Статистика гравця + K/D + екіп", inline=False)
    embed.add_field(name="!battleboard [ID]", value="⚔️ Деталі бою по EventId", inline=False)
    embed.add_field(name="!checkapi", value="🌐 Статус API Albion", inline=False)
    embed.add_field(name="!guild", value="🏰 Статистика гільдії", inline=False)
    embed.add_field(name="!status", value="📊 Статус моніторингу", inline=False)
    embed.add_field(name="!lang [ua/ru/en]", value="🌐 Зміна мови бота", inline=False)
    embed.set_footer(text="!info — детальний опис | Dev: EvilHIMARS")
    await ctx.send(embed=embed)

# Запуск
keep_alive()
bot.run(TOKEN)
