"""Bundled OFL fonts. Renders do not depend on fonts installed on the machine."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

_FONT_FILES = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
    "serif": "InstrumentSerif-Regular.ttf",
    "serif-italic": "InstrumentSerif-Italic.ttf",
    "mono": "JetBrainsMono-Regular.ttf",
    "mono-bold": "JetBrainsMono-Bold.ttf",
}


def font_dir() -> Path:
    here = Path(__file__).resolve().parent / "assets" / "fonts"
    if here.is_dir():
        return here
    # PyInstaller extracts package data next to the bundle root.
    import sys

    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for candidate in (root / "mowtion" / "assets" / "fonts", root / "assets" / "fonts"):
            if candidate.is_dir():
                return candidate
    return here


@lru_cache(maxsize=256)
def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    path = font_dir() / _FONT_FILES[role]
    if not path.is_file():
        raise FileNotFoundError(f"Missing bundled font {path.name}")
    return ImageFont.truetype(str(path), size)


def fonts_ok() -> bool:
    directory = font_dir()
    return all((directory / name).is_file() for name in _FONT_FILES.values())
