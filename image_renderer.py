"""Генератор PNG-карточек киллов/смертей — shadcn/ui Dark Style x2."""
import io
import math
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache
from price_estimator import estimate_total_loss, format_silver

logger = logging.getLogger(__name__)

SCALE = 2
ICON_SIZE = 56 * SCALE
SMALL_ICON = 28 * SCALE
GAP = 12 * SCALE
RADIUS = 12 * SCALE
PADDING = 20 * SCALE

SLOT_GRID = [
    ("Bag", 0, 0), ("Head", 1, 0), ("Cape", 2, 0),
    ("MainHand", 0, 1), ("Armor", 1, 1), ("OffHand", 2, 1),
    ("Potion", 0, 2), ("Shoes", 1, 2), ("Food", 2, 2),
    (None, 0, 3), ("Mount", 1, 3), (None, 2, 3),
]

COLORS = {
    "bg": (9, 9, 11), "card": (24, 24, 27), "border": (39, 39, 42),
    "muted": (113, 113, 122), "muted_fg": (161, 161, 170),
    "foreground": (250, 250, 250), "destructive": (239, 68, 68),
    "success": (34, 197, 94), "warning": (234, 179, 8), "silver": (192, 192, 200),
}

TIER_COLORS = {
    4: (96, 165, 250), 5: (74, 222, 128), 6: (250, 204, 21),
    7: (251, 146, 60), 8: (248, 113, 113),
}


class ImageRenderer:
    def __init__(self, render_api: RenderAPI):
        self.api = render_api
        self.width = 780 * SCALE
        self.height = 620 * SCALE

    def render(self, event_data: dict, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), COLORS["bg"])
        draw = ImageDraw.Draw(img)

        try:
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 14 * SCALE)
            font_text = ImageFont.truetype("DejaVuSans.ttf", 13 * SCALE)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 11 * SCALE)
            font_tiny = ImageFont.truetype("DejaVuSans.ttf", 10 * SCALE)
        except:
            font_heading = font_text = font_small = font_tiny = ImageFont.load_default()

        killer = event_data.get("Killer", {}) or {}
        victim = event_data.get("Victim", {}) or {}
        k_name = killer.get("Name", "Unknown")
        v_name = victim.get("Name", "Unknown")
        k_guild = killer.get("GuildName", "")
        v_guild = victim.get("GuildName", "")
        k_ip = killer.get("AverageItemPower", 0)
        v_ip = victim.get("AverageItemPower", 0)
        fame = event_data.get("TotalVictimKillFame", 0)

        v_equip = victim.get("Equipment") or {}
        silver_lost = estimate_total_loss(v_equip)

        # === EQUIPMENT ===
        eq_y = PADDING
        k_equip = killer.get("Equipment") or {}
        grid_w = 3 * (ICON_SIZE + GAP) - GAP
        grid_h = 4 * (ICON_SIZE + GAP) - GAP
        card_w = grid_w + 24 * SCALE
        card_h = grid_h + 70 * SCALE

        # KILLER CARD
        killer_card_x = PADDING
        draw.rounded_rectangle([killer_card_x, eq_y, killer_card_x + card_w, eq_y + card_h], radius=RADIUS, fill=COLORS["card"])
        draw.text((killer_card_x + 12 * SCALE, eq_y + 10 * SCALE), k_name, fill=COLORS["foreground"], font=font_heading)
        if k_guild:
            draw.text((killer_card_x + 12 * SCALE, eq_y + 30 * SCALE), f"[{k_guild}]", fill=COLORS["muted_fg"], font=font_small)
        draw.text((killer_card_x + 12 * SCALE, eq_y + 48 * SCALE), f"IP: {k_ip:.0f}", fill=COLORS["muted"], font=font_tiny)
        self._draw_build(draw, img, k_equip, killer_card_x + 12 * SCALE, eq_y + 60 * SCALE)

        # VICTIM CARD
        victim_card_x = self.width - PADDING - card_w
        draw.rounded_rectangle([victim_card_x, eq_y, victim_card_x + card_w, eq_y + card_h], radius=RADIUS, fill=COLORS["card"])
        draw.text((victim_card_x + 12 * SCALE, eq_y + 10 * SCALE), v_name, fill=(248, 113, 113), font=font_heading)
        if v_guild:
            draw.text((victim_card_x + 12 * SCALE, eq_y + 30 * SCALE), f"[{v_guild}]", fill=COLORS["muted_fg"], font=font_small)
        draw.text((victim_card_x + 12 * SCALE, eq_y + 48 * SCALE), f"IP: {v_ip:.0f}", fill=COLORS["muted"], font=font_tiny)
        self._draw_build(draw, img, v_equip, victim_card_x + 12 * SCALE, eq_y + 60 * SCALE)

        # === ЦЕНТР — Статистика ===
        center_x = self.width // 2
        center_y = eq_y + card_h // 2

        stats_box_w = 140 * SCALE
        stats_box_h = 150 * SCALE
        draw.rounded_rectangle(
            [center_x - stats_box_w // 2, center_y - stats_box_h // 2,
             center_x + stats_box_w // 2, center_y + stats_box_h // 2],
            radius=10 * SCALE, fill=COLORS["card"]
        )
        draw.rounded_rectangle(
            [center_x - stats_box_w // 2, center_y - stats_box_h // 2,
             center_x + stats_box_w // 2, center_y + stats_box_h // 2],
            radius=10 * SCALE, outline=COLORS["border"], width=1 * SCALE
        )

        # Звезда фейма
        fame_icon_x = center_x - 58 * SCALE
        fame_icon_y = center_y - 50 * SCALE
        fame_icon_size = 26 * SCALE
        self._draw_fame_star(draw, fame_icon_x, fame_icon_y, fame_icon_size)

        fame_value = f"{fame:,}"
        fvw = draw.textlength(fame_value, font=font_text)
        draw.text((center_x - fvw // 2, center_y - 18 * SCALE), fame_value, fill=COLORS["warning"], font=font_text)

        # Монета серебра
        silver_icon_x = center_x - 58 * SCALE
        silver_icon_y = center_y + 6 * SCALE
        silver_icon_size = 26 * SCALE
        self._draw_silver_coin(draw, silver_icon_x, silver_icon_y, silver_icon_size)

        silver_value = format_silver(silver_lost) if silver_lost > 0 else "0"
        svw = draw.textlength(silver_value, font=font_text)
        draw.text((center_x - svw // 2, center_y + 38 * SCALE), silver_value, fill=COLORS["silver"], font=font_text)

        # KILL / DEATH
        status_label = "GUILD KILL" if is_kill else "GUILD DEATH"
        status_color = COLORS["success"] if is_kill else COLORS["destructive"]
        stlw = draw.textlength(status_label, font=font_small)
        draw.rounded_rectangle(
            [center_x - stlw // 2 - 10 * SCALE, center_y + 58 * SCALE,
             center_x + stlw // 2 + 10 * SCALE, center_y + 78 * SCALE],
            radius=4 * SCALE, fill=status_color
        )
        draw.text((center_x - stlw // 2, center_y + 60 * SCALE), status_label, fill=(255, 255, 255), font=font_small)

        # === COMBAT STATS ===
        stats_y = eq_y + card_h + 16 * SCALE
        stats_h = 180 * SCALE
        draw.rounded_rectangle([PADDING, stats_y, self.width - PADDING, stats_y + stats_h], radius=RADIUS, fill=COLORS["card"])
        draw.text((PADDING + 16 * SCALE, stats_y + 14 * SCALE), "COMBAT STATS", fill=COLORS["muted"], font=font_small)

        participants = event_data.get("Participants") or []
        total_dmg = event_data.get("TotalDamage", 0) or sum(p.get("DamageDone", 0) for p in participants)

        bar_x = PADDING + 16 * SCALE
        bar_y = stats_y + 40 * SCALE
        bar_w = self.width - PADDING * 2 - 32 * SCALE
        bar_h = 8 * SCALE

        draw.text((bar_x, bar_y - 16 * SCALE), f"Total Damage: {total_dmg:,}", fill=COLORS["muted_fg"], font=font_small)
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4 * SCALE, fill=COLORS["border"])
        if total_dmg > 0:
            fill_w = int(bar_w * 0.75)
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=4 * SCALE, fill=COLORS["destructive"])

        if participants:
            part_y = bar_y + 24 * SCALE
            for i, p in enumerate(participants[:5]):
                col = i % 2
                row = i // 2
                px = bar_x + col * 370 * SCALE
                py = part_y + row * 40 * SCALE
                p_name = p.get("Name", "?")[:16]
                p_dmg = p.get("DamageDone", 0)
                p_heal = p.get("SupportValue", 0)
                p_weapon = p.get("Equipment", {}).get("MainHand", {})
                p_weapon_type = p_weapon.get("Type", "") if isinstance(p_weapon, dict) else str(p_weapon) if p_weapon else ""
                if p_weapon_type:
                    icon_data = self.api.fetch_icon(p_weapon_type)
                    try:
                        icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((SMALL_ICON, SMALL_ICON))
                        img.paste(icon, (px, py), icon)
                    except:
                        draw.rounded_rectangle([px, py, px + SMALL_ICON, py + SMALL_ICON], radius=4 * SCALE, fill=COLORS["border"])
                    tier = self._parse_tier(p_weapon_type)
                    color = TIER_COLORS.get(tier, COLORS["border"])
                    draw.rounded_rectangle([px - 1 * SCALE, py - 1 * SCALE, px + SMALL_ICON + 1 * SCALE, py + SMALL_ICON + 1 * SCALE], radius=4 * SCALE, outline=color, width=1 * SCALE)
                else:
                    draw.rounded_rectangle([px, py, px + SMALL_ICON, py + SMALL_ICON], radius=4 * SCALE, fill=COLORS["border"])
                draw.text((px + SMALL_ICON + 8 * SCALE, py), p_name, fill=COLORS["foreground"], font=font_small)
                draw.text((px + SMALL_ICON + 8 * SCALE, py + 16 * SCALE), f"DMG: {p_dmg:,}  HEAL: {p_heal:,}", fill=COLORS["muted_fg"], font=font_tiny)

        # === FOOTER ===
        footer_y = self.height - 36 * SCALE
        ts = event_data.get("TimeStamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m.%Y %H:%M UTC")
            except:
                ts_str = ts
        else:
            ts_str = ""
        draw.text((PADDING + 4 * SCALE, footer_y), "Server: Europe", fill=COLORS["muted"], font=font_tiny)
        draw.text((PADDING + 4 * SCALE, footer_y + 14 * SCALE), "Albion Eclipse Killboard", fill=COLORS["muted"], font=font_tiny)
        if ts_str:
            tsw = draw.textlength(ts_str, font=font_tiny)
            draw.text((self.width - PADDING - tsw, footer_y), ts_str, fill=COLORS["muted"], font=font_tiny)
        draw.text((self.width - PADDING - 90 * SCALE, footer_y + 14 * SCALE), "Dev: EvilHIMARS", fill=COLORS["muted"], font=font_tiny)

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
            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=6 * SCALE, fill=COLORS["border"])
            item = equip.get(slot_name)
            item_type = ""
            if item:
                item_type = item.get("Type", "") if isinstance(item, dict) else str(item)
            if item_type:
                icon_data = self.api.fetch_icon(item_type)
                try:
                    icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((ICON_SIZE - 8 * SCALE, ICON_SIZE - 8 * SCALE))
                    img.paste(icon, (x + 4 * SCALE, y + 4 * SCALE), icon)
                except:
                    pass
                tier = self._parse_tier(item_type)
                color = TIER_COLORS.get(tier, COLORS["border"])
                draw.rounded_rectangle([x - 1 * SCALE, y - 1 * SCALE, x + ICON_SIZE + 1 * SCALE, y + ICON_SIZE + 1 * SCALE], radius=7 * SCALE, outline=color, width=2 * SCALE)

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4

    def _draw_fame_star(self, draw, x, y, size):
        """Рисует звезду фейма."""
        r = size // 2
        cx, cy = x + r, y + r
        color = COLORS["warning"]
        points = []
        for i in range(5):
            angle = math.pi / 2 + i * 2 * math.pi / 5
            outer_x = cx + r * math.cos(angle)
            outer_y = cy - r * math.sin(angle)
            points.append((outer_x, outer_y))
            angle += math.pi / 5
            inner_x = cx + r * 0.4 * math.cos(angle)
            inner_y = cy - r * 0.4 * math.sin(angle)
            points.append((inner_x, inner_y))
        draw.polygon(points, fill=color)

    def _draw_silver_coin(self, draw, x, y, size):
        """Рисует монету серебра."""
        r = size // 2
        cx, cy = x + r, y + r
        draw.ellipse([x, y, x + size, y + size], fill=(150, 150, 160))
        draw.ellipse([x + 3, y + 3, x + size - 3, y + size - 3], fill=(180, 180, 190))
        try:
            font_coin = ImageFont.truetype("DejaVuSans-Bold.ttf", size // 2)
        except:
            font_coin = ImageFont.load_default()
        text = "$"
        tw = draw.textlength(text, font=font_coin)
        draw.text((cx - tw // 2, cy - size // 4), text, fill=(120, 120, 130), font=font_coin)
