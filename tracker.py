import os

def is_guild_kill(event):
    """
    Перевіряє, яке відношення має наша гільдія до цієї події.
    """
    guild_id = os.getenv("GUILD_ID")
    
    if not guild_id:
        print("[TRACKER ERROR] GUILD_ID не знайдено в змінних оточення!")
        return None

    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    
    killer_guild = str(killer.get("GuildId", ""))
    victim_guild = str(victim.get("GuildId", ""))
    guild_id_str = str(guild_id)

    # 1. СМЕРТЬ: жертва из нашей гильдии
    if victim_guild == guild_id_str:
        return "death"

    # 2. УБИЙСТВО: убийца из нашей гильдии
    if killer_guild == guild_id_str:
        return "kill"

    # 3. АСИСТ: проверяем участников
    participants = event.get("Participants") or []
    for p in participants:
        if isinstance(p, dict):
            p_guild = str(p.get("GuildId", ""))
            if p_guild == guild_id_str:
                return "assist"

    return None
