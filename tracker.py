import os

def is_guild_kill(event):
    """
    Перевіряє, яке відношення має наша гільдія до цієї події.
    Бере GUILD_ID прямо під час виклику, щоб уникнути багів з імпортами.
    """
    guild_id = os.getenv("GUILD_ID")
    
    if not guild_id:
        print("[TRACKER ERROR] GUILD_ID не знайдено в змінних оточення!")
        return None

    # Отримуємо дані вбивці та жертви
    killer = event.get("Killer") or {}
    victim = event.get("Victim") or {}
    
    killer_guild = killer.get("GuildId")
    victim_guild = victim.get("GuildId")

    # 1. СМЕРТЬ: Якщо ID гільдії жертви збігається з нашим
    if victim_guild == guild_id:
        return "death"

    # 2. ВБИВСТВО: Якщо ID гільдії головного вбивці збігається з нашим
    if killer_guild == guild_id:
        return "kill"

    # 3. АСИСТ: Перевіряємо, чи допомагав хтось із нашої гільдії в списку учасників
    participants = event.get("Participants") or []
    for p in participants:
        if isinstance(p, dict) and p.get("GuildId") == guild_id:
            return "assist"

    # Подія не має відношення до нашої гільдії
    return None
