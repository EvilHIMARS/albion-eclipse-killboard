"""Shared utilities for event data extraction and common constants."""


# Default fallback strings used across the bot
DEFAULT_PLAYER_NAME = "Неизвестно"
DEFAULT_GUILD_NAME = "Без гильдии"


def extract_player(event, role):
    """
    Extract player info from an event dict.

    Args:
        event: Raw event dict from the Albion API.
        role: One of "Killer" or "Victim".

    Returns:
        dict with keys: name, guild_name, guild_id, raw (original dict).
    """
    player = event.get(role) or {}
    return {
        "name": player.get("Name", DEFAULT_PLAYER_NAME),
        "guild_name": player.get("GuildName") or DEFAULT_GUILD_NAME,
        "guild_id": player.get("GuildId"),
        "raw": player,
    }


def extract_participants(event):
    """
    Extract and normalize participants list from an event.

    Returns:
        list of dicts with keys: name, guild_name, guild_id, damage, healing.
    """
    raw = event.get("Participants") or []
    participants = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        participants.append({
            "name": p.get("Name", DEFAULT_PLAYER_NAME),
            "guild_name": p.get("GuildName") or DEFAULT_GUILD_NAME,
            "guild_id": p.get("GuildId"),
            "damage": p.get("DamageDone", 0),
            "healing": p.get("SupportValue", 0),
        })
    return participants
