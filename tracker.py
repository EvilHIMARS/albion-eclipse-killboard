import os

GUILD_ID = os.getenv("GUILD_ID")


def is_guild_kill(event):

    killer = event.get("Killer", {})
    victim = event.get("Victim", {})

    killer_guild = killer.get("GuildId")
    victim_guild = victim.get("GuildId")

    if killer_guild == GUILD_ID:
        return "kill"

    if victim_guild == GUILD_ID:
        return "death"

    participants = event.get("Participants", [])

    for p in participants:
        if p.get("GuildId") == GUILD_ID:
            return "assist"

    return None