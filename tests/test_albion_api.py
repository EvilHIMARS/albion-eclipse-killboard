import pytest
from asyncio import TimeoutError
from aioresponses import aioresponses

from api_client import get_events, get_guild_info, BASE_URL


@pytest.fixture
def mock_aio():
    with aioresponses() as m:
        yield m


# =====================================================================
# get_events
# =====================================================================

@pytest.mark.asyncio
async def test_get_events_returns_list(mock_aio):
    payload = [{"EventId": 1}, {"EventId": 2}]
    mock_aio.get(f"{BASE_URL}/events?limit=50", payload=payload)
    result = await get_events()
    assert result == payload


@pytest.mark.asyncio
async def test_get_events_custom_limit(mock_aio):
    payload = [{"EventId": 99}]
    mock_aio.get(f"{BASE_URL}/events?limit=10", payload=payload)
    result = await get_events(limit=10)
    assert result == payload


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_non_list_response(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", payload={"error": "bad"})
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_server_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", status=500)
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_404(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", status=404)
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_network_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", exception=Exception("Connection failed"))
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_timeout(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", exception=TimeoutError())
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_list_payload(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", payload=[])
    result = await get_events()
    assert result == []


# =====================================================================
# get_guild_info
# =====================================================================

GUILD_ID = "test-guild-abc"


@pytest.mark.asyncio
async def test_get_guild_info_returns_dict(mock_aio):
    payload = {"Name": "Eclipse", "MemberCount": 42}
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", payload=payload)
    result = await get_guild_info(GUILD_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_guild_info_returns_none_on_non_dict(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", payload=[1, 2])
    result = await get_guild_info(GUILD_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_returns_none_on_404(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", status=404)
    result = await get_guild_info(GUILD_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_returns_none_on_500(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", status=500)
    result = await get_guild_info(GUILD_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_returns_none_on_network_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", exception=Exception("DNS fail"))
    result = await get_guild_info(GUILD_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_returns_none_on_timeout(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}", exception=TimeoutError())
    result = await get_guild_info(GUILD_ID)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_none_guild_id():
    result = await get_guild_info(None)
    assert result is None


@pytest.mark.asyncio
async def test_get_guild_info_empty_guild_id():
    result = await get_guild_info("")
    assert result is None
