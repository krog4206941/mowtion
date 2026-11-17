"""Mix voice with optional quiet music and hit -14 LUFS."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d

from mowstudio.media import ffmpeg, run

SR = 48000
TARGET_LUFS = -14.0
TARGET_TP = -1.0


def load_mono(src: Path, dest: Path, sr: int = SR) -> np.ndarray:
    """Convert any audio or video file to mono float32 samples."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            ffmpeg(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    audio, file_sr = sf.read(str(dest), dtype="float32", always_2d=False)
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if int(file_sr) != sr:
        raise RuntimeError("The audio came out at the wrong sample rate.")
    return np.ascontiguousarray(audio)


def _fade(n: int, sr: int, fade_in: float, fade_out: float) -> np.ndarray:
    curve = np.ones(n, dtype=np.float32)
    a = min(n, int(fade_in * sr))
    b = min(n, int(fade_out * sr))
    if a > 1:
        curve[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b > 1:
        curve[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return curve


def make_bed(n: int, sr: int, voice: np.ndarray) -> np.ndarray:
    """A quiet original pad. Sine tones only. No noise sweeps and no whooshes.

    Returns stereo float32 of length ``n``.
    """
    if n <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    t = np.arange(n, dtype=np.float64) / sr
    duration = n / sr
    bed = np.zeros(n, dtype=np.float64)
    chords = [
        (164.814, 207.652, 246.942, 329.628),
        (138.591, 164.814, 207.652, 277.183),
        (110.0, 138.591, 164.814, 220.0),
        (123.471, 155.563, 184.997, 246.942),
    ]
    for index, start in enumerate(np.arange(0, duration, 8.0)):
        freqs = chords[index % 4]
        local = t - start
        env = np.minimum(np.clip(local / 1.6, 0, 1), np.clip((10.0 - local) / 2.0, 0, 1))
        for partial, hz in enumerate(freqs):
            tone = np.sin(2 * np.pi * hz * local + 0.1 * partial)
            tone += 0.16 * np.sin(2 * np.pi * hz * 2.002 * local + 0.3 * partial)
            bed += 0.04 * env * tone / 4.0
    plucks = [659.255, 739.989, 830.609, 987.767, 830.609, 739.989]
    for index, start in enumerate(np.arange(0.5, duration, 3.0)):
        hz = plucks[index % len(plucks)]
        local = t - start
        env = (local >= 0) * np.exp(-np.maximum(local, 0) * 2.2) * np.minimum(np.maximum(local, 0) * 35, 1)
        bed += 0.015 * env * np.sin(2 * np.pi * hz * local)

    voice = np.asarray(voice, dtype=np.float64)
    if len(voice) != n:
        fitted = np.zeros(n, dtype=np.float64)
        count = min(n, len(voice))
        fitted[:count] = voice[:count]
        voice = fitted
    win = max(1, int(0.05 * sr))
    rms = np.sqrt(uniform_filter1d(voice * voice, win))
    gate = (rms > 0.012).astype(np.float64)
    activity = uniform_filter1d(gate, max(1, int(0.18 * sr)))
    duck = 1.0 - 0.78 * np.clip(activity, 0, 1)
    fade = np.minimum(np.clip(t / 1.1, 0, 1), np.clip((duration - t) / 1.4, 0, 1))
    mono = bed * duck * fade
    delay = int(0.008 * sr)
    right = np.roll(mono, delay)
    if delay > 0:
        right[:delay] = 0
    stereo = np.stack([mono, right], axis=1)
    return np.clip(stereo, -1, 1).astype(np.float32)


def build_timeline(speech: np.ndarray, sr: int, intro: float, outro: float, music: bool) -> np.ndarray:
    """Place speech after the intro. Music is off unless ``music`` is true."""
    speech = np.asarray(speech, dtype=np.float32)
    n_intro = int(round(intro * sr))
    n_outro = int(round(outro * sr))
    n = n_intro + len(speech) + n_outro
    voice = np.zeros(n, dtype=np.float32)
    if len(speech):
        edge = min(len(speech) // 2, int(0.015 * sr))
        if edge > 1:
            speech = speech.copy()
            speech[:edge] *= np.linspace(0, 1, edge, dtype=np.float32)
            speech[-edge:] *= np.linspace(1, 0, edge, dtype=np.float32)
        voice[n_intro : n_intro + len(speech)] = speech
    if music:
        bed = make_bed(n, sr, voice)
    else:
        bed = np.zeros((n, 2), dtype=np.float32)
    stereo = bed.copy()
    stereo[:, 0] += voice
    stereo[:, 1] += voice
    peak = float(np.max(np.abs(stereo))) if len(stereo) else 0.0
    if peak > 0.98:
        stereo *= 0.98 / peak
    return stereo.astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, subtype="PCM_16")


def measure_loudness(path: Path) -> dict:
    """Integrated LUFS and true peak from ffmpeg loudnorm."""
    proc = subprocess_loudnorm(path)
    match = re.findall(r"\{\s*\"input_i\"[\s\S]*?\}", proc)
    if not match:
        raise RuntimeError("Could not measure loudness. The video tool may be incomplete.")
    data = json.loads(match[-1])
    lufs = float(data["input_i"])
    true_peak = float(data["input_tp"])
    if lufs < -70:
        raise RuntimeError("This clip is silent, so it cannot be leveled.")
    return {"lufs": lufs, "true_peak": true_peak}


def subprocess_loudnorm(path: Path) -> str:
    proc = subprocess.run(
        [
            ffmpeg(),
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1:print_format=json",
            "-f",
            "null",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout or ""


def master(mix_wav: Path, m4a: Path, work: Path) -> dict:
    """Level to about -14 LUFS with true peak at or under -1 dBTP.

    The first pass follows the clip pipeline: a light compressor, then loudnorm.
    A short loop trims gain and the limiter until the AAC file hits the target.
    """
    work.mkdir(parents=True, exist_ok=True)
    leveled = work / "audio_master.wav"
    run(
        [
            ffmpeg(),
            "-y",
            "-hide_banner",
            "-i",
            str(mix_wav),
            "-af",
            "acompressor=threshold=0.12:ratio=2.5:attack=8:release=160:makeup=1,loudnorm=I=-14:TP=-2.5:LRA=8",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(leveled),
        ],
        log=work / "normalization.log",
    )
    gain = 0.0
    limit = 0.89
    stats = {"lufs": -99.0, "true_peak": 0.0}
    for attempt in range(6):
        run(
            [
                ffmpeg(),
                "-y",
                "-hide_banner",
                "-i",
                str(leveled),
                "-af",
                f"volume={gain:.4f}dB,alimiter=limit={limit:.5f}:attack=0.1:release=10:level=false:latency=true",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(m4a),
            ]
        )
        stats = measure_loudness(m4a)
        stats["gain_db"] = gain
        stats["limiter"] = limit
        lufs = stats["lufs"]
        true_peak = stats["true_peak"]
        if abs(lufs - TARGET_LUFS) <= 0.4 and true_peak <= TARGET_TP:
            break
        if true_peak > TARGET_TP:
            limit *= 0.94
        # Move toward the target, but do not chase it through the peak ceiling.
        step = TARGET_LUFS - lufs
        if true_peak > TARGET_TP - 0.3 and step > 0:
            step = min(step, 0.3)
        gain += step
        gain = float(np.clip(gain, -12, 12))
    else:
        if stats["true_peak"] > TARGET_TP or abs(stats["lufs"] - TARGET_LUFS) > 1.0:
            raise RuntimeError(
                f"Could not hit the loudness target (got {stats['lufs']:.2f} LUFS, peak {stats['true_peak']:.2f} dBTP)."
            )
    if stats["true_peak"] > TARGET_TP:
        raise RuntimeError(f"The audio peaked at {stats['true_peak']:.2f} dBTP. The limit is -1.")
    (work / "audio_mastering.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats
