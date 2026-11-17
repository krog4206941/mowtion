"""Saved clip projects live in studio/work/<id>/."""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from mowstudio.paths import WORK, ensure_dirs
from mowstudio.segments import format_transcript

_ID = re.compile(r"^[a-f0-9]{8}$")


def create() -> tuple[str, Path]:
    ensure_dirs()
    pid = secrets.token_hex(4)
    folder = WORK / pid
    folder.mkdir(parents=True)
    return pid, folder


def folder_for(pid: str) -> Path:
    if not _ID.fullmatch(pid or ""):
        raise ValueError("That project was not found. Get the video again.")
    folder = WORK / pid
    if not folder.is_dir() or not (folder / "meta.json").is_file():
        raise ValueError("That project was not found. Get the video again.")
    return folder


def save(folder: Path, meta: dict) -> None:
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load(folder: Path) -> dict:
    return json.loads((folder / "meta.json").read_text(encoding="utf-8"))


def public(meta: dict) -> dict:
    words = meta.get("words") or []
    return {
        "id": meta["id"],
        "title": meta.get("title") or "",
        "channel": meta.get("channel") or "",
        "upload_date": meta.get("upload_date") or "",
        "date_label": meta.get("date_label") or "",
        "url": meta.get("url") or "",
        "duration": meta.get("duration") or 0,
        "has_video": bool(meta.get("has_video")),
        "source_name": meta.get("source_name") or "",
        "transcript": meta.get("transcript") or format_transcript(words),
        "suggestions": meta.get("suggestions") or [],
        "clip": bool(meta.get("clip")),
        "clip_start": meta.get("clip_start"),
        "clip_end": meta.get("clip_end"),
        "voice": bool(meta.get("voice")),
        "voice_engine": meta.get("voice_engine") or "",
        "outputs": [name for name in ("output.mp4", "output_vertical.mp4") if (WORK / meta["id"] / name).is_file()],
    }
