"""Клиент Albion Render API для загрузки иконок."""
import logging
import httpx
from cache_manager import IconCache

logger = logging.getLogger(__name__)
RENDER_URL = "https://render.albiononline.com/v1/item"


class RenderAPI:
    def __init__(self, cache: IconCache):
        self.cache = cache
        self.client = httpx.Client(timeout=15)

    def fetch_icon(self, item_type: str) -> bytes:
        """Загружает иконку. Пробует с энчантом (@3), если нет — без."""
        if not item_type:
            return self._placeholder()

        # Пробуем полное имя с энчантом
        cached = self.cache.get(item_type)
        if cached:
            return cached

        try:
            resp = self.client.get(f"{RENDER_URL}/{item_type}.png")
            if resp.status_code == 200:
                data = resp.content
                self.cache.set(item_type, data)
                return data
        except:
            pass

        # Если с энчантом не вышло — пробуем без
        if "@" in item_type:
            base = item_type.split("@")[0]
            cached = self.cache.get(base)
            if cached:
                return cached

            try:
                resp = self.client.get(f"{RENDER_URL}/{base}.png")
                resp.raise_for_status()
                data = resp.content
                self.cache.set(base, data)
                return data
            except Exception as e:
                logger.warning(f"Не загрузилась иконка {item_type}: {e}")

        return self._placeholder()

    def _placeholder(self) -> bytes:
        path = self.cache.cache_dir / "_placeholder.png"
        if path.exists():
            return path.read_bytes()
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (56, 56), (40, 40, 40, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 55, 55], outline=(60, 60, 60), width=1)
        draw.line([20, 28, 36, 28], fill=(100, 100, 100), width=2)
        draw.line([28, 20, 28, 36], fill=(100, 100, 100), width=2)
        img.save(path)
        return path.read_bytes()
