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
# НАСТРОЙКА СИСТЕМНОГО ЛОГИРОВАНИЯ
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AlbionBot")

# --- WEB-СЕРВЕР ДЛЯ ПОДДЕРЖАНИЯ АКТИВНОСТИ (Uptime) ---
app = Flask('')


@app.route('/')
def home():
    return "Бот активен и осуществляет мониторинг логов!"


def run_server():
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=10000)


def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
    logger.info("Внутренний веб-сервер Uptime успешно запущен на порту 10000.")


# ==========================================
# ИНИЦИАЛИЗАЦИЯ И НАСТРОЙКИ БОТА
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

try:
    KILL_CHANNEL_ID = int(os.getenv("KILL_CHANNEL_ID") or 0)
    DEATH_CHANNEL_ID = int(os.getenv("DEATH_CHANNEL_ID") or 0)
except ValueError:
    logger.error("Критическая ошибка: ID каналов в .env указаны некорректно!")
    KILL_CHANNEL_ID = 0
    DEATH_CHANNEL_ID = 0

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Защита от дубликатов с контролем размера кэша
PROCESSED_EVENTS = set()
MAX_CACHE_SIZE = 2000

# ==========================================
# КОНФИГУРАЦИЯ ТИПОВ СОБЫТИЙ
# ==========================================
# Maps result_type -> (title, embed color, channel selector key)
EVENT_TYPE_CONFIG = {
    "kill": ("☠️ НОВОЕ УБИЙСТВО ГИЛЬДИИ", 0x2ecc71, "kill"),
    "death": ("💀 ПОТЕРЯ В БОЮ (СМЕРТЬ)", 0xe74c3c, "death"),
    "assist": ("🤝 АССИСТ ГИЛЬДИИ В УБИЙСТВЕ", 0x3498db, "kill"),
}


# ==========================================
# ФОРМАТ EMBED-СООБЩЕНИЙ
# ==========================================
def create_battle_embed(event, title, color_hex):
    """Генерирует информативную карточку боя с прямыми ссылками."""
    event_id = event.get("EventId", 0)
    fame = event.get("TotalVictimKillFame", 0)

    killer = extract_player(event, "Killer")
    victim = extract_player(event, "Victim")

    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"

    embed = discord.Embed(
        title=title,
        url=killboard_url,
        color=color_hex,
        description=f"🔗 [Открыть этот бой на официальном Киллборде]({killboard_url})"
    )

    embed.add_field(
        name="⚔️ Убийца",
        value=f"**{killer['name']}**\n`[{killer['guild_name']}]`",
        inline=True,
    )
    embed.add_field(
        name="💀 Жертва",
        value=f"**{victim['name']}**\n`[{victim['guild_name']}]`",
        inline=True,
    )
    embed.add_field(
        name="✨ Слава за убийство (Fame)",
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
                name="📈 Распределение урона:",
                value="\n".join(damage_list[:5]),
                inline=False,
            )
        if heal_list:
            embed.add_field(
                name="💚 Поддержка и исцеление:",
                value="\n".join(heal_list[:5]),
                inline=False,
            )

    embed.set_footer(text=f"ID события: {event_id} | Разработчик: EvilHIMARS")
    return embed


# ==========================================
# МЕНЕДЖЕРЫ И АТОМАРНЫЕ ФУНКЦИИ
# ==========================================
def manage_cache(event_id):
    """Контролирует защиту от дубликатов и очищает старый кэш при переполнении."""
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False

    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info("Кэш дубликатов заполнен. Проводится плановая очистка памяти...")
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

    try:
        embed = create_battle_embed(event, title, color)
        await channel.send(embed=embed)
        logger.info(f"[ОТПРАВКА] Успешно отправлен лог {result_type} #{event_id} в канал")
    except Exception as dispatch_err:
        logger.error(
            f"Не удалось отправить сообщение в Discord для #{event_id}: {dispatch_err}"
        )


# ==========================================
# СТАБИЛЬНЫЙ ЦИКЛ РАБОТЫ 24/7
# ==========================================
async def monitor_loop():
    """Главный изолированный цикл мониторинга, устойчивый к ошибкам сетей и API."""
    await bot.wait_until_ready()

    channels = {
        "kill": bot.get_channel(KILL_CHANNEL_ID),
        "death": bot.get_channel(DEATH_CHANNEL_ID),
    }

    logger.info("Автоматический фоновый мониторинг Albion API успешно запущен.")

    while not bot.is_closed():
        try:
            events = await get_events(limit=100)

            if not events or not isinstance(events, list):
                logger.warning(
                    "[API] Сервер Albion вернул пустой список или недоступен. Пропуск итерации."
                )
                await asyncio.sleep(30)
                continue

            guild_activity_detected = False

            for event in events:
                event_id = event.get("EventId")
                if not event_id:
                    continue

                if not manage_cache(event_id):
                    continue

                result_type = is_guild_kill(event)
                if not result_type:
                    continue

                guild_activity_detected = True
                await dispatch_event(event, result_type, channels)

            if not guild_activity_detected:
                logger.info(
                    f"[ЦИКЛ] Просканировано {len(events)} мировых событий. "
                    "Активности x E C L I P S E x не обнаружено."
                )

        except asyncio.CancelledError:
            logger.info("Цикл мониторинга остановлен администратором.")
            break
        except Exception as global_loop_error:
            logger.error(
                f"[ОШИБКА ЦИКЛА] Перехват критического сбоя: {global_loop_error}. "
                "Перезапуск через 30 секунд..."
            )

        await asyncio.sleep(30)


# ==========================================
# СОБЫТИЯ DISCORD
# ==========================================
@bot.event
async def on_ready():
    logger.info("========================================")
    logger.info(" СИСТЕМА УСПЕШНО ЗАПУЩЕНА И АВТОРИЗОВАНА")
    logger.info(f" Имя бота в Discord: {bot.user.name} (ID: {bot.user.id})")
    logger.info("========================================")
    bot.loop.create_task(monitor_loop())


@bot.command()
async def scanlive(ctx):
    """Сканування 20 останніх подій."""
    events = await get_events(limit=20)
    if not events:
        await ctx.send("❌API не відповіло або подій немає.")
        return

    for event in events:
        embed = create_battle_embed(event, "⚔ Подія", discord.Color.blue().value)
        await ctx.send(embed=embed)


@bot.command()
async def checkapi(ctx):
    """Перевірка статусу API."""
    events = await get_events(limit=1)
    if events:
        await ctx.send("🟢API працює стабільно.")
    else:
        await ctx.send("🔴API недоступне.")


@bot.command()
async def guild(ctx):
    """Статистика гільдії."""
    data = await get_guild_info(GUILD_ID)
    if data:
        await ctx.send(
            f"🏰Гільдія: {data.get('Name')} | Учасників: {data.get('MemberCount')}"
        )
    else:
        await ctx.send("❌Не вдалося отримати дані.")


# Запуск всей экосистемы
keep_alive()
bot.run(TOKEN)
