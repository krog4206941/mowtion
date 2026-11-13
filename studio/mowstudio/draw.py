"""Draw the black panel look: hook, footage, captions, notes, end card.

The background is pure black, RGB (0, 0, 0). It is never navy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from mowstudio.fonts import font_file
from mowstudio.segments import group_words

BLACK = (0, 0, 0)
CYAN = (88, 225, 235)
WHITE = (245, 247, 248)
GREY = (156, 167, 177)
DIM = (38, 49, 56)
PILL = (13, 63, 69)

INTRO = 2.5
OUTRO = 2.25
FPS = 24


@dataclass
class Card:
    hook: tuple[str, str] = ("WATCH THIS.", "IN THEIR OWN WORDS.")
    headline: str = "IN THEIR OWN WORDS"
    subtitle: str = ""
    source: str = "SOURCE"
    date: str = ""
    end: tuple[str, str] = ("THAT IS THE POINT.", "FULL SOURCE IN THE POST.")
    accents: list[str] = field(default_factory=list)
    music: bool = False
    aspect: str = "16:9"
    has_footage: bool = True

    def __post_init__(self) -> None:
        def up(value: str, limit: int = 90) -> str:
            text = " ".join((value or "").split()).upper()
            return text[:limit]

        self.hook = (up(self.hook[0], 80) or "WATCH THIS.", up(self.hook[1], 80) or "IN THEIR OWN WORDS.")
        self.headline = up(self.headline, 120) or "IN THEIR OWN WORDS"
        self.source = up(self.source, 48) or "SOURCE"
        self.date = up(self.date, 24)
        self.end = (up(self.end[0], 80) or "THAT IS THE POINT.", up(self.end[1], 90) or "FULL SOURCE IN THE POST.")
        self.accents = [up(line, 42) for line in self.accents if line and line.strip()][:6]
        self.subtitle = " ".join((self.subtitle or "").split())[:140]


@dataclass
class Layout:
    w: int
    h: int
    video_xy: tuple[int, int]
    video_size: tuple[int, int]
    left_panel: tuple[int, int, int, int]
    right_panel: tuple[int, int, int, int]
    caption_y: int
    caption_size: int
    caption_max_w: int
    max_words: int
    progress: tuple[int, int, int]
    headline_xy: tuple[int, int]
    headline_max: int
    headline_size: int
    subtitle_xy: tuple[int, int]
    label_y: int


def layout_for(aspect: str) -> Layout:
    if aspect == "9:16":
        return Layout(
            w=1080,
            h=1920,
            video_xy=(72, 330),
            video_size=(936, 526),
            left_panel=(48, 292, 1032, 890),
            right_panel=(48, 1088, 1032, 1820),
            caption_y=930,
            caption_size=40,
            caption_max_w=960,
            max_words=4,
            progress=(48, 1864, 1032),
            headline_xy=(48, 92),
            headline_max=984,
            headline_size=46,
            subtitle_xy=(48, 200),
            label_y=42,
        )
    return Layout(
        w=1920,
        h=1080,
        video_xy=(96, 278),
        video_size=(1120, 630),
        left_panel=(62, 236, 1250, 920),
        right_panel=(1284, 236, 1858, 920),
        caption_y=968,
        caption_size=48,
        caption_max_w=1710,
        max_words=6,
        progress=(64, 1048, 1856),
        headline_xy=(64, 86),
        headline_max=1790,
        headline_size=58,
        subtitle_xy=(68, 172),
        label_y=34,
    )


class FontBook:
    def __init__(self) -> None:
        self.paths = {
            "bold": str(font_file("bold")),
            "regular": str(font_file("regular")),
            "mono": str(font_file("mono")),
        }
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def font(self, size: int, kind: str) -> ImageFont.FreeTypeFont:
        key = (kind, int(size))
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(self.paths[kind], int(size))
        return self._cache[key]

    def width(self, text: str, size: int, kind: str) -> float:
        return float(self.font(size, kind).getlength(text or ""))


def ease(amount: float) -> float:
    amount = max(0.0, min(1.0, amount))
    return 1 - (1 - amount) ** 3


def _text(draw: ImageDraw.ImageDraw, xy, text: str, size: int, fill, kind: str, fonts: FontBook, anchor=None) -> None:
    if not text:
        return
    draw.text(xy, text, font=fonts.font(size, kind), fill=fill, anchor=anchor)


def fit(draw, xy, text: str, max_w: int, size: int, fill, kind: str, fonts: FontBook, min_size: int = 18) -> None:
    shown = " ".join((text or "").split())
    if not shown:
        return
    while size > min_size and fonts.width(shown, size, kind) > max_w:
        size -= 1
    while shown and fonts.width(shown, size, kind) > max_w:
        shown = shown[:-2].rstrip()
        if shown:
            shown = shown.rstrip(".") + "..."
    _text(draw, xy, shown, size, fill, kind, fonts)


def _node(draw, x, y, label: str, fonts: FontBook, active: bool = True, max_w: int = 320) -> None:
    label = " ".join((label or "").split())
    size = 20
    while size > 14 and fonts.width(label, size, "mono") > max_w - 36:
        size -= 1
    shown = label
    while shown and fonts.width(shown, size, "mono") > max_w - 36:
        shown = shown[:-2].rstrip()
        if shown:
            shown = shown + "..."
    half_w = max(120, int(fonts.width(shown, size, "mono") / 2) + 22)
    draw.rounded_rectangle((x - half_w, y - 28, x + half_w, y + 28), radius=11, outline=CYAN if active else DIM, width=2)
    _text(draw, (x, y), shown, size, WHITE if active else GREY, "mono", fonts, anchor="mm")


def _chrome(card: Card, layout: Layout, fonts: FontBook) -> Image.Image:
    image = Image.new("RGB", (layout.w, layout.h), BLACK)
    draw = ImageDraw.Draw(image)
    _text(draw, (layout.headline_xy[0], layout.label_y), card.source, 22, GREY, "mono", fonts)
    if card.date:
        _text(draw, (layout.w - 64, layout.label_y), card.date, 22, GREY, "mono", fonts, anchor="ra")
    fit(draw, layout.headline_xy, card.headline, layout.headline_max, layout.headline_size, WHITE, "bold", fonts, min_size=28)
    if card.subtitle:
        fit(draw, layout.subtitle_xy, card.subtitle, layout.headline_max, 28, GREY, "regular", fonts, min_size=18)
    draw.rounded_rectangle(layout.left_panel, radius=20, outline=DIM, width=2)
    draw.rounded_rectangle(layout.right_panel, radius=20, outline=DIM, width=2)
    _text(draw, (layout.left_panel[0] + 22, layout.left_panel[1] + 12), "SOURCE: " + card.source, 18, GREY, "mono", fonts)
    if layout.w > 1200 and card.date:
        _text(
            draw,
            (layout.left_panel[2] - 22, layout.left_panel[1] + 12),
            "RECORDED: " + card.date,
            18,
            GREY,
            "mono",
            fonts,
            anchor="ra",
        )
    return image


def _checklist(draw, card: Card, layout: Layout, fonts: FontBook, progress: float, t: float) -> None:
    x0, y0, x1, y1 = layout.right_panel
    _text(draw, (x0 + 26, y0 + 28), "THE POINT", 22, CYAN, "mono", fonts)
    items = card.accents[:6]
    top = y0 + 90
    room = max(1, (y1 - 30) - top)
    step = min(78, room / max(1, len(items)))
    for index, label in enumerate(items):
        y = top + index * step
        on = progress >= (index + 0.15) / max(1, len(items))
        draw.rounded_rectangle((x0 + 28, y, x0 + 64, y + 36), radius=8, outline=CYAN if on else DIM, width=3)
        if on:
            draw.line([(x0 + 36, y + 18), (x0 + 46, y + 28), (x0 + 58, y + 8)], fill=CYAN, width=4)
        fit(draw, (x0 + 80, y + 4), label, x1 - x0 - 120, 26, WHITE if on else GREY, "bold", fonts, min_size=16)


def _clock(draw, cx: int, cy: int, t: float) -> None:
    draw.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), outline=WHITE, width=3)
    for k in range(12):
        angle = k / 12 * 2 * math.pi
        draw.line(
            (
                cx + int(92 * math.sin(angle)),
                cy - int(92 * math.cos(angle)),
                cx + int(104 * math.sin(angle)),
                cy - int(104 * math.cos(angle)),
            ),
            fill=DIM,
            width=3,
        )
    angle = (t % 12) / 12 * 2 * math.pi
    draw.line((cx, cy, cx + int(70 * math.sin(angle)), cy - int(70 * math.cos(angle))), fill=CYAN, width=4)


def _bars(draw, x: int, y: int, progress: float, fonts: FontBook) -> None:
    labels = ["NOW", "NEXT", "LATER"]
    heights = [70, 140, 220]
    for index, (label, height) in enumerate(zip(labels, heights)):
        grown = int(height * ease(max(0.0, min(1.0, progress * 1.4 - index * 0.15))))
        left = x + index * 150
        draw.rectangle((left, y - grown, left + 90, y), outline=WHITE if grown > 8 else DIM, width=2)
        if index == 0 and grown > 8:
            draw.rectangle((left + 3, y - grown + 3, left + 87, y - 3), fill=CYAN)
        _text(draw, (left + 45, y + 16), label, 18, GREY, "mono", fonts, anchor="ma")


def _infographic(draw, card: Card, layout: Layout, fonts: FontBook, speech_t: float, speech_dur: float) -> None:
    progress = 0.0 if speech_dur <= 0 else max(0.0, min(1.0, speech_t / speech_dur))
    x0, y0, x1, y1 = layout.right_panel
    sweep = x0 + int((x1 - x0) * progress)
    draw.line((x0, y0, sweep, y0), fill=CYAN, width=3)
    if card.accents:
        _checklist(draw, card, layout, fonts, progress, speech_t)
        return
    cx = (x0 + x1) // 2
    if progress < 0.34:
        _text(draw, (x0 + 26, y0 + 36), "THE TIME", 22, CYAN, "mono", fonts)
        _clock(draw, cx, y0 + 230, speech_t)
        fit(draw, (x0 + 26, y1 - 80), "Listen to the whole point.", x1 - x0 - 52, 24, GREY, "regular", fonts)
    elif progress < 0.67:
        _text(draw, (x0 + 26, y0 + 36), "BUILDING", 22, CYAN, "mono", fonts)
        _bars(draw, x0 + 40, y1 - 120, progress, fonts)
    else:
        _text(draw, (x0 + 26, y0 + 36), "THE POINT", 22, CYAN, "mono", fonts)
        fit(draw, (x0 + 26, y0 + 140), card.end[0], x1 - x0 - 52, 42, WHITE, "bold", fonts, min_size=22)
        fit(draw, (x0 + 26, y0 + 220), card.end[1], x1 - x0 - 52, 36, CYAN, "bold", fonts, min_size=20)
        width = int((x1 - x0 - 52) * ease((progress - 0.67) / 0.33))
        draw.line((x0 + 26, y0 + 300, x0 + 26 + width, y0 + 300), fill=CYAN, width=4)


def _captions(image: Image.Image, groups: list[list[dict]], local_t: float, layout: Layout, fonts: FontBook) -> None:
    draw = ImageDraw.Draw(image)
    size = layout.caption_size
    for group in groups:
        if group[0]["start"] <= local_t < group[-1]["end"] + 0.08:
            space = fonts.width(" ", size, "bold")
            widths = [fonts.width(word["text"], size, "bold") for word in group]
            total = sum(widths) + space * (len(group) - 1)
            x = (layout.w - total) / 2
            y = layout.caption_y
            for word, width in zip(group, widths):
                active = word["start"] <= local_t < word["end"]
                if active:
                    draw.rounded_rectangle((x - 8, y - 6, x + width + 8, y + size + 10), radius=10, fill=PILL)
                _text(draw, (x, y), word["text"], size, CYAN if active else WHITE, "bold", fonts)
                x += width + space
            break


def _panel_words(image: Image.Image, groups, local_t: float, layout: Layout, fonts: FontBook) -> None:
    """When there is no footage, put the current line inside the panel."""
    draw = ImageDraw.Draw(image)
    current = ""
    for group in groups:
        if group[0]["start"] <= local_t < group[-1]["end"] + 0.08:
            current = " ".join(word["text"] for word in group)
            break
    if not current:
        return
    x0, y0, x1, y1 = layout.left_panel
    fit(draw, (x0 + 36, (y0 + y1) // 2 - 30), current, x1 - x0 - 72, 42, WHITE, "bold", fonts, min_size=22)


def draw_intro(card: Card, layout: Layout, fonts: FontBook, t: float) -> Image.Image:
    image = Image.new("RGB", (layout.w, layout.h), BLACK)
    draw = ImageDraw.Draw(image)
    label = "  /  ".join(part for part in (card.source, card.date) if part)
    _text(draw, (72, 64 if layout.w > 1200 else 80), label, 22, GREY, "mono", fonts)
    y = 250 if layout.w > 1200 else 360
    y -= int(10 * ease(t / INTRO))
    fit(draw, (72, y), card.hook[0], layout.w - 160, 78 if layout.w > 1200 else 64, WHITE, "bold", fonts, min_size=32)
    fit(draw, (72, y + 110), card.hook[1], layout.w - 150, 72 if layout.w > 1200 else 58, CYAN, "bold", fonts, min_size=28)
    if card.subtitle:
        fit(draw, (76, y + 240), card.subtitle, layout.w - 180, 30, GREY, "regular", fonts)
    nodes = card.accents[:2] or ["WATCH", "LISTEN"]
    base_y = 620 if layout.w > 1200 else 980
    base_x = layout.w - 280 if layout.w > 1200 else layout.w // 2
    for index, label_text in enumerate(nodes):
        _node(draw, base_x, base_y + index * 110, label_text, fonts, active=t > index * 0.7)
    line_w = int((layout.w - 200) * ease((t + 0.2) / INTRO))
    line_y = 900 if layout.w > 1200 else 1500
    draw.line((76, line_y, 76 + line_w, line_y), fill=CYAN, width=4)
    foot = "SOURCE FOOTAGE" if card.has_footage else "VOICE ONLY"
    _text(draw, (76, layout.h - 78), foot + "  •  " + card.source, 20, GREY, "mono", fonts)
    return image


def draw_content(
    card: Card,
    layout: Layout,
    fonts: FontBook,
    chrome: Image.Image,
    video_frame: Image.Image | None,
    groups: list[list[dict]],
    t: float,
    speech_dur: float,
) -> Image.Image:
    image = chrome.copy()
    local = t - INTRO
    if video_frame is not None:
        frame = video_frame.resize(layout.video_size, Image.Resampling.BILINEAR)
        image.paste(frame, layout.video_xy)
    else:
        _panel_words(image, groups, local, layout, fonts)
    draw = ImageDraw.Draw(image)
    _infographic(draw, card, layout, fonts, local, speech_dur)
    _captions(image, groups, local, layout, fonts)
    x0, y, x1 = layout.progress
    draw.line((x0, y, x1, y), fill=DIM, width=2)
    if speech_dur > 0:
        draw.line((x0, y, x0 + int((x1 - x0) * max(0.0, min(1.0, local / speech_dur))), y), fill=CYAN, width=3)
    return image


def draw_end(card: Card, layout: Layout, fonts: FontBook) -> Image.Image:
    image = Image.new("RGB", (layout.w, layout.h), BLACK)
    draw = ImageDraw.Draw(image)
    _text(draw, (76, 120 if layout.w > 1200 else 220), "THE TAKEAWAY", 24, CYAN, "mono", fonts)
    y = 300 if layout.w > 1200 else 460
    fit(draw, (72, y), card.end[0], layout.w - 150, 72, WHITE, "bold", fonts, min_size=32)
    fit(draw, (72, y + 110), card.end[1], layout.w - 150, 64, CYAN, "bold", fonts, min_size=28)
    _text(draw, (76, y + 280), "In the speaker's own words.", 32, WHITE, "regular", fonts)
    line_y = y + 380
    draw.line((76, line_y, layout.w - 76, line_y), fill=DIM, width=2)
    _text(draw, (76, line_y + 36), "SOURCE: " + card.source, 22, GREY, "mono", fonts)
    if card.date:
        _text(draw, (76, line_y + 72), "RECORDED: " + card.date, 22, GREY, "mono", fonts)
    _text(draw, (76, line_y + 120), "FULL SOURCE IN THE POST", 22, GREY, "mono", fonts)
    return image


def prepare_groups(words: list[dict], layout: Layout, fonts: FontBook) -> list[list[dict]]:
    size = layout.caption_size

    def measure(phrase: str) -> float:
        return fonts.width(phrase, size, "bold")

    return group_words(words, measure, max_words=layout.max_words, max_width=layout.caption_max_w)


def render_still(card: Card, t: float, words: list[dict] | None = None, video_frame: Image.Image | None = None, speech_dur: float = 8) -> Image.Image:
    """Draw one frame. Used by tests and by the movie renderer."""
    fonts = FontBook()
    layout = layout_for(card.aspect)
    groups = prepare_groups(words or [], layout, fonts)
    if t < INTRO:
        return draw_intro(card, layout, fonts, t)
    if t < INTRO + speech_dur:
        chrome = _chrome(card, layout, fonts)
        return draw_content(card, layout, fonts, chrome, video_frame, groups, t, speech_dur)
    return draw_end(card, layout, fonts)
