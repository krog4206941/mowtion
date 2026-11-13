"""Check a finished MP4 against the delivery rules."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path

from mowstudio.audio import measure_loudness
from mowstudio.media import ffmpeg, probe


def top_level_atoms(path: Path) -> list[str]:
    atoms: list[str] = []
    size = path.stat().st_size
    with path.open("rb") as handle:
        pos = 0
        while pos + 8 <= size:
            handle.seek(pos)
            data = handle.read(8)
            if len(data) < 8:
                break
            length, kind = struct.unpack(">I4s", data)
            if length == 1:
                extra = handle.read(8)
                if len(extra) < 8:
                    break
                length = struct.unpack(">Q", extra)[0]
            if length < 8:
                break
            try:
                atoms.append(kind.decode("ascii"))
            except UnicodeDecodeError:
                atoms.append("????")
            pos += length
    return atoms


def faststart(path: Path) -> bool:
    atoms = top_level_atoms(path)
    if "moov" not in atoms or "mdat" not in atoms:
        return False
    return atoms.index("moov") < atoms.index("mdat")


def corner_rgb(path: Path, t: float = 0.15) -> tuple[int, int, int]:
    raw = subprocess.check_output(
        [
            ffmpeg(),
            "-v",
            "error",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    if len(raw) < 3:
        raise RuntimeError("Could not read a frame from the video.")
    return raw[0], raw[1], raw[2]


def inspect(path: Path, width: int, height: int) -> dict:
    info = probe(path)
    video = next(item for item in info["streams"] if item["codec_type"] == "video")
    audio = next(item for item in info["streams"] if item["codec_type"] == "audio")
    duration = float(info["format"]["duration"])
    size = path.stat().st_size
    loud = measure_loudness(path)
    rgb = corner_rgb(path)
    report = {
        "ok": True,
        "issues": [],
        "width": int(video["width"]),
        "height": int(video["height"]),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "duration": duration,
        "bytes": size,
        "lufs": loud["lufs"],
        "true_peak": loud["true_peak"],
        "faststart": faststart(path),
        "corner_rgb": list(rgb),
    }
    if (report["width"], report["height"]) != (width, height):
        report["issues"].append(f"Size is {report['width']}x{report['height']}, expected {width}x{height}.")
    if report["video_codec"] != "h264":
        report["issues"].append("Video is not H.264.")
    if report["audio_codec"] != "aac":
        report["issues"].append("Audio is not AAC.")
    if size >= 15_000_000:
        report["issues"].append(f"File is {size} bytes. It must be under 15 MB.")
    if not report["faststart"]:
        report["issues"].append("The file is not set for fast start.")
    if abs(loud["lufs"] + 14) > 0.6:
        report["issues"].append(f"Loudness is {loud['lufs']:.2f} LUFS. Target is -14.")
    if loud["true_peak"] > -1.0 + 1e-3:
        report["issues"].append(f"True peak is {loud['true_peak']:.2f} dBTP. Limit is -1.")
    # yuv420 turns exact black into a very dark gray. Navy would push blue higher than red.
    if max(rgb) > 32 or rgb[2] > rgb[0] + 10:
        report["issues"].append(f"Background is not black. Corner color is {rgb}.")
    report["ok"] = not report["issues"]
    return report
