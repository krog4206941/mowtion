"""Mind Over World videos: a typed script, literal pictures, quiet music, branded end card.

The background is pure black. Elon clips do not use this module, so they stay unbranded.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from mowstudio.audio import SR, load_mono, make_bed, master, write_wav
from mowstudio.fonts import font_file
from mowstudio.media import ffmpeg
from mowstudio.paths import FONT_DIR
from mowstudio.qc import inspect
from mowstudio.render import _encode

FPS = 24
OUTRO = 3.2
BLACK = (0, 0, 0)
WHITE = (242, 242, 242)
GREY = (150, 150, 150)
DIM = (70, 70, 70)
GOLD = (250, 199, 92)
RED = (237, 84, 76)

_STOP = {
    "a", "an", "the", "and", "or", "but", "if", "to", "of", "in", "on", "for", "with",
    "is", "it", "my", "me", "i", "you", "your", "we", "they", "this", "that", "so",
    "was", "were", "be", "at", "as", "not", "do", "did", "just", "from",
}


@dataclass
class Beat:
    spoken: str
    visual: str
    kind: str
    author: str = ""
    start: float = 0.0
    end: float = 0.0


@dataclass
class Film:
    beats: list[Beat]
    words: list[dict]
    aspect: str
    title: str
    music: bool = True
    width: int = 1080
    height: int = 1920


def _kind_and_visual(spoken: str, hint: str) -> tuple[str, str, str]:
    hint = " ".join(hint.split())
    author = ""
    if hint[:1] in "—–-" or hint.lower().startswith("quote"):
        author = hint.lstrip("—–- ").strip()
        return "quote", spoken, author
    quote_match = re.search(r"[\"“](.+?)[\"”]\s*(?:—|--|-)?\s*(.*)$", spoken)
    dash = re.split(r"\s+[—–]\s+|\s+--\s+", spoken, maxsplit=1)
    if hint.lower().startswith("quote") or spoken.strip()[:1] in "\"“" or (len(dash) == 2 and len(dash[1]) < 48):
        author = dash[1].strip(" .") if len(dash) == 2 else ""
        if quote_match and quote_match.group(2).strip():
            author = quote_match.group(2).strip(" .")
        visual = hint if hint and not hint.lower().startswith("quote") else spoken
        return "quote", visual, author
    if hint:
        if re.fullmatch(r"[\d,.]+", hint.replace(" ", "")):
            return "number", hint, ""
        if hint.endswith("?"):
            return "question", hint, ""
        return "words", hint, ""
    number = re.search(r"\b\d[\d,]*\b", spoken)
    if number and len(spoken.split()) <= 16:
        return "number", number.group(0), ""
    if spoken.strip().endswith("?"):
        return "question", spoken.strip(), ""
    words = [w.strip(".,!?;:\"'") for w in spoken.split()]
    content = [w for w in words if w.lower() not in _STOP and w]
    picked = content[:4] or words[:4]
    return "words", " ".join(picked), ""


def parse_script(text: str) -> list[tuple[str, str, str]]:
    """Return spoken line, visual hint, and raw kind marker.

    One line is one beat. A ``|`` splits the spoken words from the literal picture.
    A line that starts with # is a chapter title.
    """
    rows: list[tuple[str, str, str]] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                rows.append((title, title, "chapter"))
            continue
        if "|" in line:
            spoken, hint = line.split("|", 1)
        else:
            spoken, hint = line, ""
        spoken = " ".join(spoken.split())
        hint = " ".join(hint.split())
        if spoken:
            rows.append((spoken, hint, ""))
    if rows:
        return rows
    # One block of prose: split into sentences.
    blob = " ".join(text.split())
    parts = re.split(r"(?<=[.!?])\s+", blob)
    return [(" ".join(part.split()), "", "") for part in parts if part.strip()]


def _words_from_span(spoken: str, start: float, end: float) -> list[dict]:
    parts = spoken.split()
    if not parts:
        return []
    weights = [max(1, len(part)) for part in parts]
    total = float(sum(weights))
    span = max(0.24, end - start)
    cursor = start
    words = []
    for part, weight in zip(parts, weights):
        dur = span * weight / total
        words.append({"text": part, "start": cursor, "end": cursor + dur * 0.92})
        cursor += dur
    return words


def build_film(
    text: str,
    words: list[dict] | None,
    line_times: list[dict] | None,
    aspect: str,
    title: str,
    music: bool,
) -> Film:
    rows = parse_script(text)
    if not rows and words:
        # A recording with no script: one beat per short run of words.
        chunk: list[dict] = []
        rows_from_audio: list[tuple[str, str, str]] = []
        beats: list[Beat] = []
        made: list[dict] = []
        for word in words:
            chunk.append(word)
            if len(chunk) >= 8 or str(word["text"]).endswith((".", "?", "!")):
                spoken = " ".join(item["text"] for item in chunk)
                kind, visual, author = _kind_and_visual(spoken, "")
                beats.append(Beat(spoken, visual, kind, author, float(chunk[0]["start"]), float(chunk[-1]["end"])))
                made.extend(chunk)
                chunk = []
        if chunk:
            spoken = " ".join(item["text"] for item in chunk)
            kind, visual, author = _kind_and_visual(spoken, "")
            beats.append(Beat(spoken, visual, kind, author, float(chunk[0]["start"]), float(chunk[-1]["end"])))
        width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
        cover = title.strip() or (beats[0].visual if beats else "ONE IDEA")
        return Film(beats, words or [], aspect, cover, music, width, height)

    spoken_lines = [row[0] for row in rows]
    use_whisper = bool(words) and len(words) >= max(4, int(0.55 * sum(len(line.split()) for line in spoken_lines)))
    beats: list[Beat] = []
    timed_words: list[dict] = []
    if use_whisper and words is not None:
        cursor = 0
        for spoken, hint, marker in rows:
            tokens = spoken.split()
            if cursor >= len(words):
                start = float(words[-1]["end"])
                end = start + 0.4
                slice_words: list[dict] = []
            else:
                start = float(words[cursor]["start"])
                take = words[cursor : cursor + max(1, len(tokens))]
                cursor += max(1, len(tokens))
                end = float(take[-1]["end"])
                slice_words = take
            kind, visual, author = ("chapter", hint or spoken, "") if marker == "chapter" else _kind_and_visual(spoken, hint)
            if marker == "chapter":
                visual = spoken
            beats.append(Beat(spoken, visual, kind, author, start, end))
            timed_words.extend(slice_words)
        timed_words = words
    elif line_times and len(line_times) == len(rows):
        for (spoken, hint, marker), timing in zip(rows, line_times):
            kind, visual, author = ("chapter", spoken, "") if marker == "chapter" else _kind_and_visual(spoken, hint)
            start = float(timing["start"])
            end = float(timing["end"])
            beats.append(Beat(spoken, visual, kind, author, start, end))
            timed_words.extend(_words_from_span(spoken, start, end))
    else:
        # Even spread. Used only when there is no timing yet.
        cursor = 0.1
        for spoken, hint, marker in rows:
            kind, visual, author = ("chapter", spoken, "") if marker == "chapter" else _kind_and_visual(spoken, hint)
            dur = max(1.6, 0.42 * max(1, len(spoken.split())))
            beats.append(Beat(spoken, visual, kind, author, cursor, cursor + dur))
            timed_words.extend(_words_from_span(spoken, cursor, cursor + dur))
            cursor += dur + 0.12
    if beats:
        beats[0].kind = "hook" if beats[0].kind == "words" else beats[0].kind
    width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    cover = title.strip() or (beats[0].visual if beats else "ONE IDEA")
    return Film(beats, timed_words, aspect, cover, music, width, height)


class _Fonts:
    def __init__(self) -> None:
        self.paths = {
            "bold": str(font_file("bold")),
            "regular": str(font_file("regular")),
            "mono": str(font_file("mono")),
        }
        serif = FONT_DIR / "InstrumentSerif-Italic.ttf"
        self.paths["serif"] = str(serif if serif.is_file() else font_file("regular"))
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def font(self, size: int, kind: str) -> ImageFont.FreeTypeFont:
        key = (kind, int(size))
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(self.paths[kind], int(size))
        return self._cache[key]

    def width(self, text: str, size: int, kind: str) -> float:
        return float(self.font(size, kind).getlength(text or ""))


def _ease(amount: float) -> float:
    amount = max(0.0, min(1.0, amount))
    return 1 - (1 - amount) ** 3


def _wrap(fonts: _Fonts, text: str, size: int, kind: str, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        if current and fonts.width(trial, size, kind) > max_w:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def _draw_centered(draw: ImageDraw.ImageDraw, fonts: _Fonts, lines: list[str], cx: int, y: int, size: int, fill, kind: str, gap: int) -> int:
    for line in lines:
        width = fonts.width(line, size, kind)
        draw.text((cx - width / 2, y), line, font=fonts.font(size, kind), fill=fill)
        y += size + gap
    return y


def _stars(width: int, height: int) -> list[tuple[float, float, int, float]]:
    rng = random.Random(7 + width)
    return [
        (rng.uniform(24, width - 24), rng.uniform(24, height - 24), rng.choice([1, 1, 2]), rng.uniform(0, 6.28))
        for _ in range(56)
    ]


_STAR_CACHE: dict[tuple[int, int], list[tuple[float, float, int, float]]] = {}


def _paint_stars(draw: ImageDraw.ImageDraw, t: float, width: int, height: int) -> None:
    key = (width, height)
    if key not in _STAR_CACHE:
        _STAR_CACHE[key] = _stars(width, height)
    for x, y, size, phase in _STAR_CACHE[key]:
        level = int(46 + 28 * (0.5 + 0.5 * math.sin(t * 1.4 + phase)))
        shade = (level, level, level)
        draw.ellipse((x - size, y - size, x + size, y + size), fill=shade)


def _active_beat(beats: list[Beat], t: float) -> Beat | None:
    if not beats:
        return None
    current = beats[0]
    for beat in beats:
        if t < beat.start:
            return current
        current = beat
    return current


def _caption(draw, fonts: _Fonts, words: list[dict], t: float, width: int, y: int) -> None:
    if not words or t < float(words[0]["start"]) - 0.05:
        return
    if t > float(words[-1]["end"]) + 0.35:
        return
    current = 0
    for index, word in enumerate(words):
        if t + 0.02 >= float(word["start"]):
            current = index
        else:
            break
    group = words[max(0, current - 2) : current + 2]
    size = 54 if width < 1400 else 42
    pieces = []
    total = 0.0
    space = fonts.width(" ", size, "bold")
    for word in group:
        label = str(word["text"]).upper()
        box = fonts.width(label, size, "bold")
        pieces.append((label, box, word))
        total += box
    total += space * (len(pieces) - 1)
    if total > width - 80 and total > 0:
        size = max(28, int(size * (width - 80) / total))
        space = fonts.width(" ", size, "bold")
        pieces = [(label, fonts.width(label, size, "bold"), word) for label, _, word in pieces]
        total = sum(item[1] for item in pieces) + space * (len(pieces) - 1)
    x = (width - total) / 2
    for label, box, word in pieces:
        active = float(word["start"]) - 0.04 <= t < float(word["end"]) + 0.12
        fill = GOLD if active else WHITE
        if active and re.search(r"\d", label):
            fill = RED
        draw.text((x, y), label, font=fonts.font(size, "bold"), fill=fill)
        x += box + space


def _beat_art(draw, fonts: _Fonts, beat: Beat, t: float, width: int, height: int) -> None:
    local = max(0.0, t - beat.start)
    shown = _ease(min(1.0, local / 0.28)) if local < 0.28 else 1.0
    # The first moment of the video is already a full picture, not a blank frame.
    if beat.start < 0.2:
        shown = 1.0
    cx = width // 2
    top = 150 if height > 1400 else 78
    max_w = width - 120
    label = beat.visual if beat.kind != "quote" else (beat.author or "A STOIC LINE")
    label = " ".join(label.split())[:42]
    if shown > 0:
        lw = fonts.width(label.upper(), 22, "mono")
        draw.text((cx - lw / 2, top), label.upper(), font=fonts.font(22, "mono"), fill=GREY)
        rule = int((width * 0.18) * min(1.0, local / 0.45))
        draw.line((cx - rule, top + 40, cx + rule, top + 40), fill=GOLD, width=3)
    y = int(height * (0.30 if height > 1400 else 0.24))
    if beat.kind == "number":
        token = re.search(r"\d[\d,]*", beat.visual) or re.search(r"\d[\d,]*", beat.spoken)
        number = token.group(0) if token else beat.visual
        size = 220 if height > 1400 else 160
        _draw_centered(draw, fonts, [number], cx, y, size, GOLD, "bold", 10)
    elif beat.kind == "quote":
        size = 48 if height > 1400 else 36
        lines = _wrap(fonts, beat.spoken.strip(" \"“”"), size, "serif", max_w)
        while len(lines) > 8 and size > 28:
            size -= 2
            lines = _wrap(fonts, beat.spoken.strip(" \"“”"), size, "serif", max_w)
        draw.text((80, y - 70), "“", font=fonts.font(90, "serif"), fill=GOLD)
        _draw_centered(draw, fonts, lines, cx, y, size, WHITE, "serif", 12)
        if beat.author:
            _draw_centered(draw, fonts, ["— " + beat.author.upper()], cx, y + (size + 12) * len(lines) + 16, 26, GREY, "mono", 8)
    elif beat.kind == "question":
        size = 64 if height > 1400 else 48
        lines = _wrap(fonts, beat.visual, size, "bold", max_w)
        _draw_centered(draw, fonts, lines, cx, y, size, WHITE, "bold", 12)
    elif beat.kind == "chapter":
        _draw_centered(draw, fonts, ["CHAPTER"], cx, y, 28, GOLD, "mono", 10)
        lines = _wrap(fonts, beat.spoken.upper(), 64 if height > 1400 else 48, "bold", max_w)
        _draw_centered(draw, fonts, lines, cx, y + 70, 64 if height > 1400 else 48, WHITE, "bold", 10)
    else:
        size = 86 if height > 1400 else 64
        lines = _wrap(fonts, beat.visual.upper(), size, "bold", max_w)
        while len(lines) > 4 and size > 36:
            size -= 4
            lines = _wrap(fonts, beat.visual.upper(), size, "bold", max_w)
        _draw_centered(draw, fonts, lines, cx, y + 40, size, WHITE, "bold", 8)
        if beat.kind == "hook":
            under = _wrap(fonts, beat.spoken, 32, "regular", max_w)
            _draw_centered(draw, fonts, under[:3], cx, y + 40 + (size + 8) * len(lines) + 24, 32, GREY, "regular", 8)


def _outro(draw, fonts: _Fonts, t: float, width: int, height: int) -> None:
    """Particle mark, then the channel name. One soft ending, no extra logos elsewhere."""
    rng = random.Random(11)
    grow = _ease(min(1.0, t / 1.6))
    cx, cy = width / 2, height * 0.42
    for _ in range(80):
        x0 = rng.uniform(30, width - 30)
        y0 = rng.uniform(80, height - 80)
        x1 = cx + rng.uniform(-220, 220)
        y1 = cy + rng.uniform(-30, 30)
        x = x0 + (x1 - x0) * grow
        y = y0 + (y1 - y0) * grow
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=GOLD if rng.random() > 0.75 else WHITE)
    if t > 1.15:
        _draw_centered(draw, fonts, ["MIND OVER WORLD"], int(cx), int(cy) - 20, 54 if width < 1400 else 64, WHITE, "bold", 8)
        _draw_centered(draw, fonts, ["SUBSCRIBE"], int(cx), int(cy) + 70, 32, GOLD, "mono", 8)


def render_frame(film: Film, t: float, speech_end: float, fonts: _Fonts, footage: Image.Image | None = None) -> Image.Image:
    image = Image.new("RGB", (film.width, film.height), BLACK)
    if footage is not None:
        frame = footage.resize((film.width, film.height), Image.Resampling.BILINEAR)
        darkened = Image.fromarray((np.asarray(frame) * 0.22).astype(np.uint8))
        image.paste(darkened, (0, 0))
    draw = ImageDraw.Draw(image)
    _paint_stars(draw, t, film.width, film.height)
    if t >= speech_end:
        _outro(draw, fonts, t - speech_end, film.width, film.height)
    else:
        beat = _active_beat(film.beats, t)
        if beat is not None:
            _beat_art(draw, fonts, beat, t, film.width, film.height)
        cap_y = int(film.height * 0.78)
        _caption(draw, fonts, film.words, t, film.width, cap_y)
    return image


def draw_cover(title: str, aspect: str) -> Image.Image:
    width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    image = Image.new("RGB", (width, height), BLACK)
    draw = ImageDraw.Draw(image)
    fonts = _Fonts()
    words = [part for part in title.replace("|", " ").split() if part][:4]
    if not words:
        words = ["ONE", "IDEA"]
    label = " ".join(words).upper()
    _draw_centered(draw, fonts, ["MIND OVER WORLD"], width // 2, int(height * 0.18), 28, GREY, "mono", 8)
    size = 120 if height > 1400 else 96
    lines = _wrap(fonts, label, size, "bold", width - 140)
    while len(lines) > 4 and size > 48:
        size -= 6
        lines = _wrap(fonts, label, size, "bold", width - 140)
    _draw_centered(draw, fonts, lines, width // 2, int(height * 0.36), size, WHITE, "bold", 12)
    if lines:
        last_w = fonts.width(lines[-1], size, "bold")
        y = int(height * 0.36) + (size + 12) * len(lines) + 8
        draw.line((width / 2 - last_w / 2, y, width / 2 + last_w / 2, y), fill=GOLD, width=6)
    return image


def write_upload(path: Path, title: str, script: str, aspect: str, beats: list[Beat]) -> None:
    spoken = [beat.spoken for beat in beats if beat.kind != "chapter"]
    headline = " ".join(title.split())
    if not headline and spoken:
        headline = " ".join(spoken[0].split()[:8])
    if aspect == "9:16" and "short" not in headline.lower():
        if len(headline) + 8 <= 70:
            headline = headline.rstrip(".") + " #shorts"
    question = next((beat.spoken for beat in beats if beat.spoken.strip().endswith("?")), "What will you try today?")
    tags = [
        "stoicism",
        "philosophy",
        "mindset",
        "self improvement",
        "mind over world",
        "marcus aurelius",
        "seneca",
        "overthinking",
        "shorts" if aspect == "9:16" else "philosophy video",
    ]
    lines = [
        "TITLE",
        headline[:100],
        "",
        "DESCRIPTION",
        " ".join(spoken[:3]),
        "",
        "One idea, said in plain words.",
        "",
        "Mind Over World",
        "",
        "TAGS",
        ", ".join(tags),
        "",
        "PINNED COMMENT",
        question if question.endswith("?") else question + "?",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def mix_voice(speech: np.ndarray, sr: int, outro: float, music: bool) -> np.ndarray:
    """Voice from the first moment. One soft swell when music is on. No whoosh."""
    speech = np.asarray(speech, dtype=np.float32)
    edge = min(len(speech) // 2, int(0.012 * sr))
    if edge > 1:
        speech = speech.copy()
        speech[:edge] *= np.linspace(0, 1, edge, dtype=np.float32)
        speech[-edge:] *= np.linspace(1, 0, edge, dtype=np.float32)
    total = len(speech) + int(round(outro * sr))
    voice = np.zeros(total, dtype=np.float32)
    voice[: len(speech)] = speech
    if music:
        bed = make_bed(total, sr, voice)
        clock = np.arange(total, dtype=np.float64) / sr
        center = (total / sr) * 0.62
        swell = np.exp(-0.5 * ((clock - center) / 1.35) ** 2)
        tone = (0.03 * swell * np.sin(2 * np.pi * 82.0 * clock)).astype(np.float32)
        stereo = bed.copy()
        stereo[:, 0] += voice + tone
        stereo[:, 1] += voice + tone
    else:
        stereo = np.stack([voice, voice], axis=1)
    peak = float(np.max(np.abs(stereo))) if len(stereo) else 0.0
    if peak > 0.98:
        stereo *= 0.98 / peak
    return stereo.astype(np.float32)


def render_mow(
    film: Film,
    audio: Path,
    out: Path,
    work: Path,
    footage: Path | None = None,
    progress=None,
) -> dict:
    def poke(frac: float, message: str) -> None:
        if progress:
            progress(frac, message)

    work.mkdir(parents=True, exist_ok=True)
    poke(0.04, "Reading the voice...")
    speech = load_mono(audio, work / "speech.wav", SR)
    if speech.size == 0 or float(np.max(np.abs(speech))) < 1e-4:
        raise RuntimeError("This voice file is silent.")
    speech_end = max((beat.end for beat in film.beats), default=len(speech) / SR)
    speech_end = max(speech_end, len(speech) / SR)
    n_frames = max(1, int(round((speech_end + OUTRO) * FPS)))
    duration = n_frames / FPS
    poke(0.1, "Adding quiet music..." if film.music else "Setting the loudness...")
    mix = mix_voice(speech, SR, OUTRO, film.music)
    target = int(round(duration * SR))
    if len(mix) < target:
        mix = np.concatenate([mix, np.zeros((target - len(mix), 2), dtype=np.float32)], axis=0)
    else:
        mix = mix[:target]
    write_wav(work / "mix.wav", mix, SR)
    master(work / "mix.wav", work / "audio_final.m4a", work)

    fonts = _Fonts()
    visual = work / "visual.mp4"
    decoder = None
    if footage is not None and footage.is_file():
        decoder = __import__("subprocess").Popen(
            [
                ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(footage),
                "-vf",
                f"fps={FPS},scale={film.width}:{film.height}:force_original_aspect_ratio=increase,crop={film.width}:{film.height}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").DEVNULL,
        )
    log = open(work / "draw.log", "w", encoding="utf-8")
    encoder = __import__("subprocess").Popen(
        [
            ffmpeg(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{film.width}x{film.height}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "4",
            str(visual),
        ],
        stdin=__import__("subprocess").PIPE,
        stderr=log,
    )
    frame_bytes = film.width * film.height * 3
    last = None
    assert encoder.stdin is not None
    poke(0.22, "Drawing the frames...")
    try:
        for index in range(n_frames):
            t = index / FPS
            shot = None
            if decoder is not None and decoder.stdout is not None:
                raw = decoder.stdout.read(frame_bytes)
                if len(raw) == frame_bytes:
                    last = Image.frombytes("RGB", (film.width, film.height), raw)
                shot = last
            frame = render_frame(film, t, speech_end, fonts, shot)
            if shot is None and frame.getpixel((0, 0)) != BLACK:
                raise RuntimeError("A frame was not on a black background.")
            encoder.stdin.write(frame.tobytes())
            if index % 48 == 0:
                poke(0.22 + 0.5 * (index / n_frames), "Drawing the frames...")
    finally:
        encoder.stdin.close()
        encoder.wait()
        log.close()
        if decoder is not None:
            if decoder.stdout:
                decoder.stdout.close()
            decoder.wait()
    if encoder.returncode:
        raise RuntimeError("Drawing the video failed.")
    poke(0.78, "Saving the MP4...")
    limit = 15_000_000 if film.aspect == "9:16" else 80_000_000
    _encode(visual, work / "audio_final.m4a", out, duration, work, max_bytes=limit)
    poke(0.92, "Checking the video...")
    report = inspect(out, film.width, film.height, max_bytes=limit)
    if not report["ok"]:
        raise RuntimeError("The video did not pass the checks: " + "; ".join(report["issues"]))
    try:
        visual.unlink()
    except OSError:
        pass
    report["music"] = film.music
    report["video"] = str(out)
    return report
