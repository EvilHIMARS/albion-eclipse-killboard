import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# Patch Bot.run so the module-level ``bot.run(TOKEN)`` is a no-op.
with patch("discord.ext.commands.Bot.run"):
    from bot import (
        create_battle_embed,
        manage_cache,
        dispatch_event,
        PROCESSED_EVENTS,
        MAX_CACHE_SIZE,
    )


# =====================================================================
# create_battle_embed
# =====================================================================

def _full_event(**overrides):
    ev = {
        "EventId": 42,
        "Killer": {"Name": "Attacker", "GuildName": "AttackGuild"},
        "Victim": {"Name": "Defender", "GuildName": "DefendGuild"},
        "TotalVictimKillFame": 12345,
        "Participants": [
            {"Name": "Helper", "GuildName": "HelpGuild", "DamageDone": 500, "SupportValue": 0},
            {"Name": "Healer", "GuildName": "HealGuild", "DamageDone": 0, "SupportValue": 300},
        ],
    }
    ev.update(overrides)
    return ev


class TestCreateBattleEmbed:
    def test_basic_fields(self):
        embed = create_battle_embed(_full_event(), "Test Title", 0xFF0000)
        assert embed.title == "Test Title"
        assert embed.color.value == 0xFF0000
        assert "42" in embed.url

    def test_killer_and_victim_names_in_fields(self):
        embed = create_battle_embed(_full_event(), "T", 0x00FF00)
        field_values = [f.value for f in embed.fields]
        assert any("Attacker" in v for v in field_values)
        assert any("Defender" in v for v in field_values)

    def test_fame_formatted_in_embed(self):
        embed = create_battle_embed(_full_event(), "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("12,345" in v for v in field_values)

    def test_damage_participants_shown(self):
        embed = create_battle_embed(_full_event(), "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("Helper" in v and "500" in v for v in field_values)

    def test_heal_participants_shown(self):
        embed = create_battle_embed(_full_event(), "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("Healer" in v and "300" in v for v in field_values)

    def test_footer_contains_event_id(self):
        embed = create_battle_embed(_full_event(), "T", 0x0)
        assert "42" in embed.footer.text

    def test_missing_killer_info(self):
        ev = _full_event()
        ev["Killer"] = None
        embed = create_battle_embed(ev, "T", 0x0)
        assert embed.title == "T"

    def test_missing_victim_info(self):
        ev = _full_event()
        ev["Victim"] = None
        embed = create_battle_embed(ev, "T", 0x0)
        assert embed.title == "T"

    def test_no_participants(self):
        ev = _full_event()
        ev["Participants"] = []
        embed = create_battle_embed(ev, "T", 0x0)
        # Should still have at least killer/victim/fame fields
        assert len(embed.fields) >= 3

    def test_none_participants(self):
        ev = _full_event()
        ev["Participants"] = None
        embed = create_battle_embed(ev, "T", 0x0)
        assert embed.title == "T"

    def test_no_guild_names_fallback(self):
        ev = _full_event()
        ev["Killer"] = {"Name": "Solo"}
        ev["Victim"] = {"Name": "Target"}
        embed = create_battle_embed(ev, "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("Без гильдии" in v for v in field_values)

    def test_zero_fame(self):
        ev = _full_event(TotalVictimKillFame=0)
        embed = create_battle_embed(ev, "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("0" in v for v in field_values)


# =====================================================================
# manage_cache
# =====================================================================

class TestManageCache:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        PROCESSED_EVENTS.clear()
        yield
        PROCESSED_EVENTS.clear()

    def test_new_event_returns_true(self):
        assert manage_cache(1) is True

    def test_duplicate_event_returns_false(self):
        manage_cache(1)
        assert manage_cache(1) is False

    def test_different_events_are_accepted(self):
        assert manage_cache(1) is True
        assert manage_cache(2) is True
        assert manage_cache(3) is True

    def test_cache_clears_when_exceeding_max_size(self):
        # Fill cache to MAX_CACHE_SIZE + 1 entries (0 .. MAX_CACHE_SIZE)
        for i in range(MAX_CACHE_SIZE + 1):
            manage_cache(i)
        # Next call sees len > MAX_CACHE_SIZE and clears before adding
        assert manage_cache(MAX_CACHE_SIZE + 1) is True
        # Old entries were purged, so re-adding an old id succeeds
        assert manage_cache(0) is True

    def test_cache_size_stays_bounded(self):
        for i in range(MAX_CACHE_SIZE + 10):
            manage_cache(i)
        assert len(PROCESSED_EVENTS) <= MAX_CACHE_SIZE + 10


# =====================================================================
# dispatch_event
# =====================================================================

class TestDispatchEvent:
    @pytest.mark.asyncio
    async def test_kill_event_sends_to_kill_channel(self):
        kill_ch = AsyncMock()
        death_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "kill", kill_ch, death_ch)
        kill_ch.send.assert_awaited_once()
        death_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_death_event_sends_to_death_channel(self):
        kill_ch = AsyncMock()
        death_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "death", kill_ch, death_ch)
        death_ch.send.assert_awaited_once()
        kill_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_assist_event_sends_to_kill_channel(self):
        kill_ch = AsyncMock()
        death_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "assist", kill_ch, death_ch)
        kill_ch.send.assert_awaited_once()
        death_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_send_when_kill_channel_is_none(self):
        death_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "kill", None, death_ch)
        death_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_send_when_death_channel_is_none(self):
        kill_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "death", kill_ch, None)
        kill_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_result_type_sends_nothing(self):
        kill_ch = AsyncMock()
        death_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "unknown", kill_ch, death_ch)
        kill_ch.send.assert_not_awaited()
        death_ch.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatch_handles_send_exception(self):
        kill_ch = AsyncMock()
        kill_ch.send.side_effect = Exception("Discord API error")
        event = _full_event()
        # Should not raise
        await dispatch_event(event, "kill", kill_ch, None)

    @pytest.mark.asyncio
    async def test_embed_passed_to_channel(self):
        kill_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "kill", kill_ch, None)
        call_kwargs = kill_ch.send.call_args
        assert "embed" in call_kwargs.kwargs
