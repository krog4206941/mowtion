"""Checks on a finished file: size, codecs, faststart, loudness."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mowtion.master import measure


def faststart(path: Path) -> bool:
    size = path.stat().st_size
    with path.open("rb") as handle:
        data = handle.read() if size < 30_000_000 else handle.read(8_000_000)
    moov = data.find(b"moov")
    mdat = data.find(b"mdat")
    return moov != -1 and (mdat == -1 or moov < mdat)


def probe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def qc_video(path: Path, *, width: int, height: int, check_loudness: bool = True) -> dict:
    info = probe(path)
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    issues = []
    if video.get("codec_name") != "h264":
        issues.append(f"video codec is {video.get('codec_name')}, expected h264")
    if audio.get("codec_name") not in {"aac", None} and check_loudness:
        issues.append(f"audio codec is {audio.get('codec_name')}, expected aac")
    if int(video.get("width") or 0) != width or int(video.get("height") or 0) != height:
        issues.append(f"frame is {video.get('width')}x{video.get('height')}, expected {width}x{height}")
    if not faststart(path):
        issues.append("moov atom is not at the front of the file (faststart)")
    loudness = None
    if check_loudness and audio:
        loudness = measure(path)
        if loudness["true_peak"] > -1.0 + 0.05:
            issues.append(f"true peak {loudness['true_peak']:.2f} dBTP is above -1")
        if abs(loudness["lufs"] - (-14.0)) > 1.0:
            issues.append(f"integrated loudness {loudness['lufs']:.2f} LUFS is outside -14 ± 1")
    return {
        "ok": not issues,
        "issues": issues,
        "width": video.get("width"),
        "height": video.get("height"),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "duration": float(info.get("format", {}).get("duration") or 0),
        "bytes": path.stat().st_size,
        "faststart": faststart(path),
        "loudness": loudness,
    }
