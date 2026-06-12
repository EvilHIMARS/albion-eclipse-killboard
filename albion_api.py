import aiohttp
import logging

logger = logging.getLogger("AlbionBot.API")

# Використовуємо стандартний європейський шлюз для всіх подій
BASE_URL = "https://gameinfo-ams.albiononline.com/api/gameinfo"

async def get_events(limit=50):
    """Отримуємо глобальні події (без фільтрації на сервері, щоб уникнути 400)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Запит без фільтрів, який сервер гарантовано приймає (статус 200)
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
