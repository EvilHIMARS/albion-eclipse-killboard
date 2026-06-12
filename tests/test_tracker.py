import os
import pytest
from tracker import is_guild_kill

GUILD_ID = "test-guild-id-123"


@pytest.fixture(autouse=True)
def set_guild_env(monkeypatch):
    monkeypatch.setenv("GUILD_ID", GUILD_ID)


def _event(killer_guild=None, victim_guild=None, participants=None):
    ev = {
        "EventId": 1,
        "Killer": {"Name": "KillerPlayer", "GuildId": killer_guild},
        "Victim": {"Name": "VictimPlayer", "GuildId": victim_guild},
    }
    if participants is not None:
        ev["Participants"] = participants
    return ev


# --- GUILD_ID environment variable ---

def test_missing_guild_id(monkeypatch):
    monkeypatch.delenv("GUILD_ID", raising=False)
    assert is_guild_kill(_event()) is None


def test_empty_guild_id(monkeypatch):
    monkeypatch.setenv("GUILD_ID", "")
    assert is_guild_kill(_event()) is None


# --- Death detection (victim belongs to our guild) ---

def test_death_when_victim_is_guild_member():
    assert is_guild_kill(_event(victim_guild=GUILD_ID)) == "death"


def test_death_takes_priority_over_kill():
    """When both killer and victim belong to the guild, death is returned first."""
    assert is_guild_kill(_event(killer_guild=GUILD_ID, victim_guild=GUILD_ID)) == "death"


# --- Kill detection (killer belongs to our guild) ---

def test_kill_when_killer_is_guild_member():
    assert is_guild_kill(_event(killer_guild=GUILD_ID)) == "kill"


def test_kill_with_different_victim_guild():
    assert is_guild_kill(_event(killer_guild=GUILD_ID, victim_guild="other-guild")) == "kill"


# --- Assist detection (participant belongs to our guild) ---

def test_assist_when_participant_is_guild_member():
    participants = [{"Name": "Helper", "GuildId": GUILD_ID, "DamageDone": 100}]
    assert is_guild_kill(_event(participants=participants)) == "assist"


def test_assist_skips_non_dict_participants():
    participants = [None, "bad-data", {"GuildId": GUILD_ID}]
    assert is_guild_kill(_event(participants=participants)) == "assist"


def test_assist_not_found_when_no_guild_match():
    participants = [{"Name": "Other", "GuildId": "other-guild"}]
    assert is_guild_kill(_event(participants=participants)) is None


# --- No match ---

def test_returns_none_for_unrelated_event():
    assert is_guild_kill(_event(killer_guild="a", victim_guild="b")) is None


def test_returns_none_for_empty_event():
    assert is_guild_kill({}) is None


def test_returns_none_when_killer_and_victim_are_none():
    ev = {"EventId": 1, "Killer": None, "Victim": None}
    assert is_guild_kill(ev) is None


def test_returns_none_for_missing_participants_key():
    ev = {"EventId": 1, "Killer": {"GuildId": "x"}, "Victim": {"GuildId": "y"}}
    assert is_guild_kill(ev) is None


def test_empty_participants_list():
    assert is_guild_kill(_event(participants=[])) is None
