"""Генератор PNG-карточек киллов/смертей — shadcn/ui Dark Style."""
import io
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from render_api import RenderAPI
from cache_manager import IconCache

logger = logging.getLogger(__name__)

ICON_SIZE = 56
SMALL_ICON = 28
GAP = 12

SLOT_GRID = [
    ("Bag",      0, 0), ("Head",     1, 0), ("Cape",     2, 0),
    ("MainHand", 0, 1), ("Armor",    1, 1), ("OffHand",  2, 1),
    ("Potion",   0, 2), ("Shoes",    1, 2), ("Food",     2, 2),
    (None,       0, 3), ("Mount",    1, 3), (None,       2, 3),
]

# shadcn/ui color palette
COLORS = {
    "bg":           (9, 9, 11),        # zinc-950
    "card":         (24, 24, 27),      # zinc-900
    "border":       (39, 39, 42),      # zinc-800
    "muted":        (113, 113, 122),   # zinc-500
    "muted_fg":     (161, 161, 170),   # zinc-400
    "foreground":   (250, 250, 250),   # zinc-50
    "primary":      (250, 250, 250),   # white
    "destructive":  (239, 68, 68),     # red-500
    "success":      (34, 197, 94),     # green-500
    "warning":      (234, 179, 8),     # yellow-500
    "accent":       (59, 130, 246),    # blue-500
}

TIER_COLORS = {
    4: (96, 165, 250),    # blue-400
    5: (74, 222, 128),    # green-400
    6: (250, 204, 21),    # yellow-400
    7: (251, 146, 60),    # orange-400
    8: (248, 113, 113),   # red-400
}


class ImageRenderer:
    def __init__(self, render_api: RenderAPI):
        self.api = render_api
        self.width = 780
        self.height = 680
        self.radius = 12

    def render(self, event_data: dict, is_kill: bool) -> io.BytesIO:
        img = Image.new("RGBA", (self.width, self.height), COLORS["bg"])
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
            font_text = ImageFont.truetype("DejaVuSans.ttf", 13)
            font_small = ImageFont.truetype("DejaVuSans.ttf", 11)
            font_tiny = ImageFont.truetype("DejaVuSans.ttf", 10)
        except:
            font_title = font_heading = font_text = font_small = font_tiny = ImageFont.load_default()

        killer = event_data.get("Killer", {}) or {}
        victim = event_data.get("Victim", {}) or {}
        k_name = killer.get("Name", "Unknown")
        v_name = victim.get("Name", "Unknown")
        k_guild = killer.get("GuildName", "")
        v_guild = victim.get("GuildName", "")
        k_ip = killer.get("AverageItemPower", 0)
        v_ip = victim.get("AverageItemPower", 0)
        fame = event_data.get("TotalVictimKillFame", 0)

        padding = 20

        # === HEADER CARD ===
        header_h = 100
        draw.rounded_rectangle(
            [padding, padding, self.width - padding, padding + header_h],
            radius=self.radius, fill=COLORS["card"]
        )

        # Status badge
        badge_w = 90
        badge_h = 30
        badge_x = padding + 16
        badge_y = padding + 16
        badge_color = COLORS["success"] if is_kill else COLORS["destructive"]
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
            radius=6, fill=badge_color
        )
        badge_text = "VICTORY" if is_kill else "DEFEAT"
        btw = draw.textlength(badge_text, font=font_small)
        draw.text((badge_x + badge_w//2 - btw//2, badge_y + 7), badge_text, fill=(255,255,255), font=font_small)

        # Title
        title = f"{k_name} killed {v_name}"
        tw = draw.textlength(title, font=font_title)
        if tw > self.width - 200:
            title = f"{k_name[:10]}.. killed {v_name[:10]}.."
        draw.text((badge_x + badge_w + 16, badge_y + 2), title, fill=COLORS["foreground"], font=font_title)

        # Killer / Victim info
        draw.text((padding + 20, padding + 56), f"Killer", fill=COLORS["muted"], font=font_tiny)
        draw.text((padding + 20, padding + 72), k_name, fill=COLORS["foreground"], font=font_text)
        if k_guild:
            gw = draw.textlength(f"[{k_guild}]", font=font_small)
            draw.text((self.width - padding - 20 - gw, padding + 56), f"[{k_guild}]", fill=COLORS["muted_fg"], font=font_small)

        draw.text((padding + 20, padding + 56), f"Victim", fill=COLORS["muted"], font=font_tiny)

        # Fame badge
        fame_text = f"Fame: {fame:,}"
        ftw = draw.textlength(fame_text, font=font_text)
        draw.rounded_rectangle(
            [self.width - padding - 20 - ftw - 24, padding + 16, self.width - padding - 20, padding + 46],
            radius=8, fill=(39, 39, 42)
        )
        draw.text((self.width - padding - 20 - ftw - 12, padding + 22), fame_text, fill=COLORS["warning"], font=font_text)

        # === EQUIPMENT SECTION ===
        eq_y = padding + header_h + 16

        # Card for Killer build
        k_equip = killer.get("Equipment") or {}
        v_equip = victim.get("Equipment") or {}

        grid_w = 3 * (ICON_SIZE + GAP) - GAP
        grid_h = 4 * (ICON_SIZE + GAP) - GAP
        card_w = grid_w + 24
        card_h = grid_h + 40

        # Killer card
        killer_card_x = padding
        draw.rounded_rectangle(
            [killer_card_x, eq_y, killer_card_x + card_w, eq_y + card_h],
            radius=self.radius, fill=COLORS["card"]
        )
        draw.text((killer_card_x + 12, eq_y + 12), "KILLER BUILD", fill=COLORS["muted"], font=font_small)
        self._draw_build(draw, img, k_equip, killer_card_x + 12, eq_y + 32, font_tiny)

        # Victim card
        victim_card_x = self.width - padding - card_w
        draw.rounded_rectangle(
            [victim_card_x, eq_y, victim_card_x + card_w, eq_y + card_h],
            radius=self.radius, fill=COLORS["card"]
        )
        draw.text((victim_card_x + 12, eq_y + 12), "VICTIM BUILD", fill=COLORS["muted"], font=font_small)
        self._draw_build(draw, img, v_equip, victim_card_x + 12, eq_y + 32, font_tiny)

        # Center stats between cards
        center_x = self.width // 2
        center_y = eq_y + card_h // 2
        draw.rounded_rectangle(
            [center_x - 50, center_y - 35, center_x + 50, center_y + 35],
            radius=8, fill=COLORS["card"]
        )
        draw.text((center_x - 30, center_y - 18), f"IP K: {k_ip:.0f}", fill=COLORS["muted_fg"], font=font_small)
        draw.text((center_x - 30, center_y), f"IP V: {v_ip:.0f}", fill=COLORS["muted_fg"], font=font_small)

        # === COMBAT STATS CARD ===
        stats_y = eq_y + card_h + 16
        stats_h = 180
        draw.rounded_rectangle(
            [padding, stats_y, self.width - padding, stats_y + stats_h],
            radius=self.radius, fill=COLORS["card"]
        )
        draw.text((padding + 16, stats_y + 14), "COMBAT STATS", fill=COLORS["muted"], font=font_small)

        # Damage bar
        participants = event_data.get("Participants") or []
        total_dmg = event_data.get("TotalDamage", 0) or sum(p.get("DamageDone", 0) for p in participants)

        bar_x = padding + 16
        bar_y = stats_y + 40
        bar_w = self.width - padding * 2 - 32
        bar_h = 8

        draw.text((bar_x, bar_y - 16), f"Total Damage: {total_dmg:,}", fill=COLORS["muted_fg"], font=font_small)
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4, fill=COLORS["border"])
        if total_dmg > 0:
            fill_w = int(bar_w * 0.75)
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=4, fill=COLORS["destructive"])

        # Participants
        if participants:
            part_y = bar_y + 24
            for i, p in enumerate(participants[:5]):
                col = i % 2
                row = i // 2
                px = bar_x + col * 370
                py = part_y + row * 40

                p_name = p.get("Name", "?")[:16]
                p_dmg = p.get("DamageDone", 0)
                p_heal = p.get("SupportValue", 0)
                p_weapon = p.get("Equipment", {}).get("MainHand", {})
                p_weapon_type = p_weapon.get("Type", "") if isinstance(p_weapon, dict) else str(p_weapon) if p_weapon else ""

                # Weapon icon
                if p_weapon_type:
                    icon_data = self.api.fetch_icon(p_weapon_type)
                    try:
                        icon = Image.open(io.BytesIO(icon_data)).convert("RGBA").resize((SMALL_ICON, SMALL_ICON))
                        img.paste(icon, (px, py), icon)
                    except:
                        draw.rounded_rectangle([px, py, px + SMALL_ICON, py + SMALL_ICON], radius=4, fill=COLORS["border"])
                    tier = self._parse_tier(p_weapon_type)
                    color = TIER_COLORS.get(tier, COLORS["border"])
                    draw.rounded_rectangle([px-1, py-1, px+SMALL_ICON+1, py+SMALL_ICON+1], radius=4, outline=color, width=1)
                else:
                    draw.rounded_rectangle([px, py, px + SMALL_ICON, py + SMALL_ICON], radius=4, fill=COLORS["border"])

                draw.text((px + SMALL_ICON + 8, py), p_name, fill=COLORS["foreground"], font=font_small)
                stats_text = f"DMG: {p_dmg:,}  HEAL: {p_heal:,}"
                draw.text((px + SMALL_ICON + 8, py + 16), stats_text, fill=COLORS["muted_fg"], font=font_tiny)

        # === FOOTER ===
        footer_y = self.height - 36
        ts = event_data.get("TimeStamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = dt.strftime("%d.%m.%Y %H:%M UTC")
            except:
                ts_str = ts
        else:
            ts_str = ""

        draw.text((padding + 4, footer_y), "Server: Europe", fill=COLORS["muted"], font=font_tiny)
        draw.text((padding + 4, footer_y + 14), "Albion Eclipse Killboard", fill=COLORS["muted"], font=font_tiny)
        if ts_str:
            tsw = draw.textlength(ts_str, font=font_tiny)
            draw.text((self.width - padding - tsw, footer_y), ts_str, fill=COLORS["muted"], font=font_tiny)
        draw.text((self.width - padding - 90, footer_y + 14), "Dev: EvilHIMARS", fill=COLORS["muted"], font=font_tiny)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _draw_build(self, draw, img, equip, start_x, start_y, font):
        for slot_entry in SLOT_GRID:
            slot_name, col, row = slot_entry
            if slot_name is None:
                continue

            x = start_x + col * (ICON_SIZE + GAP)
            y = start_y + row * (ICON_SIZE + GAP)

            draw.rounded_rectangle([x, y, x + ICON_SIZE, y + ICON_SIZE], radius=6, fill=COLORS["border"])

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
                color = TIER_COLORS.get(tier, COLORS["border"])
                draw.rounded_rectangle([x-1, y-1, x+ICON_SIZE+1, y+ICON_SIZE+1], radius=7, outline=color, width=2)

    def _parse_tier(self, item_type: str) -> int:
        try:
            return int(item_type[1])
        except:
            return 4
