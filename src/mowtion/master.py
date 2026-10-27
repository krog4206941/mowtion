"""Master a stereo mix to -14 LUFS with true peak at or below -1 dBTP."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


def write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="PCM_16")


def measure(path: Path) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP) via ffmpeg ebur128."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    text = proc.stderr or ""
    summary = text.split("Summary:")[-1]
    integrated = None
    true_peak = None
    for line in summary.splitlines():
        if "I:" in line and "LUFS" in line and integrated is None:
            integrated = float(line.split("I:")[1].split("LUFS")[0].strip())
        if "Peak:" in line and "dB" in line and true_peak is None:
            match = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)", line)
            if match:
                true_peak = float(match.group(1))
    if integrated is None or true_peak is None:
        raise RuntimeError("Could not read loudness from ffmpeg. Is this build of ffmpeg complete?")
    return {"lufs": integrated, "true_peak": true_peak}


def _loudnorm_json(path: Path, lufs: float, true_peak: float) -> dict:
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            f"loudnorm=I={lufs}:TP={true_peak}:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    raw = proc.stderr
    start = raw.rfind("{")
    end = raw.rfind("}")
    if start < 0 or end < 0:
        raise RuntimeError("loudnorm did not return a measurement")
    return json.loads(raw[start : end + 1])


def _apply_gain(src: Path, dst: Path, gain_db: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-af",
            f"volume={gain_db:.3f}dB",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        check=True,
    )


def master(src: Path, dst: Path, lufs: float = -14.0, true_peak: float = -1.0) -> dict:
    """Two-pass loudnorm, then a trim so the true peak stays at or under the limit.

    If the peak limit and the loudness target disagree, the peak wins and the
    result sits as close to the target as that allows.
    """
    measured = _loudnorm_json(src, lufs, min(true_peak, -1.5))
    af = (
        f"loudnorm=I={lufs}:TP={min(true_peak, -1.5)}:LRA=11:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true"
    )
    first = dst.with_name(dst.stem + ".pass1.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-af",
            af,
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(first),
        ],
        check=True,
    )
    stats = measure(first)
    # Positive gain turns the mix up. Never push the true peak past the limit.
    gain = lufs - stats["lufs"]
    max_gain = (true_peak - 0.05) - stats["true_peak"]
    gain = min(gain, max_gain)
    if abs(gain) > 0.15:
        _apply_gain(first, dst, gain)
        stats = measure(dst)
    else:
        first.replace(dst)
    if stats["true_peak"] > true_peak:
        _apply_gain(dst, first, (true_peak - 0.08) - stats["true_peak"])
        first.replace(dst)
        stats = measure(dst)
    if first.exists():
        first.unlink()
    stats["target_lufs"] = lufs
    stats["target_true_peak"] = true_peak
    return stats
