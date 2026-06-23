"""Генератор PNG-карточек киллов/смертей — Albion Online Killbot Style."""
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache

logger = logging.getLogger(__name__)

ICON_SIZE = 52
GAP = 8

# Позиции слотов в сетке 5x2
SLOT_GRID = [
    ("MainHand", 0, 0), ("OffHand", 0, 1),
    ("Head",     1, 0), ("Armor",  1, 1),
    ("Shoes",    2, 0), ("Cape",   2, 1),
    ("Bag",      3, 0), ("Mount",  3, 1),
    ("Food",     4, 0), ("Potion", 4, 1),
]

TIER_COLORS = {
    4: (110, 150, 210),
    5: (110, 190, 130),
    6: (210, 170, 70),
    7: (210, 130, 70),
    8: (230, 190, 50),
}


class ImageRenderer:
    def __init__(self, render_api: RenderAPI):
        self.api = render_api
        self.width = 780
        self.height = 620
        self.bg = (18, 15, 12)
        self.panel_dark = (28, 22, 18)
        self.panel_mid = (38, 30, 24)
        self.border = (70, 50, 30)
        self.accent = (190, 60, 50)
        self.gold = (210, 170, 70)
        self.text_white = (235, 225, 210)
        self.text_grey = (170, 160, 145)
        self.text_dim = (120, 110, 100)

    def render(self, event_data: dict, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), self.bg)
        draw = ImageDraw.Draw(img)

        # Шрифты
        try:
            font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
            font_text = ImageFont.truetype("DejaVuSans.ttf", 13)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 11)
            font_tiny = ImageFont.truetype("DejaVuSans.ttf", 9)
        except:
            font_big = font_title = font_text = font_small = font_tiny = ImageFont.load_default()

        killer = event_data.get("Killer", {}) or {}
        victim = event_data.get("Victim", {}) or {}
        k_name = killer.get("Name", "Unknown")
        v_name = victim.get("Name", "Unknown")
        k_guild = killer.get("GuildName", "")
        v_guild = victim.get("GuildName", "")
        k_ip = killer.get("AverageItemPower", 0)
        v_ip = victim.get("AverageItemPower", 0)
        fame = event_data.get("TotalVictimKillFame", 0)

        # === ВЕРХ — Заголовок ===
        draw.rectangle([0, 0, self.width, 110], fill=self.panel_dark)
        draw.rectangle([0, 108, self.width, 110], fill=self.border)

        # Заголовок
        title = f"{k_name} killed {v_name}"
        tw = draw.textlength(title, font=font_big)
        if tw > self.width - 30:
            title = f"{k_name[:12]}.. killed {v_name[:12]}.."
            tw = draw.textlength(title, font=font_big)
        draw.text(((self.width - tw) // 2, 18), title, fill=self.gold, font=font_big)

        # Killer / Victim строки
        draw.text((30, 52), f"Killer: {k_name}", fill=self.text_white, font=font_title)
        if k_guild:
            draw.text((30, 74), f"Guild: [{k_guild}]", fill=self.text_grey, font=font_small)

        v_text = f"Victim: {v_name}"
        vw = draw.textlength(v_text, font=font_title)
        draw.text((self.width - vw - 30, 52), v_text, fill=(220, 80, 70), font=font_title)
        if v_guild:
            vg_text = f"Guild: [{v_guild}]"
            vgw = draw.textlength(vg_text, font=font_small)
            draw.text((self.width - vgw - 30, 74), vg_text, fill=self.text_grey, font=font_small)

        # === ЦЕНТР — Экипировка ===
        eq_y = 125
        # Лейблы
        draw.text((55, eq_y - 18), "KILLER BUILD", fill=self.gold, font=font_small)
        draw.text((self.width - 170, eq_y - 18), "VICTIM BUILD", fill=(220, 80, 70), font=font_small)

        k_equip = killer.get("Equipment") or {}
        v_equip = victim.get("Equipment") or {}

        self._draw_build(draw, img, k_equip, 20, eq_y, font_tiny)
        self._draw_build(draw, img, v_equip, self.width - 310, eq_y, font_tiny)

        # Разделитель VS / KILLED по центру
        mid_x = self.width // 2
        eq_center_y = eq_y + 110
        draw.rectangle([mid_x - 1, eq_y, mid_x + 1, eq_y + 220], fill=self.border)
        
        # Плашка KILLED
        killed_bg = (190, 50, 40) if is_kill else (40, 40, 40)
        draw.rounded_rectangle([mid_x - 50, eq_center_y - 18, mid_x + 50, eq_center_y + 22], radius=6, fill=killed_bg)
        killed_text = "VICTORY" if is_kill else "DEFEAT"
        ktw = draw.textlength(killed_text, font=font_title)
        draw.text((mid_x - ktw // 2, eq_center_y - 10), killed_text, fill=(255, 255, 255), font=font_title)

        # Fame / Silver
        draw.text((mid_x - 40, eq_center_y + 35), f"Fame: {fame:,}", fill=self.gold, font=font_text)
        draw.text((mid_x - 40, eq_center_y + 55), f"IP Killer: {k_ip:.0f}", fill=self.text_grey, font=font_small)
        draw.text((mid_x - 40, eq_center_y + 72), f"IP Victim: {v_ip:.0f}", fill=self.text_grey, font=font_small)

        # === НИЗ — Combat Stats ===
        stats_y = 380
        draw.rectangle([0, stats_y, self.width, stats_y + 2], fill=self.border)
        
        draw.text((25, stats_y + 12), "COMBAT STATS", fill=self.gold, font=font_title)

        # Урон
        dmg_bar_y = stats_y + 40
        draw.text((25, dmg_bar_y - 18), "Damage", fill=self.text_grey, font=font_small)
        draw.text((25, dmg_bar_y), k_name, fill=self.text_white, font=font_text)

        total_dmg = event_data.get("TotalDamage", 0)
        if not total_dmg:
            # Считаем из participants
            participants = event_data.get("Participants") or []
            total_dmg = sum(p.get("DamageDone", 0) for p in participants)

        draw.text((self.width - 120, dmg_bar_y), f"{total_dmg:,} DMG", fill=(255, 150, 130), font=font_text)

        # Полоска урона
        bar_x, bar_y, bar_w, bar_h = 25, dmg_bar_y + 22, self.width - 50, 10
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=3, fill=(40, 30, 25))
        fill_w = min(int(bar_w * 0.75), bar_w)
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=3, fill=(200, 50, 40))

        # Сервер и дата
        ts = event_data.get("TimeStamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m.%Y %H:%M UTC")
            except:
                ts_str = ts
        else:
            ts_str = ""

        draw.text((25, bar_y + 25), "Server: Europe", fill=self.text_dim, font=font_small)
        if ts_str:
            tsw = draw.textlength(ts_str, font=font_small)
            draw.text((self.width - tsw - 25, bar_y + 25), ts_str, fill=self.text_dim, font=font_small)

        # Футер
        draw.line([0, self.height - 28, self.width, self.height - 28], fill=self.border)
        draw.text((25, self.height - 24), "Albion Eclipse Killboard", fill=self.text_dim, font=font_tiny)
        draw.text((self.width - 100, self.height - 24), "Dev: EvilHIMARS", fill=self.text_dim, font=font_tiny)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _draw_build(self, draw, img, equip, start_x, start_y, font):
        """Рисует сетку 5x2 с иконками."""
        for slot_name, col, row in SLOT_GRID:
            x = start_x + col * (ICON_SIZE + GAP)
            y = start_y + row * (ICON_SIZE + GAP)

            # Фон ячейки
            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=3, fill=(35, 28, 22))
            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=3, outline=(55, 40, 28), width=1)

            item = equip.get(slot_name)
            item_type = ""
            if item:
                item_type = item.get("Type", "") if isinstance(item, dict) else str(item)

            if item_type:
                icon_data = self.api.fetch_icon(item_type)
                try:
                    icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((ICON_SIZE - 6, ICON_SIZE - 6))
                    img.paste(icon, (x + 3, y + 3), icon)
                except:
                    pass

                # Рамка по тиру
                tier = self._parse_tier(item_type)
                color = TIER_COLORS.get(tier, (100, 100, 100))
                draw.rounded_rectangle([x - 1, y - 1, x + ICON_SIZE + 1, y + ICON_SIZE + 1], radius=4, outline=color, width=2)

                # Подпись
                label = self._format_label(item_type)
                lw = draw.textlength(label, font=font)
                draw.text((x + ICON_SIZE // 2 - lw // 2, y + ICON_SIZE + 2), label, fill=(180, 170, 150), font=font)

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4

    def _format_label(self, item_type: str) -> str:
        enchant = ""
        if "@" in item_type:
            enchant = f".{item_type.split('@')[1]}"
        tier = self._parse_tier(item_type)
        return f"T{tier}{enchant}"
