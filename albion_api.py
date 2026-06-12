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


async def _api_get_json(url):
    """Загальний GET-запит до API Albion, повертає розпарсений JSON або None"""
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    body = await response.text()
                    logger.warning(f"[API] Статус {response.status} для {url[:80]}, відповідь: {body[:200]}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"[API NETWORK] {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"[API ERROR] {type(e).__name__}: {e}")
        return None


async def get_events(limit=50):
    """Отримуємо глобальні події (без фільтрації на сервері, щоб уникнути 400)"""
    url = f"{BASE_URL}/events?limit={limit}"
    data = await _api_get_json(url)
    if isinstance(data, list):
        logger.info(f"[API] Отримано {len(data)} подій")
        return data
    return []


async def get_guild_info(guild_id):
    """Отримуємо інформацію про гільдію за її ID"""
    if not guild_id:
        logger.warning("[API] get_guild_info викликано без guild_id")
        return None
    url = f"{BASE_URL}/guilds/{guild_id}"
    data = await _api_get_json(url)
    return data if isinstance(data, dict) else None


async def get_guild_top(guild_id, range_type="week", limit=10):
    """Топ кілів гільдії за період (week/month/lastWeek/lastMonth)"""
    if not guild_id:
        return []
    url = f"{BASE_URL}/guilds/{guild_id}/top?range={range_type}&limit={limit}"
    data = await _api_get_json(url)
    return data if isinstance(data, list) else []


async def search_player(name):
    """Пошук гравця за ім'ям, повертає список знайдених"""
    if not name:
        return []
    url = f"{BASE_URL}/search?q={name}"
    data = await _api_get_json(url)
    if isinstance(data, dict):
        return data.get("players", [])
    return []


async def get_player_info(player_id):
    """Отримуємо детальну інформацію про гравця"""
    if not player_id:
        return None
    url = f"{BASE_URL}/players/{player_id}"
    data = await _api_get_json(url)
    return data if isinstance(data, dict) else None


async def get_player_kills(player_id, limit=10):
    """Отримуємо останні вбивства гравця"""
    if not player_id:
        return []
    url = f"{BASE_URL}/players/{player_id}/kills?limit={limit}"
    data = await _api_get_json(url)
    return data if isinstance(data, list) else []


async def get_player_deaths(player_id, limit=10):
    """Отримуємо останні смерті гравця"""
    if not player_id:
        return []
    url = f"{BASE_URL}/players/{player_id}/deaths?limit={limit}"
    data = await _api_get_json(url)
    return data if isinstance(data, list) else []


async def get_event_details(event_id):
    """Отримуємо детальну інформацію про конкретну подію"""
    if not event_id:
        return None
    url = f"{BASE_URL}/events/{event_id}"
    data = await _api_get_json(url)
    return data if isinstance(data, dict) else None


async def get_guild_members(guild_id):
    """Отримуємо список учасників гільдії"""
    if not guild_id:
        return []
    url = f"{BASE_URL}/guilds/{guild_id}/members"
    data = await _api_get_json(url)
    return data if isinstance(data, list) else []
