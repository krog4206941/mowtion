"""Original synth score. Deterministic from a seed, duration, and mood."""

from __future__ import annotations

import math

import numpy as np
from scipy.signal import butter, sosfilt

# MIDI chords. Each mood is a four-bar loop.
MOODS = {
    "minor": [[50, 53, 57, 60], [48, 52, 55, 59], [46, 50, 53, 57], [45, 48, 52, 55]],
    "major": [[65, 69, 72, 76], [64, 67, 69, 72], [62, 65, 69, 72], [62, 65, 69, 70]],
    "warm": [[50, 53, 57, 60], [46, 50, 53, 58], [48, 53, 57, 60], [45, 48, 52, 57]],
    "pulse": [[48, 51, 55, 58], [46, 50, 53, 58], [43, 46, 50, 55], [41, 45, 48, 53]],
    "airy": [[60, 64, 67, 71], [62, 65, 69, 72], [64, 67, 71, 74], [59, 62, 67, 71]],
}


def midi_hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _lowpass(x: np.ndarray, sr: int, freq: float) -> np.ndarray:
    freq = min(freq, sr / 2 - 200)
    sos = butter(2, freq / (sr / 2), btype="low", output="sos")
    return sosfilt(sos, x).astype(np.float32)


def _highpass(x: np.ndarray, sr: int, freq: float) -> np.ndarray:
    sos = butter(2, freq / (sr / 2), btype="high", output="sos")
    return sosfilt(sos, x).astype(np.float32)


def _add(left: np.ndarray, right: np.ndarray, sig: np.ndarray, t0: float, sr: int, gain: float, pan: float = 0.0):
    if len(sig) == 0 or gain == 0:
        return
    i = int(t0 * sr)
    if i >= len(left):
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    n = min(len(sig), len(left) - i)
    if n <= 0:
        return
    s = sig[:n].astype(np.float32) * gain
    left[i : i + n] += s * math.sqrt(0.5 * (1 - pan))
    right[i : i + n] += s * math.sqrt(0.5 * (1 + pan))


def render_score(
    duration: float,
    mood: str = "major",
    bpm: int = 96,
    seed: int = 7,
    sr: int = 48000,
    dips: list[list[float]] | None = None,
) -> np.ndarray:
    """Stereo float32 score of ``duration`` seconds. Peak is left under 0.6."""
    if duration <= 0.05:
        return np.zeros((1, 2), dtype=np.float32)
    rng = np.random.default_rng(seed)
    n = int(round(duration * sr))
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)
    chords = MOODS.get(mood, MOODS["major"])
    beat = 60.0 / max(40, bpm)
    bar = beat * 4
    brightness = {"minor": 900, "major": 1400, "warm": 1100, "pulse": 1600, "airy": 1800}.get(mood, 1200)

    # Soft pad, one chord per bar, overlapping slightly so it never drops out.
    t = 0.0
    bar_index = 0
    while t < duration:
        notes = chords[bar_index % len(chords)]
        length = int((bar + 0.6) * sr)
        tt = np.arange(length) / sr
        pad = np.zeros(length, dtype=np.float32)
        for note in notes:
            freq = midi_hz(note)
            phase = rng.uniform(0, 0.2)
            pad += np.sin(2 * math.pi * freq * (tt + phase)).astype(np.float32)
            pad += 0.35 * np.sin(2 * math.pi * freq * 2.01 * tt).astype(np.float32)
        env = np.minimum(1, tt / 0.4) * np.clip((bar + 0.6 - tt) / 0.5, 0, 1)
        pad = _lowpass(pad * env.astype(np.float32), sr, brightness) / max(1, len(notes))
        _add(left, right, pad, t, sr, 0.07, pan=0.0)
        t += bar
        bar_index += 1

    # Sparse felt notes on the beat, and a quieter answer on the off-beat.
    steps = int(duration / beat)
    for k in range(steps):
        t = k * beat
        if t > duration - 0.2:
            break
        chord = chords[int(t / bar) % len(chords)]
        note = chord[k % len(chord)] + 12
        dur = beat * 1.6
        nn = int(dur * sr)
        tt = np.arange(nn) / sr
        tone = np.sin(2 * math.pi * midi_hz(note) * tt).astype(np.float32)
        tone += 0.25 * np.sin(2 * math.pi * midi_hz(note) * 2 * tt).astype(np.float32)
        tone *= np.exp(-tt * 3.2).astype(np.float32)
        tone *= np.minimum(1, tt / 0.008).astype(np.float32)
        gain = 0.09 if k % 2 == 0 else 0.035
        _add(left, right, tone, t, sr, gain, pan=0.25 if k % 2 else -0.2)

    # Quiet pulse on beats 1 and 3. Low, short, never a hit.
    for k in range(steps):
        if k % 2:
            continue
        t = k * beat
        nn = int(0.28 * sr)
        tt = np.arange(nn) / sr
        freq = 52 + 70 * np.exp(-tt * 22)
        kick = np.sin(2 * math.pi * np.cumsum(freq) / sr).astype(np.float32)
        kick *= np.exp(-tt * 10).astype(np.float32)
        _add(left, right, kick, t, sr, 0.18, pan=0.0)

    # Very quiet ticks so the grid has something to breathe with.
    tick_n = int(0.02 * sr)
    noise = rng.standard_normal(tick_n).astype(np.float32)
    tick = _highpass(noise, sr, 5000) * np.exp(-np.arange(tick_n) / sr * 220).astype(np.float32)
    for k in range(steps):
        t = k * beat + beat / 2
        if t >= duration:
            break
        _add(left, right, tick, t, sr, 0.025, pan=0.4 if k % 2 else -0.4)

    # A small swell through each breath so the dip has a shape when it returns.
    for start, end in dips or []:
        dur = max(0.3, end - start)
        nn = int(dur * sr)
        tt = np.arange(nn) / sr
        noise = rng.standard_normal(nn).astype(np.float32)
        swell = _lowpass(_highpass(noise, sr, 400), sr, 2500)
        swell *= (tt / dur).astype(np.float32) ** 2
        _add(left, right, swell, start, sr, 0.04, pan=0.0)

    stereo = np.stack([left, right], axis=1)
    stereo = _highpass(stereo.T, sr, 28).T
    fade = np.ones(n, dtype=np.float32)
    fin = min(n, int(0.05 * sr))
    fade[:fin] *= np.linspace(0, 1, fin, dtype=np.float32)
    fout = min(n, int(0.9 * sr))
    if fout > 1:
        fade[-fout:] *= np.linspace(1, 0, fout, dtype=np.float32) ** 1.2
    stereo *= fade[:, None]
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if peak > 1e-6:
        stereo *= 0.55 / peak
    return stereo.astype(np.float32)


def duck_gain(voice: np.ndarray, sr: int, dips: list[list[float]] | None = None, pause_dip: float = 0.4) -> np.ndarray:
    """Gain curve for the score: down under the voice, and lower still in breaths."""
    n = len(voice)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    dec = 48
    abs_v = np.abs(voice.astype(np.float32))
    kernel = np.ones(dec, dtype=np.float32) / dec
    smooth = np.convolve(abs_v, kernel, mode="same")[::dec]
    attack = math.exp(-dec / (0.05 * sr))
    release = math.exp(-dec / (0.45 * sr))
    out = np.empty_like(smooth)
    y = 0.0
    for i, value in enumerate(smooth):
        coef = attack if value > y else release
        y = coef * y + (1 - coef) * float(value)
        out[i] = y
    env = np.repeat(out, dec)[:n]
    ref = float(np.percentile(env, 95)) if np.any(env > 1e-5) else 1.0
    env = np.clip(env / max(ref, 1e-6), 0, 1)
    gain = 1 - 0.78 * env
    if dips:
        t = np.arange(n) / sr
        for start, end in dips:
            mask = (t >= start) & (t < end + 0.05)
            if not np.any(mask):
                continue
            local = t[mask]
            # Ease down, hold, ease back. ``pause_dip`` is the floor (0.4 = 40%).
            curve = np.interp(
                local,
                [start, start + 0.18, end - 0.12, end + 0.05],
                [1.0, pause_dip, pause_dip, 1.0],
            )
            gain[mask] *= curve.astype(np.float32)
    return gain.astype(np.float32)


def mix_voice_music(
    voice: np.ndarray,
    music: np.ndarray,
    sr: int,
    dips: list[list[float]] | None = None,
    pause_dip: float = 0.4,
) -> np.ndarray:
    """Stereo mix. Voice is centered. Music ducks, and dips before key lines."""
    n = max(len(voice), len(music))
    if len(voice) < n:
        voice = np.pad(voice, (0, n - len(voice)))
    if len(music) < n:
        music = np.pad(music, ((0, n - len(music)), (0, 0)))
    voice = voice[:n].astype(np.float32)
    music = music[:n].astype(np.float32)
    gain = duck_gain(voice, sr, dips, pause_dip)
    ducked = music * gain[:, None]
    vocal = np.stack([voice, voice], axis=1) * 0.9
    mix = vocal + ducked * 0.85
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix.astype(np.float32)
