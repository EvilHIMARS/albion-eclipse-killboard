"""Reusable async HTTP client for the Albion Online API."""

import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

_REQUEST_TIMEOUT = 15


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
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=_HEADERS, params=params, timeout=_REQUEST_TIMEOUT
            ) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(
                    f"[API] GET {endpoint} returned status {response.status}"
                )
                return None
    except Exception as e:
        logger.error(f"[API ERROR] GET {endpoint}: {e}")
        return None


async def get_events(limit=50):
    """Fetch global kill events."""
    data = await _api_get("/events", params={"limit": limit})
    return data if isinstance(data, list) else []


async def get_guild_info(guild_id):
    """Fetch guild information by ID."""
    data = await _api_get(f"/guilds/{guild_id}")
    return data if isinstance(data, dict) else {}
