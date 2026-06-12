import aiohttp

BASE_URL = "https://gameinfo.albiononline.com/api/gameinfo"


async def get_events(limit=50):
    url = f"{BASE_URL}/events?limit={limit}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()