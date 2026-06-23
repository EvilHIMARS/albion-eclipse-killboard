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
from image_renderer import ImageRenderer
from render_api import RenderAPI
from cache_manager import IconCache

_icon_cache = IconCache()
_render_api = RenderAPI(_icon_cache)
_img_renderer = ImageRenderer(_render_api)

# ==========================================
# 🌐 МУЛЬТИМОВНА СИСТЕМА (UA/RU/EN)
# ==========================================
TRANSLATIONS = {
    "ua": {
        "kill_title": "⚔️ НОВЕ ВБИВСТВО ГІЛЬДІЇ",
        "death_title": "💀 ВТРАТА В БОЮ (СМЕРТЬ)",
        "assist_title": "🤝 АСИСТ ГІЛЬДІЇ У ВБИВСТВІ",
        "killer": "⚔️ Вбивця",
        "victim": "💀 Жертва",
        "fame": "✨ Слава (Fame)",
        "no_guild": "Без гільдії",
        "unknown": "Невідомо",
        "open_killboard": "🔗 Відкрити на Кілборді",
        "big_kill_alert": "🔥💀 ЕПІЧНЕ ВБИВСТВО! Fame: {fame:,} 🔥",
        "daily_report_title": "📊 Щоденний звіт гільдії",
        "weekly_report": "тижневий",
        "kills_count": "⚔️ Вбивств",
        "deaths_count": "💀 Смертей",
        "guild_events_found": "🎯 Подій гільдії",
        "top_killers": "🏆 Топ кілери",
        "scanned_events": "📡 Проскановано подій",
        "lang_set": "✅ Мова бота змінена на: **Українська** 🇺🇦",
        "scanning": "🔍 Сканую останні 51 подій...",
        "empty_api": "🟡 API повернув порожній список.",
        "found_events": "✅ Знайдено **{total}** подій: ⚔️ {kills} | 💀 {deaths} | 🤝 {assists}",
        "no_guild_events": "ℹ️ Проскановано **{total}** подій. Подій гільдії не знайдено.",
        "api_error": "🔴 Помилка API: `{error}`",
        "player_not_found": "❌ Гравця **{name}** не знайдено в Albion Online.",
        "battle_not_found": "❌ Бій **#{id}** не знайдено.",
        "invalid_period": "❌ Невідомий період. Доступні: week, month, lastWeek, lastMonth",
        "no_data_period": "ℹ️ Немає даних за цей період.",
        "loading_top": "🔍 Завантажую топ кілерів...",
        "loading_player": "🔍 Шукаю гравця...",
        "loading_battle": "🔍 Завантажую деталі бою...",
        "need_player_name": "❌ Вкажи ім'я гравця: `/player EvilHIMARS`",
        "need_battle_id": "❌ Вкажи ID бою: `/battleboard 384948794`",
    },
    "ru": {
        "kill_title": "⚔️ НОВОЕ УБИЙСТВО ГИЛЬДИИ",
        "death_title": "💀 ПОТЕРЯ В БОЮ (СМЕРТЬ)",
        "assist_title": "🤝 АССИСТ ГИЛЬДИИ В УБИЙСТВЕ",
        "killer": "⚔️ Убийца",
        "victim": "💀 Жертва",
        "fame": "✨ Слава (Fame)",
        "no_guild": "Без гильдии",
        "unknown": "Неизвестно",
        "open_killboard": "🔗 Открыть на Килборде",
        "big_kill_alert": "🔥💀 ЭПИЧЕСКОЕ УБИЙСТВО! Fame: {fame:,} 🔥",
        "daily_report_title": "📊 Ежедневный отчёт гильдии",
        "weekly_report": "недельный",
        "kills_count": "⚔️ Убийств",
        "deaths_count": "💀 Смертей",
        "guild_events_found": "🎯 Событий гильдии",
        "top_killers": "🏆 Топ киллеры",
        "scanned_events": "📡 Просканировано событий",
        "lang_set": "✅ Язык бота изменён на: **Русский** 🇷🇺",
        "scanning": "🔍 Сканирую последние 51 событий...",
        "empty_api": "🟡 API вернул пустой список.",
        "found_events": "✅ Найдено **{total}** событий: ⚔️ {kills} | 💀 {deaths} | 🤝 {assists}",
        "no_guild_events": "ℹ️ Просканировано **{total}** событий. Событий гильдии не найдено.",
        "api_error": "🔴 Ошибка API: `{error}`",
        "player_not_found": "❌ Игрок **{name}** не найден в Albion Online.",
        "battle_not_found": "❌ Бой **#{id}** не найден.",
        "invalid_period": "❌ Неизвестный период. Доступные: week, month, lastWeek, lastMonth",
        "no_data_period": "ℹ️ Нет данных за этот период.",
        "loading_top": "🔍 Загружаю топ киллеров...",
        "loading_player": "🔍 Ищу игрока...",
        "loading_battle": "🔍 Загружаю детали боя...",
        "need_player_name": "❌ Укажи имя игрока: `/player EvilHIMARS`",
        "need_battle_id": "❌ Укажи ID боя: `/battleboard 384948794`",
    },
    "en": {
        "kill_title": "⚔️ NEW GUILD KILL",
        "death_title": "💀 GUILD MEMBER DEATH",
        "assist_title": "🤝 GUILD ASSIST IN KILL",
        "killer": "⚔️ Killer",
        "victim": "💀 Victim",
        "fame": "✨ Kill Fame",
        "no_guild": "No guild",
        "unknown": "Unknown",
        "open_killboard": "🔗 Open on Killboard",
        "big_kill_alert": "🔥💀 EPIC KILL! Fame: {fame:,} 🔥",
        "daily_report_title": "📊 Daily Guild Report",
        "weekly_report": "weekly",
        "kills_count": "⚔️ Kills",
        "deaths_count": "💀 Deaths",
        "guild_events_found": "🎯 Guild events",
        "top_killers": "🏆 Top killers",
        "scanned_events": "📡 Events scanned",
        "lang_set": "✅ Bot language changed to: **English** 🇬🇧",
        "scanning": "🔍 Scanning last 51 events...",
        "empty_api": "🟡 API returned empty list.",
        "found_events": "✅ Found **{total}** events: ⚔️ {kills} | 💀 {deaths} | 🤝 {assists}",
        "no_guild_events": "ℹ️ Scanned **{total}** events. No guild events found.",
        "api_error": "🔴 API Error: `{error}`",
        "player_not_found": "❌ Player **{name}** not found in Albion Online.",
        "battle_not_found": "❌ Battle **#{id}** not found.",
        "invalid_period": "❌ Unknown period. Available: week, month, lastWeek, lastMonth",
        "no_data_period": "ℹ️ No data for this period.",
        "loading_top": "🔍 Loading top killers...",
        "loading_player": "🔍 Searching player...",
        "loading_battle": "🔍 Loading battle details...",
        "need_player_name": "❌ Enter player name: `/player EvilHIMARS`",
        "need_battle_id": "❌ Enter battle ID: `/battleboard 384948794`",
    }
}

_current_lang = "ua"

def t(key, **kwargs):
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

# --- WEB-СЕРВЕР ---
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
    logger.info("🌐 [UPTIME] Веб-сервер запущено на порту 10000")

# ==========================================
# ⚙️ КОНФІГ
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
BIG_KILL_FAME = int(os.getenv("BIG_KILL_FAME", "100000"))
BIG_KILL_ROLE_ID = int(os.getenv("BIG_KILL_ROLE_ID", "0"))

try:
    KILL_CHANNEL_ID = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL_ID = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    KILL_CHANNEL_ID = 0
    DEATH_CHANNEL_ID = 0

logger.info("=" * 50)
logger.info("⚙️  [INIT] Завантаження конфігурації...")
logger.info(f"⚙️  [INIT] GUILD_ID: {GUILD_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] BIG_KILL_FAME поріг: {BIG_KILL_FAME:,}")
logger.info(f"⚙️  [INIT] BIG_KILL_ROLE_ID: {BIG_KILL_ROLE_ID or 'Не налаштовано (пінг @everyone)'}")
logger.info(f"⚙️  [INIT] KILL_CHANNEL_ID: {KILL_CHANNEL_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] DEATH_CHANNEL_ID: {DEATH_CHANNEL_ID or '❌ НЕ ЗНАЙДЕНО'}")
logger.info(f"⚙️  [INIT] DISCORD_TOKEN: {'✅ Знайдено' if TOKEN else '❌ НЕ ЗНАЙДЕНО'}")
logger.info("=" * 50)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

PROCESSED_EVENTS = set()
MAX_CACHE_SIZE = 2000

_cycle_count = 0
_total_events_scanned = 0
_total_guild_events = 0
_daily_kills = 0
_daily_deaths = 0
_daily_assists = 0
_daily_fame = 0
_daily_top_killers = {}

# ==========================================
# 🛡️ УТИЛІТИ
# ==========================================
def _event_to_dict(event):
    return {
        "Killer": event.get("Killer", {}),
        "Victim": event.get("Victim", {}),
        "TotalVictimKillFame": event.get("TotalVictimKillFame", 0),
        "TimeStamp": event.get("TimeStamp", ""),
        "TotalDamage": event.get("TotalDamage", 0),
        "Participants": event.get("Participants", []),
        "Equipment": (event.get("Victim") or {}).get("Equipment", {}),
    }

def create_battle_embed(event, title, color_hex):
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
        description=f"**{killer_name}** `[{killer_guild}]` IP:{killer_ip:.0f} ☠️ **{victim_name}** `[{victim_guild}]` IP:{victim_ip:.0f}\n🏆 Fame: **{fame:,}**"
    )
    embed.set_image(url="attachment://killcard.png")
    embed.set_footer(text="Albion Eclipse Killboard | Dev: EvilHIMARS")

    event_dict = _event_to_dict(event)
    is_kill = "KILL" in title.upper() or "ASSIST" in title.upper() or "ВБИВСТВО" in title.upper() or "УБИЙСТВО" in title.upper() or "АСИСТ" in title.upper()
    img_buf = _img_renderer.render(event_dict, is_kill=is_kill)
    file = discord.File(img_buf, filename="killcard.png")

    return embed, file

def manage_cache(event_id):
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False
    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info(f"🧹 [КЕШ] Очистка ({len(PROCESSED_EVENTS)} записів)...")
        PROCESSED_EVENTS.clear()
    PROCESSED_EVENTS.add(event_id)
    return True

async def dispatch_event(event, result_type, kill_ch, death_ch):
    global _daily_kills, _daily_deaths, _daily_assists, _daily_fame, _daily_top_killers

    event_id = event.get("EventId")
    killer_name = (event.get("Killer") or {}).get("Name", "?")
    victim_name = (event.get("Victim") or {}).get("Name", "?")
    fame = event.get("TotalVictimKillFame", 0)

    _daily_fame += fame

    try:
        if result_type == "kill":
            _daily_kills += 1
            _daily_top_killers[killer_name] = _daily_top_killers.get(killer_name, 0) + fame
            embed, file = create_battle_embed(event, t("kill_title"), 0x2ecc71)
            if kill_ch:
                if fame >= BIG_KILL_FAME:
                    ping_text = _get_ping_text(kill_ch)
                    await kill_ch.send(content=f"{ping_text}\n{t('big_kill_alert', fame=fame)}", embed=embed, file=file)
                else:
                    await kill_ch.send(embed=embed, file=file)
                logger.info(f"📤 [ВІДПРАВКА] Вбивство #{event_id}: {killer_name} вбив {victim_name} | Fame: {fame:,}")
        elif result_type == "death":
            _daily_deaths += 1
            embed, file = create_battle_embed(event, t("death_title"), 0xe74c3c)
            if death_ch:
                await death_ch.send(embed=embed, file=file)
                logger.info(f"📤 [ВІДПРАВКА] Смерть #{event_id}: {victim_name} загинув від {killer_name} | Fame: {fame:,}")
        elif result_type == "assist":
            _daily_assists += 1
            _daily_top_killers[killer_name] = _daily_top_killers.get(killer_name, 0) + fame
            embed, file = create_battle_embed(event, t("assist_title"), 0x3498db)
            if kill_ch:
                if fame >= BIG_KILL_FAME:
                    ping_text = _get_ping_text(kill_ch)
                    await kill_ch.send(content=f"{ping_text}\n{t('big_kill_alert', fame=fame)}", embed=embed, file=file)
                else:
                    await kill_ch.send(embed=embed, file=file)
                logger.info(f"📤 [ВІДПРАВКА] Асист #{event_id}: допомога у вбивстві {victim_name} | Fame: {fame:,}")
    except Exception as dispatch_err:
        logger.error(f"❌ [ВІДПРАВКА] Помилка для #{event_id}: {dispatch_err}")

def _get_ping_text(channel):
    if BIG_KILL_ROLE_ID:
        return f"<@&{BIG_KILL_ROLE_ID}>"
    return "@everyone"

# ==========================================
# 🔁 МОНІТОРИНГ
# ==========================================
async def monitor_loop():
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

async def daily_report_loop():
    global _daily_kills, _daily_deaths, _daily_assists, _daily_fame, _daily_top_killers

    await bot.wait_until_ready()
    logger.info("📅 [ЗВІТ] Запущено планувальник щоденних звітів (22:00 UTC)")

    while not bot.is_closed():
        now = datetime.now(timezone.utc)
        target = now.replace(hour=22, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(f"📅 [ЗВІТ] Наступний звіт через {wait_seconds/3600:.1f} годин")
        await asyncio.sleep(wait_seconds)

        try:
            kill_channel = bot.get_channel(KILL_CHANNEL_ID)
            if not kill_channel:
                continue

            embed = discord.Embed(title=t("daily_report_title"), description=f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y')}", color=0xf1c40f)
            embed.add_field(name=t("kills_count"), value=f"**{_daily_kills}**", inline=True)
            embed.add_field(name=t("deaths_count"), value=f"**{_daily_deaths}**", inline=True)
            embed.add_field(name="🤝 Асисти", value=f"**{_daily_assists}**", inline=True)
            embed.add_field(name=t("fame") + " за день", value=f"🏆 **{_daily_fame:,}**", inline=False)
            embed.add_field(name=t("scanned_events"), value=f"`{_total_events_scanned:,}`", inline=True)
            embed.add_field(name=t("guild_events_found"), value=f"`{_total_guild_events}`", inline=True)

            if _daily_top_killers:
                sorted_killers = sorted(_daily_top_killers.items(), key=lambda x: x[1], reverse=True)[:5]
                top_text = "\n".join([f"**{i+1}.** {name} — {fame:,} fame" for i, (name, fame) in enumerate(sorted_killers)])
                embed.add_field(name=t("top_killers") + " (за день)", value=top_text, inline=False)

            api_top = await get_guild_top(GUILD_ID, range_type="week", limit=5)
            if api_top:
                api_top_text = []
                for i, event in enumerate(api_top[:5]):
                    k = (event.get("Killer") or {}).get("Name", "?")
                    v = (event.get("Victim") or {}).get("Name", "?")
                    f_val = event.get("TotalVictimKillFame", 0)
                    api_top_text.append(f"**{i+1}.** {k} ☠️ {v} — {f_val:,} fame")
                embed.add_field(name=t("top_killers") + f" ({t('weekly_report')})", value="\n".join(api_top_text), inline=False)

            embed.set_footer(text="Автоматичний звіт | Dev: EvilHIMARS")
            await kill_channel.send(embed=embed)
            logger.info(f"📅 [ЗВІТ] Надіслано: kills={_daily_kills}, deaths={_daily_deaths}, fame={_daily_fame:,}")

            _daily_kills = 0
            _daily_deaths = 0
            _daily_assists = 0
            _daily_fame = 0
            _daily_top_killers = {}
        except Exception as e:
            logger.error(f"❌ [ЗВІТ] Помилка: {e}")

# ==========================================
# 🎮 SLASH КОМАНДИ
# ==========================================
@bot.event
async def on_ready():
    logger.info("=" * 50)
    logger.info(f"✅ [DISCORD] Бот: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"✅ [DISCORD] Серверів: {len(bot.guilds)}")
    for g in bot.guilds:
        logger.info(f"   📌 {g.name} (ID: {g.id}, учасників: {g.member_count})")
    logger.info("=" * 50)

    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ [SYNC] Синхронізовано {len(synced)} команд")
    except Exception as e:
        logger.error(f"❌ [SYNC] Помилка: {e}")

    bot.loop.create_task(monitor_loop())
    bot.loop.create_task(daily_report_loop())

@bot.tree.command(name="scan", description="Глибокий скан 51 подій з картками")
async def scan(interaction: discord.Interaction):
    await interaction.response.defer()
    logger.info(f"🔧 /scan від {interaction.user}")

    try:
        events = await get_events(limit=51)
        if not events:
            await interaction.followup.send(t("empty_api"))
            return

        found_kills = 0
        found_deaths = 0
        found_assists = 0

        for event in events:
            result = is_guild_kill(event)
            if not result:
                continue

            if result == "kill":
                found_kills += 1
                embed, file = create_battle_embed(event, "☠️ ЗНАЙДЕНО ВБИВСТВО (СКАН)", 0x2ecc71)
            elif result == "death":
                found_deaths += 1
                embed, file = create_battle_embed(event, "💀 ЗНАЙДЕНО СМЕРТЬ (СКАН)", 0xe74c3c)
            elif result == "assist":
                found_assists += 1
                embed, file = create_battle_embed(event, "🤝 ЗНАЙДЕНО АСИСТ (СКАН)", 0x3498db)
            else:
                continue
            await interaction.followup.send(embed=embed, file=file)

        total = found_kills + found_deaths + found_assists
        if total > 0:
            await interaction.followup.send(t("found_events", total=total, kills=found_kills, deaths=found_deaths, assists=found_assists))
        else:
            await interaction.followup.send(t("no_guild_events", total=len(events)))
    except Exception as e:
        await interaction.followup.send(t("api_error", error=str(e)))

@bot.tree.command(name="scanlive", description="Швидкий скан 20 подій з картками")
async def scanlive(interaction: discord.Interaction):
    await interaction.response.defer()
    logger.info(f"🔧 /scanlive від {interaction.user}")

    try:
        events = await get_events(limit=20)
        if not events:
            await interaction.followup.send(t("empty_api"))
            return

        for event in events:
            embed, file = create_battle_embed(event, f"⚔️ #{event.get('EventId', '?')}", 0x3498db)
            await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(t("api_error", error=str(e)))

@bot.tree.command(name="lastkills", description="Останні кіли зі світового логу (з картками)")
async def lastkills(interaction: discord.Interaction, count: int = 5):
    await interaction.response.defer()
    logger.info(f"🔧 /lastkills count={count} від {interaction.user}")
    count = max(1, min(count, 20))

    try:
        events = await get_events(limit=count)
        if not events:
            await interaction.followup.send(t("empty_api"))
            return

        for event in events[:count]:
            embed, file = create_battle_embed(event, f"🌐 #{event.get('EventId', '?')}", 0x95a5a6)
            await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(t("api_error", error=str(e)))

@bot.tree.command(name="top", description="Топ кілерів гільдії")
async def top(interaction: discord.Interaction, period: str = "week"):
    await interaction.response.defer()
    logger.info(f"🔧 /top period={period} від {interaction.user}")

    valid = ["week", "month", "lastWeek", "lastMonth"]
    if period not in valid:
        await interaction.followup.send(t("invalid_period"))
        return

    top_events = await get_guild_top(GUILD_ID, range_type=period, limit=10)
    if not top_events:
        await interaction.followup.send(t("no_data_period"))
        return

    embed = discord.Embed(title=f"🏆 Топ-10 кілерів ({period})", color=0xf1c40f)
    for i, event in enumerate(top_events[:10]):
        killer = (event.get("Killer") or {}).get("Name", "?")
        victim = (event.get("Victim") or {}).get("Name", "?")
        fame = event.get("TotalVictimKillFame", 0)
        eid = event.get("EventId", "?")
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
        embed.add_field(name=f"{medal} {killer} ☠️ {victim}", value=f"Fame: **{fame:,}**\n[Killboard](https://albiononline.com/killboard/kill/{eid})", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="player", description="Статистика гравця")
async def player(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    logger.info(f"🔧 /player {name} від {interaction.user}")

    results = await search_player(name)
    if not results:
        await interaction.followup.send(t("player_not_found", name=name))
        return

    player_data = results[0]
    player_id = player_data.get("Id")
    player_name = player_data.get("Name", "?")

    info = await get_player_info(player_id)
    if not info:
        await interaction.followup.send(t("player_not_found", name=player_name))
        return

    embed = discord.Embed(title=f"👤 {player_name}", url=f"https://albiononline.com/killboard/player/{player_id}", color=0x3498db)
    embed.add_field(name="🏰 Гільдія", value=info.get("GuildName") or t("no_guild"), inline=True)
    embed.add_field(name="🤝 Альянс", value=info.get("AllianceName") or "—", inline=True)
    embed.add_field(name="📊 Fame Ratio", value=f"**{info.get('FameRatio', 0):.2f}**", inline=True)
    embed.add_field(name="⚔️ Kill Fame", value=f"**{info.get('KillFame', 0):,}**", inline=True)
    embed.add_field(name="💀 Death Fame", value=f"**{info.get('DeathFame', 0):,}**", inline=True)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="battleboard", description="Деталі бою за ID")
async def battleboard(interaction: discord.Interaction, event_id: int):
    await interaction.response.defer()
    logger.info(f"🔧 /battleboard {event_id} від {interaction.user}")

    event = await get_event_details(event_id)
    if not event:
        await interaction.followup.send(t("battle_not_found", id=event_id))
        return

    embed, file = create_battle_embed(event, f"⚔️ Бій #{event_id}", 0xe67e22)
    await interaction.followup.send(embed=embed, file=file)

@bot.tree.command(name="checkapi", description="Перевірка API Albion Online")
async def checkapi(interaction: discord.Interaction):
    await interaction.response.defer()
    logger.info(f"🔧 /checkapi від {interaction.user}")
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            event = events[0]
            event_id = event.get('EventId', '?')
            timestamp = event.get('TimeStamp', '?')
            
            embed = discord.Embed(title="🌐 Статус API", color=0x2ecc71)
            embed.add_field(name="🟢 Стан", value="Працює!", inline=False)
            embed.add_field(name="📊 Остання подія", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час (UTC)", value=f"`{timestamp}`", inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(t("empty_api"))
    except Exception as e:
        await interaction.followup.send(t("api_error", error=str(e)))

@bot.tree.command(name="guild", description="Інформація про гільдію")
async def guild(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await get_guild_info(GUILD_ID)
    if not data:
        await interaction.followup.send("❌ Не вдалося отримати дані.")
        return

    embed = discord.Embed(title=f"🏰 {data.get('Name', '?')}", color=0x3498db)
    embed.add_field(name="👑 Лідер", value=data.get('FounderName', '—'), inline=True)
    embed.add_field(name="👥 Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="⚔️ Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Статус моніторингу")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 Статус", color=0x9b59b6)
    embed.add_field(name="🔄 Циклів", value=f"`{_cycle_count}`", inline=True)
    embed.add_field(name="📡 Подій", value=f"`{_total_events_scanned:,}`", inline=True)
    embed.add_field(name="🎯 Гільдія", value=f"`{_total_guild_events}`", inline=True)
    embed.add_field(name="📅 Сьогодні", value=f"⚔️ {_daily_kills} | 💀 {_daily_deaths} | 🤝 {_daily_assists}\n🏆 {_daily_fame:,} fame", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lang", description="Змінити мову бота")
async def lang(interaction: discord.Interaction, language: str):
    global _current_lang
    if language.lower() not in TRANSLATIONS:
        await interaction.response.send_message("❌ Доступні мови: `ua`, `ru`, `en`", ephemeral=True)
        return
    _current_lang = language.lower()
    await interaction.response.send_message(t("lang_set"))

@bot.tree.command(name="info", description="Список команд")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 x E C L I P S E x — Killboard Bot", description="Слеш-команди з картками екіпіровки", color=0xf39c12)
    embed.add_field(name="/scan", value="Скан 51 подій гільдії з картками", inline=False)
    embed.add_field(name="/scanlive", value="Швидкий скан 20 подій з картками", inline=False)
    embed.add_field(name="/lastkills [n]", value="Останні n кілів з картками (макс 20)", inline=False)
    embed.add_field(name="/top [період]", value="Топ-10 кілерів гільдії", inline=False)
    embed.add_field(name="/player [ім'я]", value="Статистика гравця", inline=False)
    embed.add_field(name="/battleboard [ID]", value="Деталі бою з карткою", inline=False)
    embed.add_field(name="/guild", value="Інфо гільдії", inline=False)
    embed.add_field(name="/status", value="Статус моніторингу", inline=False)
    embed.add_field(name="/lang [ua/ru/en]", value="Зміна мови", inline=False)
    embed.add_field(name="/checkapi", value="Перевірка API", inline=False)
    await interaction.response.send_message(embed=embed)

# Запуск
keep_alive()
bot.run(TOKEN)
