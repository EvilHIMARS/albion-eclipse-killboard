import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

from api_client import get_events, get_guild_info
from tracker import is_guild_kill
from utils import extract_player, extract_participants

# ==========================================
# НАЛАШТУВАННЯ СИСТЕМНОГО ЛОГУВАННЯ
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
    logger.info("[UPTIME] Внутрішній веб-сервер запущено на порту 10000")


# ==========================================
# ІНІЦІАЛІЗАЦІЯ ТА НАЛАШТУВАННЯ БОТА
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logger.info("=" * 50)
logger.info("[INIT] Завантаження конфігурації...")
logger.info(f"[INIT] GUILD_ID: {GUILD_ID or 'НЕ ЗНАЙДЕНО'}")

try:
    KILL_CHANNEL_ID = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL_ID = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    logger.error("[INIT] Критична помилка: ID каналів в .env вказано некоректно!")
    KILL_CHANNEL_ID = 0
    DEATH_CHANNEL_ID = 0

logger.info(f"[INIT] KILL_CHANNEL_ID: {KILL_CHANNEL_ID or 'НЕ ЗНАЙДЕНО'}")
logger.info(f"[INIT] DEATH_CHANNEL_ID: {DEATH_CHANNEL_ID or 'НЕ ЗНАЙДЕНО'}")
logger.info(f"[INIT] DISCORD_TOKEN: {'Знайдено' if TOKEN else 'НЕ ЗНАЙДЕНО'}")
logger.info("=" * 50)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ЗАХИСТ ВІД ДУБЛІВ З ОПТИМІЗАЦІЄЮ ПАМ'ЯТІ
PROCESSED_EVENTS = set()
MAX_CACHE_SIZE = 2000

# Лічильник циклів для статистики
_cycle_count = 0
_total_events_scanned = 0
_total_guild_events = 0

# ==========================================
# КОНФІГУРАЦІЯ ТИПІВ ПОДІЙ
# ==========================================
# Maps result_type -> (title, embed color, channel key)
EVENT_TYPE_CONFIG = {
    "kill": ("☠ НОВЕ ВБИВСТВО ГІЛЬДІЇ", 0x2ecc71, "kill"),
    "death": ("💀 ВТРАТА В БОЮ (СМЕРТЬ)", 0xe74c3c, "death"),
    "assist": ("🤝 АСИСТ ГІЛЬДІЇ У ВБИВСТВІ", 0x3498db, "kill"),
}

# Scan-specific titles reuse the same config pattern
SCAN_TYPE_CONFIG = {
    "kill": ("☠ ЗНАЙДЕНО ВБИВСТВО ГІЛЬДІЇ (СКАН)", 0x2ecc71),
    "death": ("💀 ЗНАЙДЕНО СМЕРТЬ СОРАТНИКА (СКАН)", 0xe74c3c),
    "assist": ("🤝 ЗНАЙДЕНО АСИСТ ГІЛЬДІЇ (СКАН)", 0x3498db),
}


# ==========================================
# ФОРМАТ EMBED-ПОВІДОМЛЕНЬ
# ==========================================
def create_battle_embed(event, title, color_hex):
    """Генерує детальну картку бою з прямими посиланнями."""
    event_id = event.get("EventId", 0)
    fame = event.get("TotalVictimKillFame", 0)

    killer = extract_player(event, "Killer")
    victim = extract_player(event, "Victim")

    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"

    embed = discord.Embed(
        title=title,
        url=killboard_url,
        color=color_hex,
        description=f"🔗 [Відкрити цей бій на офіційному Кілборді]({killboard_url})"
    )

    embed.add_field(
        name="⚔ Вбивця",
        value=f"**{killer['name']}**\n`[{killer['guild_name']}]`",
        inline=True,
    )
    embed.add_field(
        name="💀 Жертва",
        value=f"**{victim['name']}**\n`[{victim['guild_name']}]`",
        inline=True,
    )
    embed.add_field(
        name="✨ Слава за вбивство (Fame)",
        value=f"🏆 **{fame:,}**",
        inline=False,
    )

    participants = extract_participants(event)
    if participants:
        damage_list = [
            f"• **{p['name']}** `[{p['guild_name']}]`: {p['damage']:,} DMG"
            for p in participants if p["damage"] > 0
        ]
        heal_list = [
            f"• **{p['name']}** `[{p['guild_name']}]`: {p['healing']:,} HEAL"
            for p in participants if p["healing"] > 0
        ]

        if damage_list:
            embed.add_field(
                name="📈 Розподіл шкоди:",
                value="\n".join(damage_list[:5]),
                inline=False,
            )
        if heal_list:
            embed.add_field(
                name="💚 Підтримка та зцілення:",
                value="\n".join(heal_list[:5]),
                inline=False,
            )

    embed.set_footer(text=f"ID події: {event_id} | Розробник: EvilHIMARS")
    return embed


def create_compact_embed(event):
    """Creates a compact embed for world-log commands (scanlive, lastkills)."""
    event_id = event.get("EventId", "?")
    fame = event.get("TotalVictimKillFame", 0)

    killer = extract_player(event, "Killer")
    victim = extract_player(event, "Victim")

    embed = discord.Embed(
        title=f"🌐 Світова подія #{event_id}",
        url=f"https://albiononline.com/killboard/kill/{event_id}",
        color=0x95a5a6,
    )
    embed.add_field(name="⚔ Вбивця", value=f"**{killer['name']}** `[{killer['guild_name']}]`", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim['name']}** `[{victim['guild_name']}]`", inline=True)
    embed.add_field(name="✨ Fame", value=f"**{fame:,}**", inline=True)
    return embed


# ==========================================
# МЕНЕДЖЕРИ ТА АТОМАРНІ ФУНКЦІЇ
# ==========================================
def manage_cache(event_id):
    """Контролює захист від дублікатів та очищає старий кеш при переповненні."""
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False

    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info(
            f"[КЕШ] Кеш дублікатів заповнено ({len(PROCESSED_EVENTS)} записів). "
            "Планова очистка пам'яті..."
        )
        PROCESSED_EVENTS.clear()

    PROCESSED_EVENTS.add(event_id)
    return True


async def dispatch_event(event, result_type, channels):
    """Send an event embed to the appropriate channel based on result_type."""
    event_id = event.get("EventId")
    config = EVENT_TYPE_CONFIG.get(result_type)
    if not config:
        return

    title, color, channel_key = config
    channel = channels.get(channel_key)
    if not channel:
        return

    killer = extract_player(event, "Killer")
    victim = extract_player(event, "Victim")
    fame = event.get("TotalVictimKillFame", 0)

    try:
        embed = create_battle_embed(event, title, color)
        await channel.send(embed=embed)
        logger.info(
            f"[ВІДПРАВКА] {result_type} #{event_id}: "
            f"{killer['name']} vs {victim['name']} | Fame: {fame:,}"
        )
    except Exception as dispatch_err:
        logger.error(
            f"[ВІДПРАВКА] Не вдалося відправити повідомлення в Discord "
            f"для #{event_id}: {dispatch_err}"
        )


# ==========================================
# АВТОМАТИЧНИЙ МОНІТОРИНГ 24/7
# ==========================================
async def monitor_loop():
    """Головний ізольований цикл моніторингу, стійкий до помилок мережі та API."""
    global _cycle_count, _total_events_scanned, _total_guild_events

    await bot.wait_until_ready()

    channels = {
        "kill": bot.get_channel(KILL_CHANNEL_ID),
        "death": bot.get_channel(DEATH_CHANNEL_ID),
    }

    kill_channel = channels["kill"]
    death_channel = channels["death"]

    logger.info("=" * 50)
    logger.info("[МОНІТОР] Запуск фонового моніторингу Albion API")
    logger.info(f"[МОНІТОР] Канал вбивств: {'✅' + kill_channel.name if kill_channel else 'НЕ ЗНАЙДЕНО (ID: ' + str(KILL_CHANNEL_ID) + ')'}")
    logger.info(f"[МОНІТОР] Канал смертей: {'✅' + death_channel.name if death_channel else 'НЕ ЗНАЙДЕНО (ID: ' + str(DEATH_CHANNEL_ID) + ')'}")
    logger.info("[МОНІТОР] Інтервал опитування: кожні 30 секунд")
    logger.info("[МОНІТОР] Ліміт подій за запит: 100")
    logger.info("=" * 50)

    # Тестовий запит при старті
    logger.info("[МОНІТОР] Підключення до серверів Albion Online (Europe Gateway)...")
    test_events = await get_events(limit=5)
    if test_events and isinstance(test_events, list):
        logger.info(f"[МОНІТОР] З'єднання з Albion API успішне! Отримано {len(test_events)} тестових подій")
        logger.info(f"[МОНІТОР] Останній EventId у світі: {test_events[0].get('EventId', '?')}")
    else:
        logger.warning("[МОНІТОР] Albion API повернув порожню відповідь при тестовому запиті.")

    logger.info("[МОНІТОР] Починаю безперервний моніторинг подій гільдії...")

    while not bot.is_closed():
        _cycle_count += 1
        try:
            logger.info(f"[ЦИКЛ #{_cycle_count}] Відправляю запит до Albion API (limit=100)...")
            events = await get_events(limit=100)

            if not events or not isinstance(events, list):
                logger.warning(f"[ЦИКЛ #{_cycle_count}] Albion API повернув порожній список. Пропуск ітерації.")
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
                await dispatch_event(event, result_type, channels)

            duplicates_count = len(events) - new_events_count
            logger.info(
                f"[ЦИКЛ #{_cycle_count}] Результат: отримано {len(events)} подій | "
                f"нових: {new_events_count} | дублікатів: {duplicates_count} | "
                f"події гільдії: {guild_events_in_cycle} | "
                f"кеш: {len(PROCESSED_EVENTS)} записів"
            )

            if guild_events_in_cycle > 0:
                logger.info(f"[ЦИКЛ #{_cycle_count}] Знайдено {guild_events_in_cycle} подій гільдії! Відправлено в Discord.")

            # Кожні 10 циклів (~5 хв) — загальна статистика
            if _cycle_count % 10 == 0:
                logger.info(
                    f"[СТАТИСТИКА] Загалом за {_cycle_count} циклів: "
                    f"проскановано {_total_events_scanned} подій | "
                    f"знайдено {_total_guild_events} подій гільдії | "
                    f"кеш: {len(PROCESSED_EVENTS)}/{MAX_CACHE_SIZE}"
                )

        except asyncio.CancelledError:
            logger.info("[МОНІТОР] Цикл моніторингу зупинено адміністратором.")
            break
        except Exception as global_loop_error:
            logger.error(
                f"[ЦИКЛ #{_cycle_count}] Критичний збій: "
                f"{type(global_loop_error).__name__}: {global_loop_error}. "
                "Перезапуск через 30 сек..."
            )

        await asyncio.sleep(30)


# ==========================================
# КОМАНДИ БОТА
# ==========================================
@bot.event
async def on_ready():
    logger.info("=" * 50)
    logger.info("[DISCORD] Бот успішно авторизовано!")
    logger.info(f"[DISCORD] Ім'я бота: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"[DISCORD] Підключено до {len(bot.guilds)} серверів Discord")
    for g in bot.guilds:
        logger.info(f"   Сервер: {g.name} (ID: {g.id}, учасників: {g.member_count})")
    logger.info("=" * 50)

    logger.info("[DISCORD] Доступні команди бота:")
    logger.info("   !info      — Повний список команд бота з описом")
    logger.info("   !checkapi  — Перевірка статусу API Albion Online")
    logger.info("   !guild     — Статистика гільдії з офіційного API")
    logger.info("   !status    — Статус моніторингу бота (цикли, події, кеш)")
    logger.info("   !scan      — Глибоке сканування 100 останніх подій на кіли/смерті гільдії")
    logger.info("   !lastkills — Показати останні кіли/смерті зі світового логу")
    logger.info("   !scanlive  — Сканування 20 останніх подій (компактний вивід)")
    logger.info("   !help      — Короткий список команд")

    bot.loop.create_task(monitor_loop())


@bot.command()
async def checkapi(ctx):
    """Перевірка доступності шлюзу Albion"""
    logger.info(f"[КОМАНДА] !checkapi від {ctx.author}")
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            event = events[0]
            event_id = event.get('EventId', '?')
            timestamp = event.get('TimeStamp', '?')
            logger.info(f"[КОМАНДА] !checkapi — API відповів, EventId: {event_id}")

            embed = discord.Embed(title="🌐 Статус API Albion Online", color=0x2ecc71)
            embed.add_field(name="🟢 Стан серверів", value="Працює, відповідь отримано!", inline=False)
            embed.add_field(name="📊 ID останньої події", value=f"`{event_id}`", inline=True)
            embed.add_field(name="🕒 Час події (UTC)", value=f"`{timestamp}`", inline=True)
            await ctx.send(embed=embed)
        else:
            logger.warning("[КОМАНДА] !checkapi — API повернув порожній масив")
            await ctx.send("🟡 **API повернуло порожній масив даних.** Можливо сервери гри перевантажені.")
    except Exception as e:
        logger.error(f"[КОМАНДА] !checkapi — збій: {e}")
        await ctx.send(f"🔴 **Помилка з'єднання з API:** `{str(e)}`")


@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію"""
    logger.info(f"[КОМАНДА] !guild від {ctx.author}")
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
    logger.info(f"[КОМАНДА] !guild — отримано дані для гільдії: {guild_name}")

    embed = discord.Embed(title=f"🏰 Статистика гільдії: {guild_name}", color=0x3498db)
    embed.add_field(name="👑 Лідер (Засновник)", value=data.get('FounderName', 'Немає'), inline=True)
    embed.add_field(name="👥 Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
    embed.add_field(name="🤝 Альянс", value=f"[{data.get('AllianceTag', '—')}] {data.get('AllianceName', 'Без альянсу')}", inline=False)
    embed.add_field(name="⚔ PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
    embed.add_field(name="💀 PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
    embed.add_field(name="⚙ Канали бота:", value=f"• ⚔ **Вбивства:** {kill_mention}\n• 💀 **Смерті:** {death_mention}", inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def status(ctx):
    """Статус моніторингу бота"""
    logger.info(f"[КОМАНДА] !status від {ctx.author}")

    embed = discord.Embed(title="📊 Статус моніторингу бота", color=0x9b59b6)
    embed.add_field(name="🔄 Циклів опитування", value=f"`{_cycle_count}`", inline=True)
    embed.add_field(name="📡 Подій проскановано", value=f"`{_total_events_scanned:,}`", inline=True)
    embed.add_field(name="🎯 Подій гільдії знайдено", value=f"`{_total_guild_events}`", inline=True)
    embed.add_field(name="🧠 Кеш дублікатів", value=f"`{len(PROCESSED_EVENTS)} / {MAX_CACHE_SIZE}`", inline=True)
    embed.add_field(name="⏱ Інтервал", value="`кожні 30 сек`", inline=True)
    embed.add_field(name="📦 Ліміт подій", value="`100 за запит`", inline=True)

    kill_ch = bot.get_channel(KILL_CHANNEL_ID)
    death_ch = bot.get_channel(DEATH_CHANNEL_ID)
    channels_status = (
        f"⚔ Вбивства: {'✅' + kill_ch.name if kill_ch else '❌ Не знайдено'}\n"
        f"💀 Смерті: {'✅' + death_ch.name if death_ch else '❌ Не знайдено'}"
    )
    embed.add_field(name="📺 Канали", value=channels_status, inline=False)
    embed.set_footer(text=f"GUILD_ID: {GUILD_ID}")
    await ctx.send(embed=embed)


@bot.command()
async def scan(ctx):
    """Глибоке сканування 100 останніх подій — шукає кіли/смерті гільдії"""
    logger.info(f"[КОМАНДА] !scan від {ctx.author}")
    status_msg = await ctx.send("🔍 **Глибоке сканування:** перевіряю 100 останніх подій в Albion Europe...")

    try:
        events = await get_events(limit=100)
        if not events or not isinstance(events, list):
            logger.warning("[КОМАНДА] !scan — API повернув порожній список")
            await status_msg.edit(content="🟡 API Альбіону повернув порожній список подій. Спробуй пізніше.")
            return

        found_kills = 0
        found_deaths = 0
        found_assists = 0
        seen_guilds = set()

        for event in events:
            killer = extract_player(event, "Killer")
            victim = extract_player(event, "Victim")
            if killer["guild_name"] != "Без гільдії":
                seen_guilds.add(killer["guild_name"])
            if victim["guild_name"] != "Без гільдії":
                seen_guilds.add(victim["guild_name"])

            result = is_guild_kill(event)
            if not result:
                continue

            scan_config = SCAN_TYPE_CONFIG.get(result)
            if not scan_config:
                continue

            scan_title, scan_color = scan_config
            if result == "kill":
                found_kills += 1
            elif result == "death":
                found_deaths += 1
            elif result == "assist":
                found_assists += 1

            embed = create_battle_embed(event, scan_title, scan_color)
            await ctx.send(embed=embed)

        total_found = found_kills + found_deaths + found_assists
        if total_found > 0:
            logger.info(
                f"[КОМАНДА] !scan — знайдено {total_found} подій гільдії "
                f"(kills: {found_kills}, deaths: {found_deaths}, assists: {found_assists})"
            )
            await status_msg.edit(
                content=f"✅ **Сканування завершено!** Знайдено **{total_found}** подій гільдії:\n"
                        f"⚔ Вбивств: **{found_kills}** | 💀 Смертей: **{found_deaths}** | 🤝 Асистів: **{found_assists}**"
            )
        else:
            sample_guilds = list(seen_guilds)[:5]
            guilds_str = ", ".join([f"`{g}`" for g in sample_guilds]) if sample_guilds else "немає даних"
            logger.info(f"[КОМАНДА] !scan — подій гільдії не знайдено серед {len(events)} подій")
            await status_msg.edit(
                content=f"ℹ Проскановано **{len(events)}** глобальних подій. Подій нашої гільдії не знайдено.\n\n"
                        f"⚙ **Фільтр працює:** бот відсіяв інші гільдії, наприклад: {guilds_str}\n"
                        f"🟢 Моніторинг продовжує працювати — нові бої будуть виявлені автоматично."
            )
    except Exception as e:
        logger.error(f"[КОМАНДА] !scan — збій: {e}")
        await status_msg.edit(content=f"🔴 **Помилка сканування:** `{str(e)}`")


@bot.command()
async def scanlive(ctx):
    """Сканування 20 останніх подій (компактний формат)"""
    logger.info(f"[КОМАНДА] !scanlive від {ctx.author}")
    events = await get_events(limit=20)
    if not events:
        logger.warning("[КОМАНДА] !scanlive — API не відповіло або подій немає")
        await ctx.send("❌ API не відповіло або подій немає.")
        return

    logger.info(f"[КОМАНДА] !scanlive — отримано {len(events)} подій")
    for event in events:
        embed = create_compact_embed(event)
        await ctx.send(embed=embed)


@bot.command()
async def lastkills(ctx, count: int = 10):
    """Показує останні кіли/смерті зі світового логу Albion (без фільтру гільдії)"""
    logger.info(f"[КОМАНДА] !lastkills (count={count}) від {ctx.author}")
    count = max(1, min(count, 20))

    try:
        events = await get_events(limit=count)
        if not events or not isinstance(events, list):
            await ctx.send("🟡 API Альбіону повернув порожній список.")
            return

        logger.info(f"[КОМАНДА] !lastkills — отримано {len(events)} подій зі світового логу")
        await ctx.send(f"🌍 **Останні {len(events)} подій зі світового логу Albion Online:**")

        for event in events[:count]:
            embed = create_compact_embed(event)
            await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"[КОМАНДА] !lastkills — збій: {e}")
        await ctx.send(f"🔴 **Помилка:** `{str(e)}`")


@bot.command()
async def info(ctx):
    """Повний список команд бота з детальним описом"""
    logger.info(f"[КОМАНДА] !info від {ctx.author}")
    embed = discord.Embed(
        title="📖 x E C L I P S E x — Killboard Bot",
        description="Бот автоматично моніторить Albion Online API кожні 30 секунд та відправляє сповіщення про вбивства, смерті та асисти гільдії у відповідні канали Discord.",
        color=0xf39c12
    )

    embed.add_field(
        name="🔍 !scan",
        value="**Глибоке сканування.** Залазить в логи Albion API та перевіряє 100 останніх подій. "
              "Шукає вбивства, смерті та асисти гільдії. Все знайдене відправляє прямо в чат з детальними картками бою.",
        inline=False
    )
    embed.add_field(
        name="⚔ !scanlive",
        value="**Швидкий скан.** Показує 20 останніх подій зі світового логу у компактному форматі (вбивця, жертва, fame).",
        inline=False
    )
    embed.add_field(
        name="🌍 !lastkills [кількість]",
        value="**Світовий лог.** Витягує останні кіли зі всього серверу Albion Europe (без фільтру гільдії). "
              "Показує хто кого вбив, з якої гільдії, та скільки Fame. За замовчуванням 10 подій, максимум 20.\n"
              "Приклад: `!lastkills 5`",
        inline=False
    )
    embed.add_field(
        name="🌐 !checkapi",
        value="**Перевірка API.** Відправляє тестовий запит до серверів Albion Online та показує статус з'єднання, "
              "ID останньої події та час.",
        inline=False
    )
    embed.add_field(
        name="🏰 !guild",
        value="**Статистика гільдії.** Витягує з API повну інформацію: лідер, кількість учасників, альянс, "
              "PvP Kill Fame, PvP Death Fame, та показує в які канали бот відправляє звіти.",
        inline=False
    )
    embed.add_field(
        name="📊 !status",
        value="**Статус моніторингу.** Показує скільки циклів опитування пройшло, скільки подій проскановано, "
              "скільки подій гільдії знайдено, стан кешу дублікатів, налаштування інтервалу та каналів.",
        inline=False
    )
    embed.add_field(
        name="📋 !help",
        value="**Короткий список.** Показує всі команди одним рядком.",
        inline=False
    )
    embed.add_field(
        name="📖 !info",
        value="**Ця сторінка.** Повний список команд з детальним описом кожної.",
        inline=False
    )

    embed.add_field(
        name="⚙ Як працює автоматичний моніторинг?",
        value="Бот кожні **30 секунд** відправляє запит до Albion API та отримує **100 останніх подій** у світі. "
              "Потім фільтрує їх по ID гільдії та відправляє:\n"
              "• ☠ **Вбивства** → канал вбивств\n"
              "• 💀 **Смерті** → канал смертей\n"
              "• 🤝 **Асисти** → канал вбивств\n"
              "Захист від дублікатів: бот запам'ятовує EventId та не відправляє одну подію двічі.",
        inline=False
    )

    embed.set_footer(text="Бот моніторить Albion API 24/7 | Розробник: EvilHIMARS")
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    """Короткий список команд бота"""
    logger.info(f"[КОМАНДА] !help від {ctx.author}")
    embed = discord.Embed(title="📋 Команди бота x E C L I P S E x", color=0xf39c12)
    embed.add_field(name="!info", value="📖 Повний список команд з детальним описом", inline=False)
    embed.add_field(name="!scan", value="🔍 Глибоке сканування 100 подій — пошук кілів/смертей гільдії", inline=False)
    embed.add_field(name="!scanlive", value="⚔ Швидкий скан 20 останніх подій (компактний вивід)", inline=False)
    embed.add_field(name="!lastkills [n]", value="🌍 Останні n кілів зі світового логу (за замовч. 10, макс. 20)", inline=False)
    embed.add_field(name="!checkapi", value="🌐 Перевірка з'єднання з API Albion Online", inline=False)
    embed.add_field(name="!guild", value="🏰 Статистика гільдії: учасники, fame, альянс", inline=False)
    embed.add_field(name="!status", value="📊 Статус моніторингу: цикли, події, кеш", inline=False)
    embed.set_footer(text="Напиши !info для детального опису кожної команди | Розробник: EvilHIMARS")
    await ctx.send(embed=embed)


# Запуск всієї екосистеми
keep_alive()
bot.run(TOKEN)
