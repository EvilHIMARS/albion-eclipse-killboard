import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aioresponses import aioresponses

from albion_api import get_events, BASE_URL


@pytest.fixture
def mock_aio():
    with aioresponses() as m:
        yield m


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
    from asyncio import TimeoutError
    mock_aio.get(f"{BASE_URL}/events?limit=50", exception=TimeoutError())
    result = await get_events()
    assert result == []


@pytest.mark.asyncio
async def test_get_events_returns_empty_list_payload(mock_aio):
    mock_aio.get(f"{BASE_URL}/events?limit=50", payload=[])
    result = await get_events()
    assert result == []
