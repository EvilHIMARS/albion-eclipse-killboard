"""Генератор PNG-карточек киллов/смертей — Albion Online Killbot Style."""
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache

logger = logging.getLogger(__name__)

ICON_SIZE = 56
GAP = 10

SLOT_GRID = [
    ("Bag",      0, 0), ("Head",     1, 0), ("Cape",     2, 0),
    ("MainHand", 0, 1), ("Armor",    1, 1), ("OffHand",  2, 1),
    ("Potion",   0, 2), ("Shoes",    1, 2), ("Food",     2, 2),
    (None,       0, 3), ("Mount",    1, 3), (None,       2, 3),
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
        self.width = 820
        self.height = 720
        self.bg = (18, 15, 12)
        self.panel_dark = (28, 22, 18)
        self.border = (70, 50, 30)
        self.gold = (210, 170, 70)
        self.text_white = (235, 225, 210)
        self.text_grey = (170, 160, 145)
        self.text_dim = (120, 110, 100)

    def render(self, event_data: dict, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), self.bg)
        draw = ImageDraw.Draw(img)

        try:
            font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
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
        draw.rectangle([0, 0, self.width, 100], fill=self.panel_dark)
        draw.rectangle([0, 98, self.width, 100], fill=self.border)

        title = f"{k_name} killed {v_name}"
        tw = draw.textlength(title, font=font_big)
        if tw > self.width - 30:
            title = f"{k_name[:12]}.. killed {v_name[:12]}.."
            tw = draw.textlength(title, font=font_big)
        draw.text(((self.width - tw) // 2, 16), title, fill=self.gold, font=font_big)

        draw.text((30, 48), f"Killer: {k_name}", fill=self.text_white, font=font_title)
        if k_guild:
            draw.text((30, 68), f"Guild: [{k_guild}]", fill=self.text_grey, font=font_small)

        v_text = f"Victim: {v_name}"
        vw = draw.textlength(v_text, font=font_title)
        draw.text((self.width - vw - 30, 48), v_text, fill=(220, 80, 70), font=font_title)
        if v_guild:
            vg_text = f"Guild: [{v_guild}]"
            vgw = draw.textlength(vg_text, font=font_small)
            draw.text((self.width - vgw - 30, 68), vg_text, fill=self.text_grey, font=font_small)

        # === ЦЕНТР — Экипировка ===
        eq_y = 115

        k_equip = killer.get("Equipment") or {}
        v_equip = victim.get("Equipment") or {}

        killer_start_x = 15
        self._draw_build(draw, img, k_equip, killer_start_x, eq_y)

        grid_w = 3 * (ICON_SIZE + GAP) - GAP
        victim_start_x = self.width - grid_w - 15
        self._draw_build(draw, img, v_equip, victim_start_x, eq_y)

        draw.text((killer_start_x + 10, eq_y - 18), "KILLER BUILD", fill=self.gold, font=font_small)
        draw.text((victim_start_x + 10, eq_y - 18), "VICTIM BUILD", fill=(220, 80, 70), font=font_small)

        # Вертикальная полоса по центру
        mid_x = self.width // 2
        grid_h = 4 * (ICON_SIZE + GAP) - GAP
        draw.rectangle([mid_x - 2, eq_y - 20, mid_x + 2, eq_y + grid_h + 10], fill=self.border)

        # Плашка VICTORY / DEFEAT
        center_y = eq_y + grid_h // 2 - 20
        killed_bg = (190, 50, 40) if is_kill else (60, 60, 60)
        draw.rounded_rectangle([mid_x - 55, center_y - 18, mid_x + 55, center_y + 22], radius=6, fill=killed_bg)
        killed_text = "VICTORY" if is_kill else "DEFEAT"
        ktw = draw.textlength(killed_text, font=font_title)
        draw.text((mid_x - ktw // 2, center_y - 10), killed_text, fill=(255, 255, 255), font=font_title)

        draw.text((mid_x - 45, center_y + 35), f"Fame: {fame:,}", fill=self.gold, font=font_text)
        draw.text((mid_x - 45, center_y + 55), f"IP K: {k_ip:.0f}", fill=self.text_grey, font=font_small)
        draw.text((mid_x - 45, center_y + 72), f"IP V: {v_ip:.0f}", fill=self.text_grey, font=font_small)

        # === УЧАСТНИКИ (Assists & Heals) ===
        participants = event_data.get("Participants") or []
        if participants:
            part_y = eq_y + grid_h + 20
            draw.text((25, part_y), "PARTICIPANTS", fill=self.gold, font=font_title)

            # Заголовки колонок
            draw.text((25, part_y + 22), "Name", fill=self.text_grey, font=font_small)
            draw.text((230, part_y + 22), "Damage", fill=(255, 150, 130), font=font_small)
            draw.text((350, part_y + 22), "Heal", fill=(130, 200, 130), font=font_small)
            draw.text((470, part_y + 22), "Guild", fill=self.text_grey, font=font_small)

            # Линия
            draw.line([25, part_y + 40, self.width - 25, part_y + 40], fill=(60, 45, 30), width=1)

            # Участники (макс 6)
            for i, p in enumerate(participants[:6]):
                row_y = part_y + 46 + i * 20
                p_name = p.get("Name", "?")[:20]
                p_dmg = p.get("DamageDone", 0)
                p_heal = p.get("SupportValue", 0)
                p_guild = p.get("GuildName", "")[:15]

                draw.text((25, row_y), p_name, fill=self.text_white, font=font_small)
                draw.text((230, row_y), f"{p_dmg:,}", fill=(255, 150, 130), font=font_small)
                draw.text((350, row_y), f"{p_heal:,}", fill=(130, 200, 130), font=font_small)
                draw.text((470, row_y), f"[{p_guild}]" if p_guild else "—", fill=self.text_dim, font=font_small)

            part_end_y = part_y + 50 + min(len(participants), 6) * 20 + 10
        else:
            part_end_y = eq_y + grid_h + 20

        # === НИЗ — Combat Stats ===
        stats_y = part_end_y + 5
        draw.rectangle([0, stats_y, self.width, stats_y + 2], fill=self.border)

        draw.text((25, stats_y + 12), "COMBAT STATS", fill=self.gold, font=font_title)

        total_dmg = event_data.get("TotalDamage", 0)
        if not total_dmg:
            total_dmg = sum(p.get("DamageDone", 0) for p in participants)

        dmg_bar_y = stats_y + 38
        draw.text((25, dmg_bar_y - 18), "Damage", fill=self.text_grey, font=font_small)
        draw.text((25, dmg_bar_y), k_name, fill=self.text_white, font=font_text)
        dmg_text = f"{total_dmg:,} DMG"
        dtw = draw.textlength(dmg_text, font=font_text)
        draw.text((self.width - dtw - 25, dmg_bar_y), dmg_text, fill=(255, 150, 130), font=font_text)

        bar_x, bar_y, bar_w, bar_h = 25, dmg_bar_y + 22, self.width - 50, 12
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4, fill=(40, 30, 25))
        if total_dmg > 0:
            fill_ratio = min(total_dmg / max(total_dmg, 1), 1.0)
            fill_w = int(bar_w * fill_ratio)
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=4, fill=(200, 50, 40))

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

        draw.line([0, self.height - 28, self.width, self.height - 28], fill=self.border)
        draw.text((25, self.height - 24), "Albion Eclipse Killboard", fill=self.text_dim, font=font_tiny)
        draw.text((self.width - 100, self.height - 24), "Dev: EvilHIMARS", fill=self.text_dim, font=font_tiny)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _draw_build(self, draw, img, equip, start_x, start_y):
        for slot_entry in SLOT_GRID:
            slot_name, col, row = slot_entry
            if slot_name is None:
                continue

            x = start_x + col * (ICON_SIZE + GAP)
            y = start_y + row * (ICON_SIZE + GAP)

            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=4, fill=(35, 28, 22))
            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=4, outline=(55, 40, 28), width=1)

            item = equip.get(slot_name)
            item_type = ""
            if item:
                item_type = item.get("Type", "") if isinstance(item, dict) else str(item)

            if item_type:
                icon_data = self.api.fetch_icon(item_type)
                try:
                    icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((ICON_SIZE - 8, ICON_SIZE - 8))
                    img.paste(icon, (x + 4, y + 4), icon)
                except:
                    pass

                tier = self._parse_tier(item_type)
                color = TIER_COLORS.get(tier, (100, 100, 100))
                draw.rounded_rectangle([x - 1, y - 1, x + ICON_SIZE + 1, y + ICON_SIZE + 1], radius=5, outline=color, width=2)

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4
