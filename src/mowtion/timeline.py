"""Turn word timings into a calm scene list and a tightened voice track."""

from __future__ import annotations

import hashlib
import math
import re

import numpy as np

from mowtion.cleanup import cleanup_words

# About 3–4 seconds on screen, with a short breath before key lines.
PACING = {
    "min_scene_s": 3.4,
    "max_comfort_s": 4.15,
    "breath_s": 0.75,
    "lead_s": 0.4,
    "inner_tail_s": 0.4,
    "max_gap_s": 0.18,
    "min_gap_s": 0.04,
    "outro_s": 0.7,
    "crossfade_s": 0.65,
    "max_line_s": 4.0,
}

KINDS = ("kinetic", "card", "bars", "ring", "line", "abstract")
TRANSITIONS = ("dissolve", "wipe", "iris")


def _hash01(text: str) -> float:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") / 2**32


def group_lines(words: list[dict], max_span: float = PACING["max_line_s"]) -> list[list[dict]]:
    """Group words into lines that can each hold one graphic.

    A sentence, a long pause, or about four seconds of speech starts a new line.
    Short lines are padded later so the graphic still holds for 3–4 seconds.
    """
    lines: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            span_if_added = word["end"] - current[0]["start"]
            if gap > 0.55 or span_if_added > max_span:
                lines.append(current)
                current = []
        current.append(word)
        ended = word["text"][-1:] in ".!?"
        if ended:
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return [line for line in lines if line]


def line_is_key(index: int, words: list[dict], total: int) -> bool:
    if index == 0:
        return False
    text = " ".join(word["text"] for word in words)
    tokens = [re.sub(r"[^A-Za-z0-9']", "", word["text"]) for word in words]
    tokens = [token for token in tokens if token]
    if len(tokens) <= 8:
        return True
    if any(ch.isdigit() for ch in text):
        return True
    if index % 3 == 2:
        return True
    if index == total - 1 and total > 1:
        return True
    return False


def _payload(text: str) -> dict:
    raw = [re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word) for word in text.split()]
    labels = [word for word in raw if len(word) > 2][:4]
    while len(labels) < 4:
        labels.append(("voice", "picture", "music", "export")[len(labels)])
    bars = []
    for index, label in enumerate(labels):
        value = 0.34 + 0.58 * _hash01(f"{index}:{label}:{text}")
        bars.append({"label": label[:12], "value": round(value, 3)})
    numbers = [int(n) for n in re.findall(r"\d+", text) if int(n) <= 100]
    ring = numbers[0] if numbers else int(58 + 34 * _hash01("ring:" + text))
    points = [round(0.2 + 0.7 * _hash01(f"pt:{i}:{text}"), 3) for i in range(8)]
    return {"bars": bars, "ring": ring, "points": points}


def _fade(chunk: np.ndarray, sr: int, fade_s: float = 0.01) -> np.ndarray:
    n = min(len(chunk) // 2, int(fade_s * sr))
    if n <= 1:
        return chunk
    out = chunk.copy()
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def _slice_word(audio: np.ndarray, sr: int, word: dict, prev_end: float | None, next_start: float | None) -> np.ndarray:
    start = word["start"] - 0.03
    end = word["end"] + 0.05
    if prev_end is not None:
        start = max(start, (prev_end + word["start"]) / 2)
    if next_start is not None:
        end = min(end, (word["end"] + next_start) / 2)
    start = max(0.0, start)
    end = min(len(audio) / sr, max(start + 0.04, end))
    a = int(start * sr)
    b = max(a + 1, int(end * sr))
    return _fade(audio[a:b].astype(np.float32), sr)


def _silence(sr: int, seconds: float) -> np.ndarray:
    n = max(0, int(round(seconds * sr)))
    return np.zeros(n, dtype=np.float32)


def plan_timeline(words: list[dict], audio: np.ndarray, sr: int, pacing: dict | None = None) -> dict:
    """Clean words, drop dead air, and build scenes of about 3–4 seconds.

    ``audio`` is mono float32. Word times are seconds into that buffer.
    The returned audio is the tightened voice, and word times are rewritten
    to match it.
    """
    cfg = dict(PACING)
    if pacing:
        cfg.update(pacing)
    cleaned = cleanup_words(words)
    if not cleaned:
        raise ValueError("No words left after cleanup. Try a longer clip or a script.")
    # Keep times monotonic in case a recognizer overlaps words.
    fixed = []
    cursor = 0.0
    for word in cleaned:
        start = max(float(word["start"]), cursor)
        end = max(float(word["end"]), start + 0.04)
        fixed.append({"text": word["text"].strip(), "start": start, "end": end})
        cursor = end
    lines = group_lines(fixed, cfg["max_line_s"])
    pieces: list[np.ndarray] = []
    new_words: list[dict] = []
    scenes: list[dict] = []
    dips: list[list[float]] = []
    clock = 0.0

    for index, line in enumerate(lines):
        key = line_is_key(index, line, len(lines))
        breath = cfg["breath_s"] if key else (cfg["lead_s"] if index == 0 else 0.12)
        pieces.append(_silence(sr, breath))
        scene_t0 = clock
        clock += breath
        speech_t0 = clock
        line_words = []
        for j, word in enumerate(line):
            if j > 0:
                natural = word["start"] - line[j - 1]["end"]
                gap = min(cfg["max_gap_s"], max(cfg["min_gap_s"], natural))
                pieces.append(_silence(sr, gap))
                clock += gap
            prev_end = line[j - 1]["end"] if j else None
            next_start = line[j + 1]["start"] if j + 1 < len(line) else None
            chunk = _slice_word(audio, sr, word, prev_end, next_start)
            pieces.append(chunk)
            dur = len(chunk) / sr
            copied = {"text": word["text"], "start": clock, "end": clock + dur}
            line_words.append(copied)
            new_words.append(copied)
            clock += dur
        speech_t1 = clock
        speech_span = max(0.2, speech_t1 - speech_t0)
        tail = cfg["inner_tail_s"]
        total = breath + speech_span + tail
        if total < cfg["min_scene_s"]:
            tail += cfg["min_scene_s"] - total
            total = breath + speech_span + tail
        elif total > cfg["max_comfort_s"] and speech_span + breath < cfg["max_comfort_s"]:
            tail = max(0.28, cfg["max_comfort_s"] - breath - speech_span)
        pieces.append(_silence(sr, tail))
        clock += tail
        text = " ".join(word["text"] for word in line_words)
        payload = _payload(text)
        scene = {
            "kind": KINDS[index % len(KINDS)],
            "transition": TRANSITIONS[index % len(TRANSITIONS)],
            "t0": round(scene_t0, 4),
            "t1": round(clock, 4),
            "speech_t0": round(speech_t0, 4),
            "speech_t1": round(speech_t1, 4),
            "key": key,
            "breath": round(breath if key else 0.0, 4),
            "words": line_words,
            "title": text,
            **payload,
        }
        scenes.append(scene)
        if key and breath >= 0.5:
            dips.append([round(scene_t0, 4), round(speech_t0, 4)])

    pieces.append(_silence(sr, cfg["outro_s"]))
    duration = clock + cfg["outro_s"]
    voice = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
    # Guard against a sample of rounding drift.
    expect = int(math.ceil(duration * sr))
    if len(voice) < expect:
        voice = np.pad(voice, (0, expect - len(voice)))
    return {
        "audio": voice.astype(np.float32),
        "sample_rate": sr,
        "words": new_words,
        "scenes": scenes,
        "dips": dips,
        "duration": round(duration, 4),
        "pacing": cfg,
    }
