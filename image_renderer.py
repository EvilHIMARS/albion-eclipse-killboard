"""Генератор PNG-карточек киллов/смертей."""
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache

logger = logging.getLogger(__name__)

# Слоты для матрицы (слева Killer, справа Victim)
SLOT_LAYOUT = {
    "killer": {
        "MainHand": (0, 0),
        "OffHand":  (0, 1),
        "Head":     (0, 2),
        "Armor":    (1, 0),
        "Shoes":    (1, 1),
        "Cape":     (1, 2),
        "Bag":      (2, 0),
        "Mount":    (2, 1),
        "Food":     (3, 0),
        "Potion":   (3, 1),
    },
    "victim": {
        "MainHand": (0, 0),
        "OffHand":  (0, 1),
        "Head":     (0, 2),
        "Armor":    (1, 0),
        "Shoes":    (1, 1),
        "Cape":     (1, 2),
        "Bag":      (2, 0),
        "Mount":    (2, 1),
        "Food":     (3, 0),
        "Potion":   (3, 1),
    },
}

SLOT_LABELS = {
    "MainHand": "Weapon",
    "OffHand": "Offhand",
    "Head": "Helmet",
    "Armor": "Armor",
    "Shoes": "Shoes",
    "Cape": "Cape",
    "Bag": "Bag",
    "Mount": "Mount",
    "Food": "Food",
    "Potion": "Potion",
}

ICON_SIZE = 52
COL_SPACING = 70
ROW_SPACING = 66
MATRIX_START_X_KILLER = 30
MATRIX_START_Y = 155
MATRIX_START_X_VICTIM = 380

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
        self.width = 700
        self.height = 420
        self.bg = (20, 20, 28)
        self.panel_bg = (30, 30, 40)
        self.accent = (200, 55, 55)
        self.green = (50, 180, 80)

    def render(self, event_data: dict, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), self.bg)
        draw = ImageDraw.Draw(img)

        # Шрифты
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
            font_text = ImageFont.truetype("DejaVuSans.ttf", 13)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 10)
            font_tiny = ImageFont.truetype("DejaVuSans.ttf", 9)
        except:
            font_title = ImageFont.load_default()
            font_text = font_title
            font_small = font_title
            font_tiny = font_title

        # Верхняя полоса
        color = self.green if is_kill else self.accent
        draw.rectangle([0, 0, self.width, 36], fill=color)
        status = "⚔ KILL" if is_kill else "☠ DEATH"
        draw.text((15, 8), status, fill=(255, 255, 255), font=font_title)

        # Timestamp
        ts = event_data.get("TimeStamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m.%Y %H:%M")
            except:
                ts_str = ts
            tw = draw.textlength(ts_str, font=font_small)
            draw.text((self.width - tw - 12, 10), ts_str, fill=(200, 200, 200), font=font_small)

        # Инфо-панель (Killer / Victim)
        killer = event_data.get("Killer", {})
        victim = event_data.get("Victim", {})
        k_name = killer.get("Name", "Unknown") if isinstance(killer, dict) else "Unknown"
        v_name = victim.get("Name", "Unknown") if isinstance(victim, dict) else "Unknown"
        k_guild = killer.get("GuildName", "") if isinstance(killer, dict) else ""
        v_guild = victim.get("GuildName", "") if isinstance(victim, dict) else ""
        k_ip = killer.get("AverageItemPower", 0) if isinstance(killer, dict) else 0
        v_ip = victim.get("AverageItemPower", 0) if isinstance(victim, dict) else 0
        fame = event_data.get("TotalVictimKillFame", 0)

        # Панель инфы
        draw.rounded_rectangle([12, 44, self.width - 12, 140], radius=8, fill=self.panel_bg)

        # Заголовки колонок
        draw.text((MATRIX_START_X_KILLER + 10, 48), k_name, fill=(255, 255, 255), font=font_text)
        if k_guild:
            draw.text((MATRIX_START_X_KILLER + 10, 66), f"[{k_guild}]", fill=(150, 150, 150), font=font_small)
        draw.text((MATRIX_START_X_KILLER + 10, 84), f"IP: {k_ip:.0f}", fill=(200, 200, 200), font=font_small)

        draw.text((MATRIX_START_X_VICTIM + 10, 48), v_name, fill=(255, 100, 100), font=font_text)
        if v_guild:
            draw.text((MATRIX_START_X_VICTIM + 10, 66), f"[{v_guild}]", fill=(150, 150, 150), font=font_small)
        draw.text((MATRIX_START_X_VICTIM + 10, 84), f"IP: {v_ip:.0f}", fill=(200, 200, 200), font=font_small)

        # Fame по центру
        fame_text = f"Fame: {fame:,}"
        fw = draw.textlength(fame_text, font=font_text)
        draw.text((self.width // 2 - fw // 2, 110), fame_text, fill=(255, 200, 80), font=font_text)

        # Разделитель
        draw.line([12, 145, self.width - 12, 145], fill=(60, 60, 75), width=1)

        # Матрицы экипировки
        k_equip = (killer.get("Equipment") if isinstance(killer, dict) else {}) or {}
        v_equip = (victim.get("Equipment") if isinstance(victim, dict) else {}) or {}

        self._draw_matrix(draw, img, k_equip, MATRIX_START_X_KILLER, MATRIX_START_Y, font_tiny)
        self._draw_matrix(draw, img, v_equip, MATRIX_START_X_VICTIM, MATRIX_START_Y, font_tiny)

        # Футер
        draw.line([12, self.height - 22, self.width - 12, self.height - 22], fill=(60, 60, 75), width=1)
        draw.text((15, self.height - 20), "Albion Eclipse Killboard", fill=(100, 100, 120), font=font_small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _draw_matrix(self, draw, img, equip, start_x, start_y, font):
        """Рисует матрицу 3x3 + Food/Potion с иконками."""
        for slot_name, (col, row) in SLOT_LAYOUT["killer"].items():
            x = start_x + col * COL_SPACING
            y = start_y + row * ROW_SPACING

            # Фон слота
            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=4, fill=(40, 40, 50))

            item = equip.get(slot_name)
            if item:
                item_type = item.get("Type", "") if isinstance(item, dict) else item
                if item_type:
                    icon_data = self.api.fetch_icon(item_type)
                    try:
                        icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((ICON_SIZE - 4, ICON_SIZE - 4))
                        img.paste(icon, (x + 2, y + 2), icon)
                    except:
                        pass

                    # Рамка по тиру
                    tier = self._parse_tier(item_type)
                    color = TIER_COLORS.get(tier, (100, 100, 100))
                    draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=4, outline=color, width=2)

                    # Подпись
                    label = self._format_label(item_type)
                    lw = draw.textlength(label, font=font)
                    draw.text((x + ICON_SIZE // 2 - lw // 2, y + ICON_SIZE + 2), label, fill=(180, 180, 180), font=font)

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4

    def _format_label(self, item_type: str) -> str:
        base = item_type.split("@")[0] if "@" in item_type else item_type
        enchant = ""
        if "@" in item_type:
            enchant = f".{item_type.split('@')[1]}"
        tier = self._parse_tier(item_type)
        return f"T{tier}{enchant}"
