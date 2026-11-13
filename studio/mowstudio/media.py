"""ffmpeg helpers that work on Windows and Linux."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from mowstudio.paths import ROOT


def tool(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    local = ROOT / "tools" / "ffmpeg" / "bin" / exe
    if local.is_file():
        return str(local)
    found = shutil.which(name) or shutil.which(exe)
    if found:
        return found
    raise FileNotFoundError(
        "The video tool is missing. Double-click install.bat again and wait until it says Done."
    )


def ffmpeg() -> str:
    return tool("ffmpeg")


def ffprobe() -> str:
    return tool("ffprobe")


def run(args: list[str], log: Path | None = None) -> str:
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = proc.stdout or ""
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = output.strip()[-1200:]
        raise RuntimeError(tail or "The video tool stopped.")
    return output


def probe(path: Path) -> dict:
    raw = subprocess.check_output(
        [ffprobe(), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        text=True,
    )
    return json.loads(raw)


def streams(info: dict, kind: str) -> list[dict]:
    return [item for item in info.get("streams", []) if item.get("codec_type") == kind]


def duration_of(path: Path) -> float:
    info = probe(path)
    raw = (info.get("format") or {}).get("duration")
    if raw is None:
        raise RuntimeError("Could not read how long this file is.")
    return float(raw)


def has_video(path: Path) -> bool:
    return bool(streams(probe(path), "video"))


def has_audio(path: Path) -> bool:
    return bool(streams(probe(path), "audio"))
