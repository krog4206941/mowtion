"""Drop filler words and immediate repeats. Dead air is removed when audio is rebuilt."""

from __future__ import annotations

import re

# Spoken fillers. "like" and "so" are real words and are left alone.
FILLERS = {
    "um",
    "uh",
    "uhh",
    "umm",
    "erm",
    "er",
    "ah",
    "ahh",
    "hmm",
    "mm",
    "mmm",
    "mhm",
    "uhhuh",
}

# Two-word fillers, matched in order.
FILLER_PAIRS = (
    ("you", "know"),
    ("i", "mean"),
)


def norm_token(text: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", text.lower())


def cleanup_words(words: list[dict]) -> list[dict]:
    """Return a new word list with fillers and consecutive repeats removed."""
    kept: list[dict] = []
    skip_next = False
    for index, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        token = norm_token(word["text"])
        if not token:
            continue
        if token in FILLERS:
            continue
        if index + 1 < len(words):
            nxt = norm_token(words[index + 1]["text"])
            if (token, nxt) in FILLER_PAIRS:
                skip_next = True
                continue
        if kept and token == norm_token(kept[-1]["text"]):
            continue
        kept.append({"text": word["text"].strip(), "start": float(word["start"]), "end": float(word["end"])})
    return kept
