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
        _format_item_name,
        _get_equipment_text,
        t,
    )


# =====================================================================
# create_battle_embed
# =====================================================================

def _full_event(**overrides):
    ev = {
        "EventId": 42,
        "Killer": {
            "Name": "Attacker", "GuildName": "AttackGuild",
            "AverageItemPower": 1200,
            "Equipment": {
                "MainHand": {"Type": "T6_MAIN_SPEAR@2", "Count": 1, "Quality": 3},
                "Armor": {"Type": "T5_ARMOR_PLATE_SET1", "Count": 1, "Quality": 2},
                "Head": None, "Shoes": None, "OffHand": None,
                "Bag": None, "Cape": None, "Mount": None, "Potion": None, "Food": None,
            }
        },
        "Victim": {
            "Name": "Defender", "GuildName": "DefendGuild",
            "AverageItemPower": 800,
            "Equipment": {
                "MainHand": {"Type": "T4_2H_BOW_KEEPER@1", "Count": 1, "Quality": 2},
                "Armor": None, "Head": None, "Shoes": None, "OffHand": None,
                "Bag": None, "Cape": None, "Mount": None, "Potion": None, "Food": None,
            }
        },
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
        no_guild = t("no_guild")
        assert any(no_guild in v for v in field_values)

    def test_zero_fame(self):
        ev = _full_event(TotalVictimKillFame=0)
        embed = create_battle_embed(ev, "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("0" in v for v in field_values)

    def test_equipment_shown_in_embed(self):
        ev = _full_event()
        embed = create_battle_embed(ev, "T", 0x0)
        field_names = [f.name for f in embed.fields]
        assert any(t("killer_gear") in n for n in field_names)

    def test_ip_shown_in_embed(self):
        ev = _full_event()
        embed = create_battle_embed(ev, "T", 0x0)
        field_values = [f.value for f in embed.fields]
        assert any("1200" in v for v in field_values)


# =====================================================================
# _format_item_name / _get_equipment_text
# =====================================================================

class TestEquipmentFormatting:
    def test_format_item_name_basic(self):
        result = _format_item_name("T6_MAIN_SPEAR@2")
        assert "T6" in result
        assert "SPEAR" in result
        assert ".2" in result

    def test_format_item_name_no_enchant(self):
        result = _format_item_name("T5_ARMOR_PLATE_SET1")
        assert "T5" in result
        assert ".0" not in result  # no enchant 0

    def test_format_item_name_none(self):
        assert _format_item_name(None) == "—"

    def test_format_item_name_empty(self):
        assert _format_item_name("") == "—"

    def test_get_equipment_text_with_items(self):
        eq = {
            "MainHand": {"Type": "T6_MAIN_SPEAR@2", "Count": 1, "Quality": 3},
            "Armor": {"Type": "T5_ARMOR_PLATE_SET1", "Count": 1, "Quality": 2},
            "Head": None, "Shoes": None, "Cape": None, "Mount": None
        }
        result = _get_equipment_text(eq)
        assert t("weapon") in result
        assert t("armor") in result

    def test_get_equipment_text_all_none(self):
        eq = {"MainHand": None, "Armor": None, "Head": None, "Shoes": None, "Cape": None, "Mount": None}
        result = _get_equipment_text(eq)
        assert result == "—"

    def test_get_equipment_text_none_input(self):
        assert _get_equipment_text(None) == "—"

    def test_get_equipment_text_empty_dict(self):
        assert _get_equipment_text({}) == "—"


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
        for i in range(MAX_CACHE_SIZE + 1):
            manage_cache(i)
        assert manage_cache(MAX_CACHE_SIZE + 1) is True
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
        await dispatch_event(event, "kill", kill_ch, None)

    @pytest.mark.asyncio
    async def test_embed_passed_to_channel(self):
        kill_ch = AsyncMock()
        event = _full_event()
        await dispatch_event(event, "kill", kill_ch, None)
        call_kwargs = kill_ch.send.call_args
        assert "embed" in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_big_kill_sends_with_ping(self):
        kill_ch = AsyncMock()
        event = _full_event(TotalVictimKillFame=200000)
        await dispatch_event(event, "kill", kill_ch, None)
        call_kwargs = kill_ch.send.call_args
        assert "content" in call_kwargs.kwargs
        assert "200,000" in call_kwargs.kwargs["content"]

    @pytest.mark.asyncio
    async def test_small_kill_no_ping(self):
        kill_ch = AsyncMock()
        event = _full_event(TotalVictimKillFame=50)
        await dispatch_event(event, "kill", kill_ch, None)
        call_kwargs = kill_ch.send.call_args
        # Small kills should not have content (only embed)
        content = call_kwargs.kwargs.get("content")
        assert content is None


# =====================================================================
# Translation system
# =====================================================================

class TestTranslation:
    def test_t_returns_ua_by_default(self):
        result = t("killer")
        assert "Вбивця" in result

    def test_t_with_kwargs(self):
        result = t("big_kill_alert", fame=100000)
        assert "100,000" in result

    def test_t_unknown_key_returns_key(self):
        result = t("nonexistent_key_xyz")
        assert result == "nonexistent_key_xyz"
