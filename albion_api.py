import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Європейський шлюз
BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


async def get_events(limit=50):
    """Отримує глобальні події"""
    url = f"{BASE_URL}/events?limit={limit}"

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    if not isinstance(data, list):
                        logger.warning(
                            "[API EUROPE] Неочікуваний формат відповіді: очікувався list, отримано %s",
                            type(data).__name__,
                        )
                        return []
                    return data
                else:
                    body_preview = await response.text()
                    logger.warning(
                        "[API EUROPE] Статус %s для %s. Тіло: %.200s",
                        response.status, url, body_preview,
                    )
                    return []
    except aiohttp.ClientError as e:
        logger.error("[API ERROR] Мережева помилка при запиті %s: %s", url, e)
        return []
    except TimeoutError:
        logger.error("[API ERROR] Таймаут при запиті %s", url)
        return []
    except Exception as e:
        logger.exception("[API ERROR] Непередбачена помилка при запиті %s: %s", url, e)
        return []


async def get_guild_info(guild_id):
    """Отримує інформацію про гільдію"""
    if not guild_id:
        logger.error("[API] get_guild_info викликано без guild_id")
        return None

    url = f"{BASE_URL}/guilds/{guild_id}"

    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    body_preview = await response.text()
                    logger.warning(
                        "[API] Статус %s для %s. Тіло: %.200s",
                        response.status, url, body_preview,
                    )
                    return None
    except aiohttp.ClientError as e:
        logger.error("[API ERROR] Мережева помилка при запиті %s: %s", url, e)
        return None
    except TimeoutError:
        logger.error("[API ERROR] Таймаут при запиті %s", url)
        return None
    except Exception as e:
        logger.exception("[API ERROR] Непередбачена помилка при запиті %s: %s", url, e)
        return None
