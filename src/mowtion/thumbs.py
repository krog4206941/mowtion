"""Still images for the posting pack: a 16:9 thumbnail and a cover in the video shape."""

from __future__ import annotations

from PIL import Image, ImageDraw

from mowtion.fonts import font
from mowtion.paint import rgb, rgba
from mowtion.theme import Theme


def _cover(theme: Theme, title: str, w: int, h: int) -> Image.Image:
    image = Image.new("RGB", (w, h), rgb(theme.bg))
    draw = ImageDraw.Draw(image, "RGBA")
    # A quiet accent field, fully drawn — this is a still, not a frame of the video.
    rad = int(min(w, h) * 0.42)
    draw.ellipse((int(w * 0.62) - rad, int(h * 0.28) - rad, int(w * 0.62) + rad, int(h * 0.28) + rad), fill=rgba(theme.accent, 0.16))
    margin = int(w * 0.08)
    draw.text((margin, int(h * 0.1)), "MOWTION", font=font("mono", max(18, w // 48)), fill=rgb(theme.muted))
    draw.text((margin, int(h * 0.1) + 36), theme.name.upper(), font=font("mono", max(18, w // 52)), fill=rgb(theme.accent))
    words = title.split()
    # Two lines, big.
    mid = max(1, len(words) // 2)
    lines = [" ".join(words[:mid]), " ".join(words[mid:])] if len(words) > 3 else [title]
    size = max(42, w // 16)
    y = int(h * 0.38)
    for index, line in enumerate(lines[:3]):
        while size > 28 and font("bold", size).getlength(line) > w - margin * 2:
            size -= 2
        face = font("serif-italic", size) if index == len(lines[:3]) - 1 else font("bold", size)
        color = theme.accent if index == len(lines[:3]) - 1 else theme.ink
        draw.text((margin, y), line, font=face, fill=rgb(color))
        y += size + 12
    y += 20
    draw.line((margin, y, margin + int(w * 0.28), y), fill=rgb(theme.accent), width=8)
    return image


def thumbnail(theme: Theme, title: str) -> Image.Image:
    return _cover(theme, title, 1280, 720)


def cover(theme: Theme, title: str, aspect: str) -> Image.Image:
    if aspect == "16:9":
        return _cover(theme, title, 1920, 1080)
    return _cover(theme, title, 1080, 1920)


def save_pack(theme: Theme, title: str, aspect: str, thumb_path, cover_path) -> None:
    thumbnail(theme, title).save(thumb_path, "PNG")
    cover(theme, title, aspect).save(cover_path, "PNG")
