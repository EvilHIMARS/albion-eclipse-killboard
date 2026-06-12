"""Reusable async HTTP client for the Albion Online API."""

import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


async def _api_get(endpoint, params=None):
    """
    Perform a GET request against the Albion API.

    Args:
        endpoint: Path appended to BASE_URL (e.g. "/events").
        params: Optional dict of query parameters.

    Returns:
        Parsed JSON on success (200), or None on failure.
    """
    url = f"{BASE_URL}{endpoint}"
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.get(url, headers=HEADERS, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    body = await response.text()
                    logger.warning(
                        f"[API] GET {endpoint} returned status {response.status}, "
                        f"response: {body[:200]}"
                    )
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"[API NETWORK] GET {endpoint}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.error(f"[API ERROR] GET {endpoint}: {type(e).__name__}: {e}")
        return None


async def get_events(limit=50):
    """Fetch global kill events."""
    data = await _api_get("/events", params={"limit": limit})
    if isinstance(data, list):
        logger.info(f"[API] Отримано {len(data)} подій")
        return data
    return []


async def get_guild_info(guild_id):
    """Fetch guild information by ID."""
    if not guild_id:
        logger.warning("[API] get_guild_info викликано без guild_id")
        return None
    data = await _api_get(f"/guilds/{guild_id}")
    return data if isinstance(data, dict) else None
