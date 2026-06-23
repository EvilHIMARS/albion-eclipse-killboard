"""Кэш иконок предметов Albion на диске."""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IconCache:
    def __init__(self, cache_dir: str = "cache/icons"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, item_type: str) -> bytes | None:
        path = self.cache_dir / f"{item_type}.png"
        if path.exists():
            return path.read_bytes()
        return None

    def set(self, item_type: str, data: bytes):
        path = self.cache_dir / f"{item_type}.png"
        path.write_bytes(data)

    def has(self, item_type: str) -> bool:
        return (self.cache_dir / f"{item_type}.png").exists()