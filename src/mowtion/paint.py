"""Small drawing helpers shared by the renderer and the poster images."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

from mowtion.easing import clamp


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgba(value: str, alpha: float) -> tuple[int, int, int, int]:
    r, g, b = rgb(value)
    return (r, g, b, int(clamp(alpha) * 255))


def rounded(draw: ImageDraw.ImageDraw, box, radius: int, fill, outline=None, width: int = 2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def partial_points(points: list[tuple[float, float]], p: float) -> list[tuple[float, float]]:
    """Polyline from the start up to fraction ``p``. The last point is the leading edge."""
    if not points:
        return []
    if p <= 0:
        return [points[0], points[0]]
    if p >= 1:
        return points
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    if total <= 0:
        return points
    target = total * p
    out = [points[0]]
    acc = 0.0
    for index, dist in enumerate(lengths):
        if acc + dist >= target:
            u = (target - acc) / dist if dist else 0
            ax, ay = points[index]
            bx, by = points[index + 1]
            out.append((ax + (bx - ax) * u, ay + (by - ay) * u))
            return out
        out.append(points[index + 1])
        acc += dist
    return out


def stroke(draw: ImageDraw.ImageDraw, points, p: float, fill, width: int):
    pts = partial_points(points, p)
    if len(pts) >= 2:
        draw.line(pts, fill=fill, width=width, joint="curve")


def shadow(base: Image.Image, box, radius: int, alpha: float = 0.18):
    """Soft drop shadow, a few stacked blurs stand-in. Calm, not a glow flash."""
    x, y, w, h = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for i, spread in enumerate((28, 16, 8)):
        a = int(255 * alpha * (0.35 - i * 0.08))
        if a <= 0:
            continue
        draw.rounded_rectangle(
            (x - spread * 0.3, y + 10 + i * 2, x + w + spread * 0.3, y + h + 18 + spread * 0.2),
            radius=radius + spread // 4,
            fill=(0, 0, 0, a),
        )
    return Image.alpha_composite(base.convert("RGBA"), layer)


def wrap_words(words: list[str], measure, max_width: float) -> list[list[str]]:
    lines: list[list[str]] = [[]]
    width = 0.0
    space = measure(" ")
    for word in words:
        piece = measure(word)
        if lines[-1] and width + space + piece > max_width:
            lines.append([])
            width = 0.0
        if lines[-1]:
            width += space
        lines[-1].append(word)
        width += piece
    return [line for line in lines if line]
