"""Генератор PNG-карточек киллов/смертей."""
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache

logger = logging.getLogger(__name__)

# Слоты и их позиции на карточке (x, y)
SLOTS = {
    "MainHand": (20, 170),
    "OffHand": (90, 170),
    "Head": (160, 170),
    "Armor": (230, 170),
    "Shoes": (300, 170),
    "Cape": (370, 170),
    "Bag": (440, 170),
    "Mount": (510, 170),
    "Food": (580, 170),
    "Potion": (650, 170),
}

# Цвета по Tier
TIER_COLORS = {
    4: (100, 140, 200),
    5: (100, 180, 120),
    6: (200, 160, 60),
    7: (200, 120, 60),
    8: (220, 180, 40),
}


class ImageRenderer:
    def __init__(self, render_api: RenderAPI):
        self.api = render_api
        self.width = 740
        self.height = 280
        self.bg = (30, 30, 35)
        self.panel_bg = (40, 40, 48)
        self.accent = (200, 50, 50)
        self.green = (50, 180, 80)

    def render(self, event, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), self.bg)
        draw = ImageDraw.Draw(img)

        # Шрифт
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
            font_text = ImageFont.truetype("DejaVuSans.ttf", 14)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 11)
        except:
            font_title = ImageFont.load_default()
            font_text = font_title
            font_small = font_title

        # Верхняя полоса
        color = self.green if is_kill else self.accent
        draw.rectangle([0, 0, self.width, 40], fill=color)
        status = "⚔ KILL" if is_kill else "☠ DEATH"
        draw.text((15, 10), status, fill=(255, 255, 255), font=font_title)

        # Timestamp
        ts = event.get("TimeStamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m.%Y %H:%M")
            except:
                ts_str = ts
            tw = draw.textlength(ts_str, font=font_small)
            draw.text((self.width - tw - 15, 13), ts_str, fill=(200, 200, 200), font=font_small)

        # Панель инфы
        draw.rounded_rectangle([15, 50, self.width - 15, 140], radius=8, fill=self.panel_bg)

        # Killer / Victim
        killer = event.get("Killer", {}).get("Name", "Unknown")
        victim = event.get("Victim", {}).get("Name", "Unknown")
        killer_guild = event.get("Killer", {}).get("GuildName", "")
        victim_guild = event.get("Victim", {}).get("GuildName", "")

        if is_kill:
            draw.text((30, 58), f"Убийца: {killer}", fill=(255, 255, 255), font=font_text)
            draw.text((30, 80), f"Цель: {victim}", fill=(255, 100, 100), font=font_text)
            if killer_guild:
                draw.text((30, 102), f"Гильдия: {killer_guild}", fill=(180, 180, 180), font=font_small)
            if victim_guild:
                draw.text((30, 120), f"Гильдия цели: {victim_guild}", fill=(180, 180, 180), font=font_small)
        else:
            draw.text((30, 58), f"Убийца: {killer}", fill=(255, 100, 100), font=font_text)
            draw.text((30, 80), f"Цель: {victim}", fill=(255, 255, 255), font=font_text)
            if killer_guild:
                draw.text((30, 102), f"Гильдия убийцы: {killer_guild}", fill=(180, 180, 180), font=font_small)
            if victim_guild:
                draw.text((30, 120), f"Гильдия: {victim_guild}", fill=(180, 180, 180), font=font_small)

        # Fame
        fame = event.get("TotalVictimKillFame", 0)
        draw.text((400, 58), f"Fame: {fame:,}", fill=(255, 200, 100), font=font_text)

        # Equip
        equip = event.get("Equipment", {})
        for slot, (sx, sy) in SLOTS.items():
            item = equip.get(slot)
            if item and isinstance(item, dict):
                item_type = item.get("Type", "")
            elif item and isinstance(item, str):
                item_type = item
            else:
                item_type = ""

            if item_type:
                icon_data = self.api.fetch_icon(item_type)
                try:
                    icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((56, 56))
                except:
                    icon = Image.new("RGBA", (56, 56), (40, 40, 40))
                img.paste(icon, (sx, sy), icon)

                # Рамка по Tier
                tier = self._parse_tier(item_type)
                color = TIER_COLORS.get(tier, (100, 100, 100))
                draw.rounded_rectangle([sx - 1, sy - 1, sx + 57, sy + 57], radius=4, outline=color, width=2)

                # Подпись (Tier.Enchant)
                label = self._format_label(item_type)
                lw = draw.textlength(label, font=font_small)
                draw.text((sx + 28 - lw // 2, sy + 58), label, fill=(200, 200, 200), font=font_small)

        # Футер
        draw.line([15, self.height - 25, self.width - 15, self.height - 25], fill=(60, 60, 70), width=1)
        draw.text((20, self.height - 22), "Albion Eclipse Killboard", fill=(120, 120, 130), font=font_small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4

    def _format_label(self, item_type: str) -> str:
        base = item_type.split("@")[0]
        enchant = ""
        if "@" in item_type:
            enchant = f".{item_type.split('@')[1]}"
        tier = self._parse_tier(item_type)
        return f"T{tier}{enchant}"