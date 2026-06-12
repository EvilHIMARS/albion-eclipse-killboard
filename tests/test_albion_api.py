import pytest
from asyncio import TimeoutError
from aioresponses import aioresponses

from albion_api import (
    get_events, get_guild_info, get_guild_top,
    search_player, get_player_info, get_player_kills, get_player_deaths,
    get_event_details, get_guild_members, BASE_URL
)


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


# =====================================================================
# get_guild_top
# =====================================================================

@pytest.mark.asyncio
async def test_get_guild_top_returns_list(mock_aio):
    payload = [{"EventId": 1, "Killer": {"Name": "X"}}]
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}/top?range=week&limit=10", payload=payload)
    result = await get_guild_top(GUILD_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_guild_top_empty_guild():
    result = await get_guild_top("")
    assert result == []


@pytest.mark.asyncio
async def test_get_guild_top_returns_empty_on_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}/top?range=week&limit=10", status=500)
    result = await get_guild_top(GUILD_ID)
    assert result == []


# =====================================================================
# search_player
# =====================================================================

@pytest.mark.asyncio
async def test_search_player_returns_players(mock_aio):
    payload = {"players": [{"Id": "abc", "Name": "Test"}], "guilds": []}
    mock_aio.get(f"{BASE_URL}/search?q=Test", payload=payload)
    result = await search_player("Test")
    assert len(result) == 1
    assert result[0]["Name"] == "Test"


@pytest.mark.asyncio
async def test_search_player_empty_name():
    result = await search_player("")
    assert result == []


@pytest.mark.asyncio
async def test_search_player_returns_empty_on_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/search?q=Nobody", status=404)
    result = await search_player("Nobody")
    assert result == []


# =====================================================================
# get_player_info
# =====================================================================

PLAYER_ID = "test-player-123"


@pytest.mark.asyncio
async def test_get_player_info_returns_dict(mock_aio):
    payload = {"Name": "Hero", "KillFame": 1000}
    mock_aio.get(f"{BASE_URL}/players/{PLAYER_ID}", payload=payload)
    result = await get_player_info(PLAYER_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_player_info_none_id():
    result = await get_player_info(None)
    assert result is None


@pytest.mark.asyncio
async def test_get_player_info_returns_none_on_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/players/{PLAYER_ID}", status=500)
    result = await get_player_info(PLAYER_ID)
    assert result is None


# =====================================================================
# get_player_kills / get_player_deaths
# =====================================================================

@pytest.mark.asyncio
async def test_get_player_kills_returns_list(mock_aio):
    payload = [{"EventId": 1}]
    mock_aio.get(f"{BASE_URL}/players/{PLAYER_ID}/kills?limit=10", payload=payload)
    result = await get_player_kills(PLAYER_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_player_kills_empty_id():
    result = await get_player_kills("")
    assert result == []


@pytest.mark.asyncio
async def test_get_player_deaths_returns_list(mock_aio):
    payload = [{"EventId": 2}]
    mock_aio.get(f"{BASE_URL}/players/{PLAYER_ID}/deaths?limit=10", payload=payload)
    result = await get_player_deaths(PLAYER_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_player_deaths_empty_id():
    result = await get_player_deaths("")
    assert result == []


# =====================================================================
# get_event_details
# =====================================================================

@pytest.mark.asyncio
async def test_get_event_details_returns_dict(mock_aio):
    payload = {"EventId": 999, "Killer": {"Name": "X"}}
    mock_aio.get(f"{BASE_URL}/events/999", payload=payload)
    result = await get_event_details(999)
    assert result == payload


@pytest.mark.asyncio
async def test_get_event_details_none_id():
    result = await get_event_details(None)
    assert result is None


@pytest.mark.asyncio
async def test_get_event_details_returns_none_on_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/events/999", status=404)
    result = await get_event_details(999)
    assert result is None


# =====================================================================
# get_guild_members
# =====================================================================

@pytest.mark.asyncio
async def test_get_guild_members_returns_list(mock_aio):
    payload = [{"Id": "p1", "Name": "Player1"}]
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}/members", payload=payload)
    result = await get_guild_members(GUILD_ID)
    assert result == payload


@pytest.mark.asyncio
async def test_get_guild_members_empty_guild():
    result = await get_guild_members("")
    assert result == []


@pytest.mark.asyncio
async def test_get_guild_members_returns_empty_on_error(mock_aio):
    mock_aio.get(f"{BASE_URL}/guilds/{GUILD_ID}/members", status=500)
    result = await get_guild_members(GUILD_ID)
    assert result == []
