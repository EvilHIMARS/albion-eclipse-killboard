import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Використовуємо стабільний альтернативний хост-дзеркало Альбіону (Albion2D)
BASE_URL = "https://gameinfo.albiononline2d.com/api/gameinfo"

async def get_events(limit=50):
    """Отримує свіжі події з альтернативного стабільного хосту"""
    # Для цього хосту потрібен правильний User-Agent, щоб він не блокував запити
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
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
                    logger.warning(f"[API ALTERNATIVE] Хост повернув статус {response.status}. Пробуємо перечекати.")
                    return []
    except Exception as e:
        logger.error(f"[API ALTERNATIVE ERROR] Не вдалося зв'язатися з альтернативним хостом: {e}")
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
