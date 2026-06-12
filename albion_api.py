import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Використовуємо офіційний європейський шлюз
BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

async def get_events(limit=50):
    """Отримує глобальні події (без фільтрації на сервері, щоб уникнути 400)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    url = f"{BASE_URL}/events?limit={limit}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                else:
                    logger.warning(f"[API EUROPE] Статус {response.status}. Спробуємо пізніше.")
                    return []
    except Exception as e:
        logger.error(f"[API ERROR] {e}")
        return []

async def get_guild_info(guild_id):
    """Повертає інформацію про гільдію"""
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
