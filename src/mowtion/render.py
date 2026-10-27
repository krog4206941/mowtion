"""Code-drawn motion graphics.

Rules baked in here, on purpose:
- springs settle, they do not shake
- strokes grow from the leading edge
- the container is on screen before the words
- graphics hold for about 3–4 seconds
- dissolves, wipes, and irises are soft
- something (the grid, the waveform, the playhead) moves on every frame
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from mowtion.easing import clamp, container_open, ease_in_out, leading, lerp, spring, text_open
from mowtion.fonts import font
from mowtion.paint import partial_points, rgb, rgba, rounded, stroke, wrap_words
from mowtion.theme import get_theme

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080)}


def frame_size(aspect: str) -> tuple[int, int]:
    if aspect not in ASPECTS:
        raise ValueError(f"Aspect must be 9:16 or 16:9, not {aspect!r}")
    return ASPECTS[aspect]


@lru_cache(maxsize=8)
def _gradient(w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> np.ndarray:
    blend = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top = np.array(c1, dtype=np.float32)
    bottom = np.array(c2, dtype=np.float32)
    column = top * (1 - blend) + bottom * blend
    image = np.broadcast_to(column[:, None, :], (h, w, 3)).copy()
    ys = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    xs = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    radius = np.sqrt((xs * 0.85) ** 2 + ys**2)
    shade = np.clip(1 - np.clip(radius - 0.72, 0, 1) * 0.45, 0, 1)
    return (image * shade[..., None]).astype(np.uint8)


def _layout(w: int, h: int) -> dict:
    vertical = h > w
    margin = 72 if vertical else 84
    if vertical:
        stage = (margin, int(h * 0.15), w - 2 * margin, int(h * 0.60))
        caption_y = int(h * 0.80)
    else:
        stage = (margin, int(h * 0.18), w - 2 * margin, int(h * 0.56))
        caption_y = int(h * 0.80)
    return {"margin": margin, "stage": stage, "caption_y": caption_y, "vertical": vertical}


def _scene_at(project: dict, t: float) -> tuple[dict | None, dict | None]:
    scenes = project.get("scenes") or []
    current = None
    previous = None
    for scene in scenes:
        if scene["t0"] <= t:
            previous = current
            current = scene
        else:
            break
    if current is None and scenes:
        current = scenes[0]
    return previous, current


def _energy(project: dict, t: float) -> float:
    env = project.get("energy") or []
    if not env:
        return 0.25
    fps = project["format"]["fps"]
    index = int(t * fps)
    index = max(0, min(len(env) - 1, index))
    return float(env[index])


def _background(project: dict, theme, t: float) -> Image.Image:
    w, h = project["format"]["w"], project["format"]["h"]
    fps = project["format"]["fps"]
    base = _gradient(w, h, rgb(theme.bg), rgb(theme.bg2))
    image = Image.fromarray(base, "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    # Two slow blobs. Positions are continuous, so the plate never sits still.
    blobs = (
        (0.2, 0.18, 0.55, theme.accent, 0.10),
        (0.82, 0.72, 0.48, theme.accent2, 0.08),
    )
    for cx, cy, scale, color, alpha in blobs:
        dx = math.sin(t * 0.23 + cx) * 0.03
        dy = math.cos(t * 0.19 + cy) * 0.03
        rad = int(min(w, h) * scale)
        x = int((cx + dx) * w)
        y = int((cy + dy) * h)
        draw.ellipse((x - rad, y - rad, x + rad, y + rad), fill=rgba(color, alpha))
    # Dot grid drifts one pixel every other frame. Slow, always in motion.
    step = 64
    frame = int(round(t * fps))
    ox = (frame // 2) % step
    oy = (frame // 3) % step
    dot = rgba(theme.ink, 0.16)
    ys = range(oy, h, step)
    xs = range(ox, w, step)
    for y in ys:
        for x in xs:
            draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=dot)
    lay = _layout(w, h)
    margin = lay["margin"]
    # Header
    draw.text((margin, 56 if lay["vertical"] else 40), "MOWTION", font=font("mono", 22), fill=rgba(theme.muted, 0.9))
    preset = theme.name.upper()
    pw = font("mono", 22).getlength(preset)
    draw.text((w - margin - pw, 56 if lay["vertical"] else 40), preset, font=font("mono", 22), fill=rgba(theme.accent, 1))
    # Playhead. It advances with time, so a held graphic still has a moving edge.
    duration = max(0.1, float(project.get("duration") or 1))
    y = 108 if lay["vertical"] else 84
    x0, x1 = margin, w - margin
    draw.line((x0, y, x1, y), fill=rgba(theme.line, 1), width=4)
    head = lerp(x0, x1, clamp(t / duration))
    draw.line((x0, y, head, y), fill=rgba(theme.accent, 1), width=4)
    draw.ellipse((head - 7, y - 7, head + 7, y + 7), fill=rgba(theme.accent, 1))
    _footer(draw, theme, t, project, lay)
    return image


def _footer(draw, theme, t, project, lay):
    w, h = project["format"]["w"], project["format"]["h"]
    bpm = float(project.get("music", {}).get("bpm") or 96)
    energy = _energy(project, t)
    n = 42 if lay["vertical"] else 64
    gap = 14
    total = n * gap
    x = (w - total) / 2
    base = h - (78 if lay["vertical"] else 56)
    phase = (t * bpm / 60.0) % 1.0
    pulse = math.exp(-phase * 6)
    for i in range(n):
        idle = 0.25 + 0.2 * abs(math.sin(t * 1.5 + i * 0.5))
        height = 6 + (idle + 0.55 * energy + 0.12 * pulse) * (28 if lay["vertical"] else 20)
        xx = x + i * gap
        color = theme.accent if abs(i - n / 2) < n * 0.12 else theme.ink
        draw.line((xx, base - height / 2, xx, base + height / 2), fill=rgba(color, 0.85), width=4)


def _panel(draw, theme, box, open_p: float):
    if open_p <= 0.01:
        return
    x, y, w, h = box
    slide = (1 - clamp(open_p)) * 26
    rect = (x, y + slide, x + w, y + h + slide)
    rounded(draw, rect, 32, rgba(theme.panel, 0.96 * clamp(open_p)), rgba(theme.line, clamp(open_p)), 2)


def _caption(draw, theme, scene, t, lay, w):
    words = scene.get("words") or []
    if not words:
        return
    size = 36 if lay["vertical"] else 32
    face = font("semibold", size)
    max_w = w - lay["margin"] * 2
    lines = wrap_words([word["text"] for word in words], face.getlength, max_w)
    # Flatten back so we can match spoken words. Wrap may split them.
    spoken = None
    for word in words:
        if word["start"] <= t <= word["end"] + 0.08:
            spoken = word["text"]
    if spoken is None:
        for word in words:
            if word["start"] <= t:
                spoken = word["text"]
    y = lay["caption_y"]
    for line in lines[:3]:
        widths = [face.getlength(word) for word in line]
        space = face.getlength(" ")
        total = sum(widths) + space * (len(line) - 1)
        x = (w - total) / 2
        for word, width in zip(line, widths):
            color = theme.accent if word == spoken else theme.ink
            alpha = 1.0 if text_open(t - scene["t0"]) > 0.05 else 0.0
            if alpha:
                draw.text((x, y), word, font=face, fill=rgba(color, alpha))
            x += width + space
        y += size + 12


def _fit_size(text_lines: list[str], role: str, max_w: float, start: int, minimum: int) -> int:
    size = start
    while size > minimum:
        face = font(role, size)
        if all(face.getlength(line) <= max_w for line in text_lines):
            return size
        size -= 2
    return minimum


def _draw_kinetic(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    words = scene["words"]
    if not words or text_open(local) <= 0:
        return
    max_w = w - 80
    # Build up to three lines of the phrase.
    tokens = [word["text"] for word in words]
    size = _fit_size([" ".join(tokens)], "bold", max_w, 78 if h > 700 else 64, 36)
    face = font("bold", size)
    lines = wrap_words(tokens, face.getlength, max_w)[:4]
    line_h = size + 16
    block = line_h * len(lines)
    cy = y + h / 2 - block / 2
    cursor = 0
    for line in lines:
        widths = [face.getlength(word) for word in line]
        space = face.getlength(" ")
        total = sum(widths) + space * max(0, len(line) - 1)
        xx = x + (w - total) / 2
        for word, width in zip(line, widths):
            src = words[min(cursor, len(words) - 1)]
            p = spring(t - src["start"], 9.0, 0.82)
            cursor += 1
            if p <= 0:
                xx += width + space
                continue
            accent = cursor == len(words)
            role_font = font("serif-italic", int(size * 1.05)) if accent else face
            slide = (1 - clamp(p)) * 36
            color = theme.accent if accent else theme.ink
            draw.text((xx, cy + slide), word, font=role_font, fill=rgba(color, clamp(p)))
            xx += width + space
        cy += line_h


def _draw_card(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    if container_open(local) < 0.35:
        return
    pad = 48
    title = scene["title"]
    size = _fit_size([title], "bold", w - pad * 2, 48, 28)
    text_p = text_open(local)
    if text_p > 0:
        draw.text((x + pad, y + 64), title, font=font("bold", size), fill=rgba(theme.ink, clamp(text_p)))
    # Rules draw from the left edge.
    speech = t - scene["speech_t0"]
    for i in range(3):
        yy = y + 180 + i * 56
        length = (w - pad * 2) * (1, 0.86, 0.62)[i]
        stroke(draw, [(x + pad, yy), (x + pad + length, yy)], leading(speech - 0.15 * i, 0.8), rgba(theme.line, 1), 10)
    # A check that draws on after the lines.
    p = leading(speech - 0.45, 0.45)
    if p > 0:
        cx, cy, s = x + pad + 16, y + h - 90, 28
        pts = [(cx - s * 0.4, cy), (cx - s * 0.05, cy + s * 0.35), (cx + s * 0.5, cy - s * 0.4)]
        stroke(draw, pts, p, rgba(theme.accent, 1), 6)
        if text_p > 0.4:
            draw.text((cx + 36, cy - 16), "ready", font=font("mono", 28), fill=rgba(theme.accent, clamp(text_p)))


def _draw_bars(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    if container_open(local) < 0.3:
        return
    bars = scene.get("bars") or []
    if not bars:
        return
    speech = t - scene["speech_t0"]
    base = y + h - 120
    count = len(bars)
    gap = 28
    bw = min(84, (w - 120 - gap * (count - 1)) / count)
    total = count * bw + (count - 1) * gap
    x0 = x + (w - total) / 2
    # Baseline is the container; the bars grow up from it, cap first.
    draw.line((x + 48, base, x + w - 48, base), fill=rgba(theme.line, 1), width=3)
    max_h = h * 0.46
    for i, bar in enumerate(bars):
        lead = leading(speech - 0.12 * i, 0.85)
        trail = leading(speech - 0.12 * i - 0.1, 0.85)
        bh = max_h * bar["value"] * clamp(trail)
        bx = x0 + i * (bw + gap)
        if bh > 2:
            color = theme.accent if i == count - 1 else theme.ink
            rounded(draw, (bx, base - bh, bx + bw, base), 12, rgba(color, 0.95))
            cap_y = base - max_h * bar["value"] * clamp(lead)
            draw.rounded_rectangle((bx, cap_y - 6, bx + bw, cap_y + 8), radius=6, fill=rgba(theme.accent2, 0.95))
        if text_open(local) > 0.2:
            label = bar["label"]
            face = font("mono", 20)
            lw = face.getlength(label)
            draw.text((bx + bw / 2 - lw / 2, base + 18), label, font=face, fill=rgba(theme.muted, 1))


def _draw_ring(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    if container_open(local) < 0.3:
        return
    speech = t - scene["speech_t0"]
    p = leading(speech, 1.1)
    target = float(scene.get("ring") or 70)
    r = min(w, h) * 0.22
    cx, cy = x + w / 2, y + h / 2 - 20
    box_e = (cx - r, cy - r, cx + r, cy + r)
    draw.arc(box_e, 0, 360, fill=rgba(theme.line, 1), width=16)
    if p > 0:
        # Pillow arcs start at 3 o'clock and run clockwise. -90 puts the start at 12 o'clock.
        draw.arc(box_e, -90, -90 + 360 * (target / 100) * p, fill=rgba(theme.accent, 1), width=16)
    if text_open(local) > 0:
        label = str(int(round(target * p)))
        face = font("bold", 64)
        tw = face.getlength(label)
        draw.text((cx - tw / 2, cy - 36), label, font=face, fill=rgba(theme.ink, clamp(text_open(local))))


def _draw_line(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    if container_open(local) < 0.3:
        return
    points = scene.get("points") or [0.2, 0.4, 0.35, 0.6, 0.55, 0.8, 0.7, 0.9]
    speech = t - scene["speech_t0"]
    p = leading(speech, 1.15)
    left, right = x + 56, x + w - 56
    top, bottom = y + 80, y + h - 100
    draw.line((left, bottom, right, bottom), fill=rgba(theme.line, 1), width=3)
    coords = []
    for i, value in enumerate(points):
        px = left + (right - left) * (i / (len(points) - 1))
        py = bottom - (bottom - top) * float(value)
        coords.append((px, py))
    stroke(draw, coords, p, rgba(theme.accent, 1), 6)
    tip = partial_points(coords, p)[-1]
    draw.ellipse((tip[0] - 8, tip[1] - 8, tip[0] + 8, tip[1] + 8), fill=rgba(theme.accent, 1))


def _draw_abstract(draw, theme, scene, t, box):
    x, y, w, h = box
    local = t - scene["t0"]
    _panel(draw, theme, box, container_open(local))
    if container_open(local) < 0.25:
        return
    cx, cy = x + w / 2, y + h / 2
    speech = t - scene["speech_t0"]
    p = leading(max(0, speech), 1.0)
    for i in range(3):
        rad = 70 + i * 58
        draw.arc(
            (cx - rad, cy - rad, cx + rad, cy + rad),
            -90,
            -90 + 300 * p,
            fill=rgba(theme.accent if i == 1 else theme.accent2, 0.9),
            width=4,
        )
    for i in range(10):
        ang = t * 0.45 + i * (math.tau / 10)
        rad = 120 + 16 * math.sin(t * 0.8 + i)
        px = cx + math.cos(ang) * rad
        py = cy + math.sin(ang) * rad * 0.55
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=rgba(theme.accent, 0.8))
    if text_open(local) > 0:
        words = scene["title"].split()[:4]
        label = " ".join(words)
        size = _fit_size([label], "serif-italic", w - 80, 54, 28)
        face = font("serif-italic", size)
        tw = face.getlength(label)
        draw.text((cx - tw / 2, cy - size / 2), label, font=face, fill=rgba(theme.ink, clamp(text_open(local))))


_DRAW = {
    "kinetic": _draw_kinetic,
    "card": _draw_card,
    "bars": _draw_bars,
    "ring": _draw_ring,
    "line": _draw_line,
    "abstract": _draw_abstract,
}


def _foreground(project, theme, scene, t) -> Image.Image:
    w, h = project["format"]["w"], project["format"]["h"]
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    lay = _layout(w, h)
    box = lay["stage"]
    kind = scene.get("kind") or "kinetic"
    _DRAW.get(kind, _draw_kinetic)(draw, theme, scene, t, box)
    _caption(draw, theme, scene, t, lay, w)
    return image


def _blend(previous: Image.Image, current: Image.Image, p: float, kind: str) -> Image.Image:
    p = ease_in_out(p)
    if kind == "wipe":
        w, h = current.size
        mask = np.zeros((h, w), dtype=np.uint8)
        cutoff = p * w
        soft = max(8, int(w * 0.045))
        xs = np.arange(w)
        col = np.clip((cutoff - xs) / soft + 1, 0, 1)
        mask[:, :] = (col * 255).astype(np.uint8)[None, :]
        return Image.composite(current, previous, Image.fromarray(mask, "L"))
    if kind == "iris":
        w, h = current.size
        yy, xx = np.ogrid[0:h, 0:w]
        radius = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2)
        cutoff = p * math.hypot(w / 2, h / 2)
        soft = 28
        mask = np.clip((cutoff - radius) / soft + 1, 0, 1)
        return Image.composite(current, previous, Image.fromarray((mask * 255).astype(np.uint8), "L"))
    return Image.blend(previous, current, p)


def render_frame(project: dict, t: float) -> Image.Image:
    theme = get_theme(project["preset"])
    w, h = project["format"]["w"], project["format"]["h"]
    background = _background(project, theme, t)
    _previous, current = _scene_at(project, t)
    if current is None:
        return background.convert("RGB")
    current_fg = _foreground(project, theme, current, t)
    xfade = float(project.get("pacing", {}).get("crossfade_s") or 0.65)
    if _previous is not None and t < current["t0"] + xfade:
        old = _foreground(project, theme, _previous, min(t, _previous["t1"] - 0.01))
        current_fg = _blend(old, current_fg, (t - current["t0"]) / xfade, current.get("transition") or "dissolve")
    # Soft open and soft close. The background keeps moving underneath.
    duration = float(project.get("duration") or t + 1)
    fade = 1.0
    if t < 0.35:
        fade *= ease_in_out(t / 0.35)
    if t > duration - 0.6:
        fade *= ease_in_out((duration - t) / 0.6)
    if fade < 0.999:
        arr = np.array(current_fg)
        arr[..., 3] = (arr[..., 3].astype(np.float32) * fade).astype(np.uint8)
        current_fg = Image.fromarray(arr, "RGBA")
    background.alpha_composite(current_fg)
    return background.convert("RGB")
