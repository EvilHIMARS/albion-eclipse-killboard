import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def get_events(limit=50):
    """Отримуємо глобальні події (без фільтрації на сервері, щоб уникнути 400)"""
    url = f"{BASE_URL}/events?limit={limit}"

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"[API] Отримано {len(data) if isinstance(data, list) else 0} подій")
                    return data if isinstance(data, list) else []
                else:
                    body = await response.text()
                    logger.warning(
                        f"[API EUROPE] Статус {response.status}, "
                        f"відповідь: {body[:200]}"
                    )
                    return []
    except aiohttp.ClientError as e:
        logger.error(f"[API NETWORK] Помилка мережі: {type(e).__name__}: {e}")
        return []
    except Exception as e:
        logger.error(f"[API ERROR] {type(e).__name__}: {e}")
        return []


async def get_guild_info(guild_id):
    """Отримуємо інформацію про гільдію за її ID"""
    if not guild_id:
        logger.warning("[API] get_guild_info викликано без guild_id")
        return None

    url = f"{BASE_URL}/guilds/{guild_id}"

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, dict) else None
                else:
                    logger.warning(
                        f"[API GUILD] Статус {response.status} для гільдії {guild_id}"
                    )
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"[API GUILD NETWORK] {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"[API GUILD ERROR] {type(e).__name__}: {e}")
        return None
