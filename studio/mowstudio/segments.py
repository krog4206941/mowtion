"""Pick clip windows and group words into caption lines."""

from __future__ import annotations

from mowstudio.timeutil import format_ts


def group_words(words: list[dict], measure, max_words: int = 6, max_width: float = 1710, gap: float = 0.95) -> list[list[dict]]:
    """Group words the way a caption line should break.

    ``measure`` takes a phrase and returns its width in pixels.
    A line breaks when it is too long, has too many words, a pause is long,
    or a sentence ends.
    """
    groups: list[list[dict]] = []
    current: list[dict] = []

    def phrase(items: list[dict]) -> str:
        return " ".join(item["text"] for item in items)

    for word in words:
        text = (word.get("text") or "").strip()
        if not text:
            continue
        item = {"text": text, "start": float(word["start"]), "end": float(word["end"])}
        if item["end"] < item["start"]:
            item["end"] = item["start"] + 0.04
        if current:
            too_many = len(current) >= max_words
            too_wide = measure(phrase(current + [item])) > max_width
            pause = item["start"] - current[-1]["end"] > gap
            if too_many or too_wide or pause:
                groups.append(current)
                current = []
        current.append(item)
        if item["text"][-1:] in ".?!":
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def slice_words(words: list[dict], start: float, end: float) -> list[dict]:
    """Keep words that overlap [start, end] and shift them so the clip starts at 0."""
    kept: list[dict] = []
    for word in words:
        w_start = float(word["start"])
        w_end = float(word["end"])
        if w_end <= start or w_start >= end:
            continue
        kept.append(
            {
                "text": word["text"],
                "start": round(max(0.0, w_start - start), 3),
                "end": round(max(0.04, min(end, w_end) - start), 3),
            }
        )
    return kept


def format_transcript(words: list[dict]) -> str:
    lines: list[str] = []
    buf: list[str] = []
    line_start: float | None = None
    for word in words:
        text = (word.get("text") or "").strip()
        if not text:
            continue
        if line_start is None:
            line_start = float(word["start"])
        buf.append(text)
        if len(buf) >= 12 or text[-1:] in ".?!":
            lines.append(f"{format_ts(line_start or 0)}  {' '.join(buf)}")
            buf = []
            line_start = None
    if buf:
        lines.append(f"{format_ts(line_start or 0)}  {' '.join(buf)}")
    return "\n".join(lines)


def _preview(words: list[dict], limit: int = 160) -> str:
    text = " ".join(word["text"] for word in words)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def suggest_segments(words: list[dict], low: float = 90, high: float = 120, duration: float | None = None) -> list[dict]:
    """Suggest up to three moments. Short files return the whole clip."""
    clean = [w for w in words if (w.get("text") or "").strip()]
    if not clean:
        return []
    span_end = float(duration if duration is not None else clean[-1]["end"])
    span = span_end - float(clean[0]["start"])
    if span <= high + 8:
        start = 0.0
        end = round(max(float(clean[-1]["end"]), span_end), 2)
        return [
            {
                "start": start,
                "end": end,
                "start_text": format_ts(start),
                "end_text": format_ts(end),
                "label": f"The whole clip ({int(round(end - start))}s)",
                "preview": _preview(clean),
            }
        ]

    starts = [float(clean[0]["start"])]
    for prev, word in zip(clean, clean[1:]):
        if prev["text"][-1:] in ".?!" :
            starts.append(float(word["start"]))
    if len(starts) < 4:
        cursor = float(clean[0]["start"])
        while cursor < span_end - low:
            starts.append(cursor)
            cursor += 15

    scored: list[tuple[float, float, float, str]] = []
    for start in starts:
        if start > span_end - low * 0.85:
            continue
        window = [w for w in clean if start - 0.05 <= float(w["start"]) and float(w["end"]) <= start + high + 0.3]
        if not window:
            continue
        end = None
        for word in window:
            dur = float(word["end"]) - start
            if dur < low:
                continue
            if dur > high:
                break
            if word["text"][-1:] in ".?!":
                end = float(word["end"])
        if end is None:
            inside = [w for w in window if low * 0.9 <= float(w["end"]) - start <= high]
            if not inside:
                continue
            target = start + min(high, 105)
            end = float(min(inside, key=lambda w: abs(float(w["end"]) - target))["end"])
        chunk = [w for w in clean if start <= float(w["start"]) and float(w["end"]) <= end + 0.05]
        if len(chunk) < 8:
            continue
        dur = end - start
        speech = sum(max(0.0, float(w["end"]) - float(w["start"])) for w in chunk)
        gaps = [float(chunk[i + 1]["start"]) - float(chunk[i]["end"]) for i in range(len(chunk) - 1)]
        long_gaps = sum(g for g in gaps if g > 1.2)
        score = speech - long_gaps * 0.8 - abs(dur - 105) * 0.08
        scored.append((score, start, end, _preview(chunk)))

    scored.sort(key=lambda item: item[0], reverse=True)
    picked: list[tuple[float, float, str]] = []
    for _score, start, end, preview in scored:
        overlaps = False
        for old_start, old_end, _preview_text in picked:
            overlap = min(end, old_end) - max(start, old_start)
            if overlap > 35:
                overlaps = True
                break
        if overlaps:
            continue
        picked.append((start, end, preview))
        if len(picked) == 3:
            break

    if not picked:
        end = min(span_end, float(clean[0]["start"]) + high)
        picked.append((float(clean[0]["start"]), end, _preview(clean)))

    results = []
    for index, (start, end, preview) in enumerate(picked, start=1):
        results.append(
            {
                "start": round(start, 2),
                "end": round(end, 2),
                "start_text": format_ts(start),
                "end_text": format_ts(end),
                "label": f"Idea {index} ({int(round(end - start))}s)",
                "preview": preview,
            }
        )
    return results
