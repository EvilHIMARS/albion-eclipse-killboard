import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Головний, залізобетонний офіційний хост Альбіону, який Render точно бачить
BASE_URL = "https://gameinfo.albiononline.com/api/gameinfo"

async def get_events(limit=20):
    """Отримує свіжі події з головного стабільного шлюзу Albion"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    # Знижуємо ліміт за замовчуванням до 20, щоб сервер віддавав інфу миттєво
    url = f"{BASE_URL}/events?limit={limit}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        return data
                    return []
                else:
                    logger.warning(f"[API MAIN] Сервер повернув статус {response.status}. Пропуск.")
                    return []
    except Exception as e:
        logger.error(f"[API MAIN ERROR] Помилка підключення до головного сервера: {e}")
        return []

async def get_guild_info(guild_id):
    """Отримує інформацію про гільдію"""
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
