import os
import sys
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

logger.info("=" * 50)
logger.info("[INIT] Завантаження конфігурації...")
logger.info("[INIT] GUILD_ID: %s", GUILD_ID)

try:
    KILL_CHANNEL_ID = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL_ID = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    logger.critical("ID каналів в .env вказано некоректно! Очікуються числові значення.")
    sys.exit(1)

if not KILL_CHANNEL_ID or not DEATH_CHANNEL_ID:
    logger.warning(
        "Один або обидва канали не налаштовані (KILL_CHANNEL_ID=%s, DEATH_CHANNEL_ID=%s). "
        "Відповідні події не будуть відправлятися.",
        KILL_CHANNEL_ID, DEATH_CHANNEL_ID,
    )

logger.info("[INIT] KILL_CHANNEL_ID: %s", KILL_CHANNEL_ID or 'НЕ ЗНАЙДЕНО')
logger.info("[INIT] DEATH_CHANNEL_ID: %s", DEATH_CHANNEL_ID or 'НЕ ЗНАЙДЕНО')
logger.info("[INIT] DISCORD_TOKEN: Знайдено")
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
# ФОРМАТ EMBED-ПОВІДОМЛЕНЬ
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
        description=f"[Відкрити цей бій на офіційному Кілборді]({killboard_url})"
    )

    embed.add_field(name="Вбивця", value=f"**{killer_name}**\n`[{killer_guild}]`", inline=True)
    embed.add_field(name="Жертва", value=f"**{victim_name}**\n`[{victim_guild}]`", inline=True)
    embed.add_field(name="Слава за вбивство (Fame)", value=f"**{fame:,}**", inline=False)

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
                damage_list.append(f"* **{name}** `[{guild}]`: {dmg:,} DMG")
            if heal > 0:
                heal_list.append(f"* **{name}** `[{guild}]`: {heal:,} HEAL")

        if damage_list:
            embed.add_field(name="Розподіл шкоди:", value="\n".join(damage_list[:5]), inline=False)
        if heal_list:
            embed.add_field(name="Підтримка та зцілення:", value="\n".join(heal_list[:5]), inline=False)

    embed.set_footer(text=f"ID події: {event_id} | Розробник: EvilHIMARS")
    return embed

# ==========================================
# МЕНЕДЖЕРИ ТА АТОМАРНІ ФУНКЦІЇ
# ==========================================
def manage_cache(event_id):
    """Контролює захист від дублікатів та очищає старий кеш при переповненні"""
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False

    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info("[КЕШ] Кеш дублікатів заповнено (%s записів). Планова очистка пам'яті...", len(PROCESSED_EVENTS))
        PROCESSED_EVENTS.clear()

    PROCESSED_EVENTS.add(event_id)
    return True

async def dispatch_event(event, result_type, kill_ch, death_ch):
    """Ізольована функція відправки конкретної події в потрібний канал"""
    event_id = event.get("EventId")
    killer_name = (event.get("Killer") or {}).get("Name", "?")
    victim_name = (event.get("Victim") or {}).get("Name", "?")
    fame = event.get("TotalVictimKillFame", 0)

    channel_map = {
        "kill": ("НОВЕ ВБИВСТВО ГІЛЬДІЇ", 0x2ecc71, kill_ch),
        "death": ("ВТРАТА В БОЮ (СМЕРТЬ)", 0xe74c3c, death_ch),
        "assist": ("АСИСТ ГІЛЬДІЇ У ВБИВСТВІ", 0x3498db, kill_ch),
    }

    entry = channel_map.get(result_type)
    if entry is None:
        logger.warning("Невідомий тип події '%s' для #%s — пропуск.", result_type, event_id)
        return

    title, color, channel = entry
    if channel is None:
        logger.warning(
            "Канал для типу '%s' не знайдено (подія #%s). Перевірте KILL_CHANNEL_ID / DEATH_CHANNEL_ID.",
            result_type, event_id,
        )
        return

    try:
        embed = create_battle_embed(event, title, color)
        await channel.send(embed=embed)
        logger.info(
            "[ВІДПРАВКА] %s #%s: %s -> %s | Fame: %s",
            result_type.capitalize(), event_id, killer_name, victim_name, f"{fame:,}",
        )
    except discord.Forbidden as e:
        logger.error(
            "Немає прав для надсилання повідомлення в канал %s (подія #%s): %s", channel.id, event_id, e,
        )
    except discord.HTTPException as e:
        logger.error(
            "HTTP-помилка Discord при відправленні події #%s в канал %s: %s", event_id, channel.id, e,
        )
    except Exception as e:
        logger.exception("Непередбачена помилка при відправленні події #%s: %s", event_id, e)

# ==========================================
# АВТОМАТИЧНИЙ МОНІТОРИНГ 24/7
# ==========================================
async def monitor_loop():
    """Головний ізольований цикл моніторингу, стійкий до будь-яких помилок мережі та API"""
    global _cycle_count, _total_events_scanned, _total_guild_events

    await bot.wait_until_ready()

    kill_channel = bot.get_channel(KILL_CHANNEL_ID)
    death_channel = bot.get_channel(DEATH_CHANNEL_ID)

    logger.info("=" * 50)
    logger.info("[МОНІТОР] Запуск фонового моніторингу Albion API")
    if kill_channel is None and KILL_CHANNEL_ID:
        logger.error(
            "Не вдалося знайти канал для вбивств (KILL_CHANNEL_ID=%s). "
            "Переконайтеся, що бот додано на сервер і ID каналу коректний.",
            KILL_CHANNEL_ID,
        )
    else:
        logger.info("[МОНІТОР] Канал вбивств: %s", kill_channel.name if kill_channel else "НЕ ЗНАЙДЕНО")
    if death_channel is None and DEATH_CHANNEL_ID:
        logger.error(
            "Не вдалося знайти канал для смертей (DEATH_CHANNEL_ID=%s). "
            "Переконайтеся, що бот додано на сервер і ID каналу коректний.",
            DEATH_CHANNEL_ID,
        )
    else:
        logger.info("[МОНІТОР] Канал смертей: %s", death_channel.name if death_channel else "НЕ ЗНАЙДЕНО")
    logger.info("[МОНІТОР] Інтервал опитування: кожні 30 секунд")
    logger.info("[МОНІТОР] Ліміт подій за запит: 100")
    logger.info("=" * 50)

    # Тестовий запит при старті
    logger.info("[МОНІТОР] Підключення до серверів Albion Online (Europe Gateway)...")
    test_events = await get_events(limit=5)
    if test_events and isinstance(test_events, list):
        logger.info("[МОНІТОР] З'єднання з Albion API успішне! Отримано %s тестових подій", len(test_events))
        logger.info("[МОНІТОР] Останній EventId у світі: %s", test_events[0].get('EventId', '?'))
    else:
        logger.warning("[МОНІТОР] Albion API повернув порожню відповідь при тестовому запиті. Можливо сервер перевантажений.")

    logger.info("[МОНІТОР] Починаю безперервний моніторинг подій гільдії...")

    while not bot.is_closed():
        _cycle_count += 1
        try:
            events = await get_events(limit=100)

            if not events or not isinstance(events, list):
                logger.warning("[ЦИКЛ #%s] Albion API повернув порожній список. Пропуск ітерації.", _cycle_count)
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
                "[ЦИКЛ #%s] Результат: отримано %s подій | нових: %s | дублікатів: %s | події гільдії: %s | кеш: %s записів",
                _cycle_count, len(events), new_events_count, duplicates_count,
                guild_events_in_cycle, len(PROCESSED_EVENTS),
            )

            if guild_events_in_cycle > 0:
                logger.info("[ЦИКЛ #%s] Знайдено %s подій гільдії! Відправлено в Discord.", _cycle_count, guild_events_in_cycle)

            # Кожні 10 циклів (~5 хв) — загальна статистика
            if _cycle_count % 10 == 0:
                logger.info(
                    "[СТАТИСТИКА] Загалом за %s циклів: проскановано %s подій | знайдено %s подій гільдії | кеш: %s/%s",
                    _cycle_count, _total_events_scanned, _total_guild_events,
                    len(PROCESSED_EVENTS), MAX_CACHE_SIZE,
                )

        except asyncio.CancelledError:
            logger.info("[МОНІТОР] Цикл моніторингу зупинено адміністратором.")
            raise
        except Exception:
            logger.exception("[ЦИКЛ #%s] Критичний збій. Перезапуск через 30 сек...", _cycle_count)

        await asyncio.sleep(30)

# ==========================================
# КОМАНДИ БОТА
# ==========================================
def _handle_monitor_task_result(task):
    """Обробка результату задачі моніторингу — логуємо необроблені виключення."""
    if task.cancelled():
        logger.info("Задачу моніторингу було скасовано.")
        return
    exc = task.exception()
    if exc is not None:
        logger.critical(
            "Задача моніторингу завершилась з необробленою помилкою: %s", exc, exc_info=exc,
        )


@bot.event
async def on_ready():
    logger.info("=" * 50)
    logger.info("[DISCORD] Бот успішно авторизовано!")
    logger.info("[DISCORD] Ім'я бота: %s (ID: %s)", bot.user.name, bot.user.id)
    logger.info("[DISCORD] Підключено до %s серверів Discord", len(bot.guilds))
    for g in bot.guilds:
        logger.info("   Сервер: %s (ID: %s, учасників: %s)", g.name, g.id, g.member_count)
    logger.info("=" * 50)

    logger.info("[DISCORD] Доступні команди бота:")
    logger.info("   !info      -- Повний список команд бота з описом")
    logger.info("   !checkapi  -- Перевірка статусу API Albion Online")
    logger.info("   !guild     -- Статистика гільдії з офіційного API")
    logger.info("   !status    -- Статус моніторингу бота (цикли, події, кеш)")
    logger.info("   !scan      -- Глибоке сканування 100 останніх подій на кіли/смерті гільдії")
    logger.info("   !lastkills -- Показати останні кіли/смерті зі світового логу")
    logger.info("   !scanlive  -- Сканування 20 останніх подій (компактний вивід)")
    logger.info("   !help      -- Короткий список команд")

    task = bot.loop.create_task(monitor_loop())
    task.add_done_callback(_handle_monitor_task_result)

@bot.command()
async def checkapi(ctx):
    """Перевірка доступності шлюзу Albion"""
    logger.info("[КОМАНДА] !checkapi від %s", ctx.author)
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            event = events[0]
            event_id = event.get('EventId', '?')
            timestamp = event.get('TimeStamp', '?')
            logger.info("[КОМАНДА] !checkapi -- API відповів, EventId: %s", event_id)

            embed = discord.Embed(title="Статус API Albion Online", color=0x2ecc71)
            embed.add_field(name="Стан серверів", value="Працює, відповідь отримано!", inline=False)
            embed.add_field(name="ID останньої події", value=f"`{event_id}`", inline=True)
            embed.add_field(name="Час події (UTC)", value=f"`{timestamp}`", inline=True)
            await ctx.send(embed=embed)
        else:
            logger.warning("[КОМАНДА] !checkapi -- API повернув порожній масив")
            await ctx.send("**API повернуло порожній масив даних.** Можливо сервери гри перевантажені.")
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити відповідь на !checkapi: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !checkapi -- збій: %s", e)
        try:
            await ctx.send(f"**Помилка з'єднання з API:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def guild(ctx):
    """Повна інформація про гільдію"""
    logger.info("[КОМАНДА] !guild від %s", ctx.author)
    try:
        data = await get_guild_info(GUILD_ID)
        if not data:
            logger.warning("[КОМАНДА] !guild -- не вдалося отримати дані для %s", GUILD_ID)
            await ctx.send("Не вдалося отримати дані гільдії від API Albion.")
            return

        kill_ch = bot.get_channel(KILL_CHANNEL_ID)
        death_ch = bot.get_channel(DEATH_CHANNEL_ID)
        kill_mention = kill_ch.mention if kill_ch else f"`ID: {KILL_CHANNEL_ID} (Не знайдено)`"
        death_mention = death_ch.mention if death_ch else f"`ID: {DEATH_CHANNEL_ID} (Не знайдено)`"

        guild_name = data.get('Name', 'Невідомо')
        logger.info("[КОМАНДА] !guild -- отримано дані для гільдії: %s", guild_name)

        embed = discord.Embed(title=f"Статистика гільдії: {guild_name}", color=0x3498db)
        embed.add_field(name="Лідер (Засновник)", value=data.get('FounderName', 'Немає'), inline=True)
        embed.add_field(name="Учасників", value=f"{data.get('MemberCount', 0)} / 300", inline=True)
        embed.add_field(name="Альянс", value=f"[{data.get('AllianceTag', '-')}] {data.get('AllianceName', 'Без альянсу')}", inline=False)
        embed.add_field(name="PvP Kill Fame", value=f"{data.get('KillFame', 0):,}", inline=True)
        embed.add_field(name="PvP Death Fame", value=f"{data.get('DeathFame', 0):,}", inline=True)
        embed.add_field(name="Канали бота:", value=f"* **Вбивства:** {kill_mention}\n* **Смерті:** {death_mention}", inline=False)
        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити відповідь на !guild: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !guild -- збій: %s", e)
        try:
            await ctx.send(f"**Помилка:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def status(ctx):
    """Статус моніторингу бота"""
    logger.info("[КОМАНДА] !status від %s", ctx.author)
    try:
        embed = discord.Embed(title="Статус моніторингу бота", color=0x9b59b6)
        embed.add_field(name="Циклів опитування", value=f"`{_cycle_count}`", inline=True)
        embed.add_field(name="Подій проскановано", value=f"`{_total_events_scanned:,}`", inline=True)
        embed.add_field(name="Подій гільдії знайдено", value=f"`{_total_guild_events}`", inline=True)
        embed.add_field(name="Кеш дублікатів", value=f"`{len(PROCESSED_EVENTS)} / {MAX_CACHE_SIZE}`", inline=True)
        embed.add_field(name="Інтервал", value="`кожні 30 сек`", inline=True)
        embed.add_field(name="Ліміт подій", value="`100 за запит`", inline=True)

        kill_ch = bot.get_channel(KILL_CHANNEL_ID)
        death_ch = bot.get_channel(DEATH_CHANNEL_ID)
        channels_status = (
            f"Вбивства: {kill_ch.name if kill_ch else 'Не знайдено'}\n"
            f"Смерті: {death_ch.name if death_ch else 'Не знайдено'}"
        )
        embed.add_field(name="Канали", value=channels_status, inline=False)
        embed.set_footer(text=f"GUILD_ID: {GUILD_ID}")
        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити відповідь на !status: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !status -- збій: %s", e)

@bot.command()
async def scan(ctx):
    """Глибоке сканування 100 останніх подій -- шукає кіли/смерті гільдії"""
    logger.info("[КОМАНДА] !scan від %s", ctx.author)
    try:
        status_msg = await ctx.send("**Глибоке сканування:** перевіряю 100 останніх подій в Albion Europe...")
    except discord.HTTPException as e:
        logger.error("Не вдалося відправити початкове повідомлення !scan: %s", e)
        return

    try:
        events = await get_events(limit=100)
        if not events or not isinstance(events, list):
            logger.warning("[КОМАНДА] !scan -- API повернув порожній список")
            await status_msg.edit(content="API Альбіону повернув порожній список подій. Спробуй пізніше.")
            return

        found_kills = 0
        found_deaths = 0
        found_assists = 0
        seen_guilds = set()

        for event in events:
            k_guild = (event.get("Killer") or {}).get("GuildName")
            v_guild = (event.get("Victim") or {}).get("GuildName")
            if k_guild:
                seen_guilds.add(k_guild)
            if v_guild:
                seen_guilds.add(v_guild)

            result = is_guild_kill(event)
            if not result:
                continue

            if result == "kill":
                found_kills += 1
                embed = create_battle_embed(event, "ЗНАЙДЕНО ВБИВСТВО ГІЛЬДІЇ (СКАН)", 0x2ecc71)
            elif result == "death":
                found_deaths += 1
                embed = create_battle_embed(event, "ЗНАЙДЕНО СМЕРТЬ СОРАТНИКА (СКАН)", 0xe74c3c)
            elif result == "assist":
                found_assists += 1
                embed = create_battle_embed(event, "ЗНАЙДЕНО АСИСТ ГІЛЬДІЇ (СКАН)", 0x3498db)
            else:
                continue
            await ctx.send(embed=embed)

        total_found = found_kills + found_deaths + found_assists
        if total_found > 0:
            logger.info("[КОМАНДА] !scan -- знайдено %s подій гільдії (kills: %s, deaths: %s, assists: %s)", total_found, found_kills, found_deaths, found_assists)
            await status_msg.edit(
                content=f"**Сканування завершено!** Знайдено **{total_found}** подій гільдії:\n"
                        f"Вбивств: **{found_kills}** | Смертей: **{found_deaths}** | Асистів: **{found_assists}**"
            )
        else:
            sample_guilds = list(seen_guilds)[:5]
            guilds_str = ", ".join([f"`{g}`" for g in sample_guilds]) if sample_guilds else "немає даних"
            logger.info("[КОМАНДА] !scan -- подій гільдії не знайдено серед %s подій", len(events))
            await status_msg.edit(
                content=f"Проскановано **{len(events)}** глобальних подій. Подій нашої гільдії не знайдено.\n\n"
                        f"**Фільтр працює:** бот відсіяв інші гільдії, наприклад: {guilds_str}\n"
                        f"Моніторинг продовжує працювати -- нові бої будуть виявлені автоматично."
            )
    except discord.HTTPException as e:
        logger.error("[КОМАНДА] !scan -- помилка Discord: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !scan -- збій: %s", e)
        try:
            await status_msg.edit(content=f"**Помилка сканування:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def scanlive(ctx):
    """Сканування 20 останніх подій (компактний формат)"""
    logger.info("[КОМАНДА] !scanlive від %s", ctx.author)
    try:
        events = await get_events(limit=20)
        if not events:
            logger.warning("[КОМАНДА] !scanlive -- API не відповіло або подій немає")
            await ctx.send("API не відповіло або подій немає.")
            return

        logger.info("[КОМАНДА] !scanlive -- отримано %s подій", len(events))
        for event in events:
            killer = (event.get('Killer') or {}).get('Name', 'Unknown')
            victim = (event.get('Victim') or {}).get('Name', 'Unknown')
            fame = event.get('TotalVictimKillFame', 0)
            event_id = event.get('EventId', '?')
            embed = discord.Embed(title=f"Подія #{event_id}", color=discord.Color.blue())
            embed.add_field(name="Вбивця", value=killer, inline=True)
            embed.add_field(name="Жертва", value=victim, inline=True)
            embed.add_field(name="Fame", value=f"{fame:,}", inline=True)
            await ctx.send(embed=embed)
    except discord.Forbidden:
        logger.error("Немає прав для надсилання повідомлення в канал %s", ctx.channel.id)
    except discord.HTTPException as e:
        logger.error("[КОМАНДА] !scanlive -- помилка Discord: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !scanlive -- збій: %s", e)
        try:
            await ctx.send(f"**Помилка:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def lastkills(ctx, count: int = 10):
    """Показує останні кіли/смерті зі світового логу Albion (без фільтру гільдії)"""
    logger.info("[КОМАНДА] !lastkills (count=%s) від %s", count, ctx.author)
    count = max(1, min(count, 20))

    try:
        events = await get_events(limit=count)
        if not events or not isinstance(events, list):
            await ctx.send("API Альбіону повернув порожній список.")
            return

        logger.info("[КОМАНДА] !lastkills -- отримано %s подій зі світового логу", len(events))
        await ctx.send(f"**Останні {len(events)} подій зі світового логу Albion Online:**")

        for event in events[:count]:
            killer = (event.get("Killer") or {}).get("Name", "?")
            killer_guild = (event.get("Killer") or {}).get("GuildName") or "Без гільдії"
            victim = (event.get("Victim") or {}).get("Name", "?")
            victim_guild = (event.get("Victim") or {}).get("GuildName") or "Без гільдії"
            fame = event.get("TotalVictimKillFame", 0)
            event_id = event.get("EventId", "?")

            embed = discord.Embed(
                title=f"Світова подія #{event_id}",
                url=f"https://albiononline.com/killboard/kill/{event_id}",
                color=0x95a5a6
            )
            embed.add_field(name="Вбивця", value=f"**{killer}** `[{killer_guild}]`", inline=True)
            embed.add_field(name="Жертва", value=f"**{victim}** `[{victim_guild}]`", inline=True)
            embed.add_field(name="Fame", value=f"**{fame:,}**", inline=True)
            await ctx.send(embed=embed)

    except discord.HTTPException as e:
        logger.error("[КОМАНДА] !lastkills -- помилка Discord: %s", e)
    except Exception as e:
        logger.exception("[КОМАНДА] !lastkills -- збій: %s", e)
        try:
            await ctx.send(f"**Помилка:** `{e}`")
        except discord.HTTPException:
            logger.error("Не вдалося відправити повідомлення про помилку в канал.")

@bot.command()
async def info(ctx):
    """Повний список команд бота з детальним описом"""
    logger.info("[КОМАНДА] !info від %s", ctx.author)
    embed = discord.Embed(
        title="x E C L I P S E x -- Killboard Bot",
        description="Бот автоматично моніторить Albion Online API кожні 30 секунд та відправляє сповіщення про вбивства, смерті та асисти гільдії у відповідні канали Discord.",
        color=0xf39c12
    )

    embed.add_field(
        name="!scan",
        value="**Глибоке сканування.** Залазить в логи Albion API та перевіряє 100 останніх подій. "
              "Шукає вбивства, смерті та асисти гільдії. Все знайдене відправляє прямо в чат з детальними картками бою.",
        inline=False
    )
    embed.add_field(
        name="!scanlive",
        value="**Швидкий скан.** Показує 20 останніх подій зі світового логу у компактному форматі (вбивця, жертва, fame).",
        inline=False
    )
    embed.add_field(
        name="!lastkills [кількість]",
        value="**Світовий лог.** Витягує останні кіли зі всього серверу Albion Europe (без фільтру гільдії). "
              "Показує хто кого вбив, з якої гільдії, та скільки Fame. За замовчуванням 10 подій, максимум 20.\n"
              "Приклад: `!lastkills 5`",
        inline=False
    )
    embed.add_field(
        name="!checkapi",
        value="**Перевірка API.** Відправляє тестовий запит до серверів Albion Online та показує статус з'єднання, "
              "ID останньої події та час.",
        inline=False
    )
    embed.add_field(
        name="!guild",
        value="**Статистика гільдії.** Витягує з API повну інформацію: лідер, кількість учасників, альянс, "
              "PvP Kill Fame, PvP Death Fame, та показує в які канали бот відправляє звіти.",
        inline=False
    )
    embed.add_field(
        name="!status",
        value="**Статус моніторингу.** Показує скільки циклів опитування пройшло, скільки подій проскановано, "
              "скільки подій гільдії знайдено, стан кешу дублікатів, налаштування інтервалу та каналів.",
        inline=False
    )
    embed.add_field(
        name="!help",
        value="**Короткий список.** Показує всі команди одним рядком.",
        inline=False
    )
    embed.add_field(
        name="!info",
        value="**Ця сторінка.** Повний список команд з детальним описом кожної.",
        inline=False
    )

    embed.add_field(
        name="Як працює автоматичний моніторинг?",
        value="Бот кожні **30 секунд** відправляє запит до Albion API та отримує **100 останніх подій** у світі. "
              "Потім фільтрує їх по ID гільдії та відправляє:\n"
              "* **Вбивства** -> канал вбивств\n"
              "* **Смерті** -> канал смертей\n"
              "* **Асисти** -> канал вбивств\n"
              "Захист від дублікатів: бот запам'ятовує EventId та не відправляє одну подію двічі.",
        inline=False
    )

    embed.set_footer(text="Бот моніторить Albion API 24/7 | Розробник: EvilHIMARS")
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    """Короткий список команд бота"""
    logger.info("[КОМАНДА] !help від %s", ctx.author)
    embed = discord.Embed(title="Команди бота x E C L I P S E x", color=0xf39c12)
    embed.add_field(name="!info", value="Повний список команд з детальним описом", inline=False)
    embed.add_field(name="!scan", value="Глибоке сканування 100 подій -- пошук кілів/смертей гільдії", inline=False)
    embed.add_field(name="!scanlive", value="Швидкий скан 20 останніх подій (компактний вивід)", inline=False)
    embed.add_field(name="!lastkills [n]", value="Останні n кілів зі світового логу (за замовч. 10, макс. 20)", inline=False)
    embed.add_field(name="!checkapi", value="Перевірка з'єднання з API Albion Online", inline=False)
    embed.add_field(name="!guild", value="Статистика гільдії: учасники, fame, альянс", inline=False)
    embed.add_field(name="!status", value="Статус моніторингу: цикли, події, кеш", inline=False)
    embed.set_footer(text="Напиши !info для детального опису кожної команди | Розробник: EvilHIMARS")
    await ctx.send(embed=embed)

# Запуск всієї екосистеми
keep_alive()
bot.run(TOKEN)
