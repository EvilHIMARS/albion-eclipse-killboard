"""Примерная оценка стоимости предметов по Tier и Enchant."""
import logging

logger = logging.getLogger(__name__)

BASE_PRICES = {
    4: {0: 2000, 1: 8000, 2: 25000, 3: 80000, 4: 250000},
    5: {0: 8000, 1: 30000, 2: 100000, 3: 300000, 4: 1000000},
    6: {0: 30000, 1: 120000, 2: 400000, 3: 1200000, 4: 4000000},
    7: {0: 120000, 1: 500000, 2: 1500000, 3: 5000000, 4: 15000000},
    8: {0: 500000, 1: 2000000, 2: 6000000, 3: 20000000, 4: 60000000},
}

SLOT_MULTIPLIERS = {
    "MainHand": 2.0, "OffHand": 1.0, "Head": 1.2, "Armor": 1.5,
    "Shoes": 1.0, "Cape": 1.0, "Bag": 0.5, "Mount": 3.0,
    "Food": 0.3, "Potion": 0.2,
}

def estimate_item_price(item_type: str, slot: str = "Armor") -> int:
    if not item_type:
        return 0
    tier = 4
    enchant = 0
    try:
        if item_type.startswith("T"):
            tier = int(item_type[1])
    except:
        pass
    if "@" in item_type:
        try:
            enchant = int(item_type.split("@")[1])
        except:
            pass
    base = BASE_PRICES.get(tier, {}).get(enchant, 5000)
    multiplier = SLOT_MULTIPLIERS.get(slot, 1.0)
    return int(base * multiplier)

def estimate_total_loss(equipment: dict) -> int:
    if not equipment:
        return 0
    total = 0
    for slot, item in equipment.items():
        if isinstance(item, dict):
            item_type = item.get("Type", "")
        else:
            item_type = str(item) if item else ""
        if item_type:
            total += estimate_item_price(item_type, slot)
    return total

def format_silver(amount: int) -> str:
    if amount >= 1_000_000:
        return f"{amount/1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{amount/1000:.0f}K"
    return str(amount)
