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
# 📊 НАСТРОЙКА СИСТЕМНОГО ЛОГИРОВАНИЯ (Пункт 7)
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
    # Отключаем лишний спам логов Flask в консоли
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
    logger.info("Внутренний веб-сервер Uptime успешно запущен на порту 10000.")

# ==========================================
# ⚙️ ИНИЦИАЛИЗАЦИЯ И НАСТРОЙКИ БОТА
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

# 🧠 ЗАЩИТА ОТ ДУБЛЕЙ С ОПТИМИЗАЦИЕЙ ПАМЯТИ (Пункт 5)
# Используем set, но контролируем его размер, чтобы избежать утечки памяти через недели аптайма
PROCESSED_EVENTS = set()
MAX_CACHE_SIZE = 2000

# ==========================================
# 🧾 УЛУЧШЕННЫЙ ФОРМАТ EMBED-СООБЩЕНИЙ (Пункт 6)
# ==========================================
def create_battle_embed(event, title, color_hex):
    """Генерирует высокоинформативную карточку боя с прямыми ссылками"""
    event_id = event.get("EventId", 0)
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    fame = event.get("TotalVictimKillFame", 0)
    
    killer_name = killer.get('Name', 'Неизвестно')
    killer_guild = killer.get('GuildName') or 'Без гильдии'
    victim_name = victim.get('Name', 'Неизвестно')
    victim_guild = victim.get('GuildName') or 'Без гильдии'
    
    # Ссылка на официальный киллборд Albion Online
    killboard_url = f"https://albiononline.com/killboard/kill/{event_id}"
    
    embed = discord.Embed(
        title=title, 
        url=killboard_url, 
        color=color_hex,
        description=f"🔗 [Открыть этот бой на официальном Киллборде]({killboard_url})"
    )
    
    embed.add_field(name="⚔️ Убийца", value=f"**{killer_name}**\n`[{killer_guild}]`", inline=True)
    embed.add_field(name="💀 Жертва", value=f"**{victim_name}**\n`[{victim_guild}]`", inline=True)
    embed.add_field(name="✨ Слава за убийство (Fame)", value=f"🏆 **{fame:,}**", inline=False)
    
    # Парсинг участников боя (нанесение урона и хил)
    participants = event.get("Participants") or []
    if participants:
        damage_list = []
        heal_list = []
        
        for p in participants:
            name = p.get("Name", "Неизвестно")
            guild = p.get("GuildName") or "Без гильдии"
            dmg = p.get("DamageDone", 0)
            heal = p.get("SupportValue", 0)
            
            if dmg > 0:
                damage_list.append(f"• **{name}** `[{guild}]`: {dmg:,} DMG")
            if heal > 0:
                heal_list.append(f"• **{name}** `[{guild}]`: {heal:,} HEAL")
        
        if damage_list:
            embed.add_field(name="📈 Распределение урона:", value="\n".join(damage_list[:5]), inline=False)
        if heal_list:
            embed.add_field(name="💚 Поддержка и исцеление:", value="\n".join(heal_list[:5]), inline=False)
            
    embed.set_footer(text=f"ID события: {event_id} | Разработчик: EvilHIMARS")
    return embed

# ==========================================
# 🧩 РАЗБИВКА НА МЕНЕДЖЕРЫ И АТОМАРНЫЕ ФУНКЦИИ (Пункт 8)
# ==========================================
def manage_cache(event_id):
    """Контролирует защиту от дубликатов и очищает старый кэш при переполнении"""
    global PROCESSED_EVENTS
    if event_id in PROCESSED_EVENTS:
        return False
        
    # Предотвращаем бесконечный рост set в оперативной памяти
    if len(PROCESSED_EVENTS) > MAX_CACHE_SIZE:
        logger.info("Кэш дубликатов заполнен. Проводится плановая очистка памяти...")
        PROCESSED_EVENTS.clear()
        
    PROCESSED_EVENTS.add(event_id)
    return True

async def dispatch_event(event, result_type, kill_ch, death_ch):
    """Изолированная функция отправки конкретного события в нужный канал"""
    event_id = event.get("EventId")
    try:
        if result_type == "kill":
            embed = create_battle_embed(event, "☠️ НОВОЕ УБИЙСТВО ГИЛЬДИИ", 0x2ecc71)
            if kill_ch: 
                await kill_ch.send(embed=embed)
                logger.info(f"[ОТПРАВКА] Успешно отправлен лог убийства #{event_id} в канал")
                
        elif result_type == "death":
            embed = create_battle_embed(event, "💀 ПОТЕРЯ В БОЮ (СМЕРТЬ)", 0xe74c3c)
            if death_ch: 
                await death_ch.send(embed=embed)
                logger.info(f"[ОТПРАВКА] Успешно отправлен лог смерти #{event_id} в канал")
                
        elif result_type == "assist":
            embed = create_battle_embed(event, "🤝 АССИСТ ГИЛЬДИИ В УБИЙСТВЕ", 0x3498db)
            if kill_ch: 
                await kill_ch.send(embed=embed)
                logger.info(f"[ОТПРАВКА] Успешно отправлен лог ассиста #{event_id} в канал")
    except Exception as dispatch_err:
        logger.error(f"Не удалось отправить сообщение в Discord для #{event_id}: {dispatch_err}")

# ==========================================
# 🔁 СТАБИЛЬНЫЙ ЦИКЛ РАБОТЫ 24/7 (Пункт 9)
# ==========================================
async def monitor_loop():
    """Главный изолированный цикл мониторинга, устойчивый к любым ошибкам сетей и API"""
    await bot.wait_until_ready()
    
    kill_channel = bot.get_channel(KILL_CHANNEL_ID)
    death_channel = bot.get_channel(DEATH_CHANNEL_ID)
    
    logger.info("Автоматический фоновый мониторинг Albion API успешно запущен.")

    while not bot.is_closed():
        try:
            # Запрашиваем 100 свежих событий (Прайм-тайм покрытие)
            events = await get_events(limit=100)
            
            if not events or not isinstance(events, list):
                logger.warning("[API] Сервер Albion вернул пустой список или недоступен. Пропуск итерации.")
                await asyncio.sleep(30)
                continue
                
            guild_activity_detected = False
            
            for event in events:
                event_id = event.get("EventId")
                if not event_id: 
                    continue
                
                # Проверка на дубликат (Пункт 5)
                if not manage_cache(event_id):
                    continue
                
                # Фильтрация принадлежности к нашей гильдии
                result_type = is_guild_kill(event)
                if not result_type: 
                    continue
                
                guild_activity_detected = True
                # Отправка события (Пункт 8)
                await dispatch_event(event, result_type, kill_channel, death_channel)
            
            if not guild_activity_detected:
                logger.info(f"[ЦИКЛ] Просканировано {len(events)} мировых событий. Активности x E C L I P S E x не обнаружено.")
                
        except asyncio.CancelledError:
            logger.info("Цикл мониторинга остановлен администратором.")
            break
        except Exception as global_loop_error:
            # Бот никогда не упадет и не зависнет здесь (Пункт 9)
            logger.error(f"[ОШИБКА ЦИКЛА] Перехват критического сбоя: {global_loop_error}. Перезапуск через 30 секунд...")
            
        await asyncio.sleep(30)

# ==========================================
# 🧼 СОБЫТИЯ И КЛИНИНГ КОДА (Пункт 10)
# ==========================================
@bot.event
async def on_ready():
    logger.info("========================================")
    logger.info(f" СИСТЕМА УСПЕШНО ЗАПУЩЕНА И АВТОРИЗОВАНА")
    logger.info(f" Имя бота в Discord: {bot.user.name} (ID: {bot.user.id})")
    logger.info("========================================")
    
    # Запуск фонового процесса
    bot.loop.create_task(monitor_loop())

@bot.command()
async def checkapi(ctx):
    """Быстрая проверка доступности шлюза Albion"""
    try:
        events = await get_events(limit=1)
        if events and isinstance(events, list):
            await ctx.send(f"🟢 **API Albion Online стабильно.** ID последнего события в мире: `{events[0].get('EventId')}`")
        else:
            await ctx.send("🟡 **API вернуло пустой массив данных.** Возможно сервера игры перегружены.")
    except Exception as e:
        logger.error(f"Команда !checkapi вызвала сбой: {e}")
        await ctx.send(f"🔴 **Ошибка соединения с API:** `{str(e)}`")

# Запуск всей экосистемы
keep_alive()
bot.run(TOKEN)
