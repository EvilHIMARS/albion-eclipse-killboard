from unittest.mock import AsyncMock

import albion_api

# bot.py imports get_guild_info which is not defined in albion_api.py;
# patch it here so that ``import bot`` does not raise ImportError.
if not hasattr(albion_api, "get_guild_info"):
    albion_api.get_guild_info = AsyncMock(return_value={})
