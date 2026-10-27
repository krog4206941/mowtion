"""A small posting pack: title, description, and tags. No network calls."""

from __future__ import annotations

import re

STOP = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "between",
    "could",
    "every",
    "from",
    "have",
    "into",
    "just",
    "more",
    "only",
    "other",
    "should",
    "some",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "under",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
    "yours",
}


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def build_seo(script: str, title: str | None = None, description: str | None = None, tags: list[str] | None = None) -> dict:
    lines = _sentences(script or "")
    auto_title = (lines[0] if lines else "A motion graphics video").strip().rstrip(".")
    if len(auto_title) > 70:
        auto_title = auto_title[:67].rstrip() + "..."
    body = (script or "").strip()
    if len(body) > 280:
        body = body[:277].rstrip() + "..."
    auto_description = (body + "\n\nMade with mowtion.").strip()
    words = re.findall(r"[A-Za-z][A-Za-z']{3,}", script or "")
    counts: dict[str, int] = {}
    for word in words:
        key = word.lower()
        if key in STOP:
            continue
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts, key=lambda w: (-counts[w], w))[:6]
    auto_tags = ranked + ["motion graphics", "mowtion"]
    # Keep order, drop duplicates.
    seen = set()
    clean_tags = []
    for tag in tags or auto_tags:
        item = tag.strip().lstrip("#")
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        clean_tags.append(item)
    return {
        "title": (title or auto_title).strip(),
        "description": (description or auto_description).strip(),
        "tags": clean_tags[:12],
    }
