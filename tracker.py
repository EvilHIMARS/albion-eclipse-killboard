import os

from utils import extract_player, extract_participants


def is_guild_kill(event):
    """
    Перевіряє, яке відношення має наша гільдія до цієї події.
    Бере GUILD_ID прямо під час виклику, щоб уникнути багів з імпортами.
    """
    guild_id = os.getenv("GUILD_ID")

    if not guild_id:
        print("[TRACKER ERROR] GUILD_ID не знайдено в змінних оточення!")
        return None

    killer = extract_player(event, "Killer")
    victim = extract_player(event, "Victim")

    if victim["guild_id"] == guild_id:
        return "death"

    if killer["guild_id"] == guild_id:
        return "kill"

    for p in extract_participants(event):
        if p["guild_id"] == guild_id:
            return "assist"

    return None
