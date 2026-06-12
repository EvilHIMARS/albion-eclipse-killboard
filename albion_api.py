import os
import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Офіційний європейський шлюз
BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

async def get_events(limit=20):
    """Отримує свіжі події конкретної гільдії, щоб уникнути блокування та помилки 400"""
    # Беремо ID гільдії з налаштувань оточення
    guild_id = os.getenv("GUILD_ID")
    
    if not guild_id:
        logger.error("[API EUROPE] Критична помилка: GUILD_ID не знайдено в змінних оточення (.env)!")
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Фільтруємо події за вашою гільдією прямо на сервері Альбіону.
    # Це єдиний формат запиту, який сервер зараз приймає стабільно!
    url = f"{BASE_URL}/events?limit={limit}&offset=0&guildId={guild_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        return data
                    return []
                else:
                    logger.warning(f"[API EUROPE] Сервер повернув статус {response.status} для гільдії {guild_id}. Пропуск.")
                    return []
    except Exception as e:
        logger.error(f"[API EUROPE ERROR] Помилка підключення до європейського сервера: {e}")
        return []

async def get_guild_info(guild_id):
    """Отримує інформацію про гільдію з європейського сервера"""
    if not guild_id:
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"{BASE_URL}/guilds/{guild_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception:
        return None
