"""Word-level transcription with faster-whisper.

Input is always rewritten to 16 kHz mono WAV first. compute_type is float32.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


def ffmpeg_to_16k(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        check=True,
    )


def write_16k(audio: np.ndarray, sr: int, dst: Path) -> np.ndarray:
    """Resample ``audio`` to 16 kHz mono and write a WAV. Returns the 16 kHz samples."""
    from scipy.signal import resample_poly

    mono = audio.mean(axis=1) if getattr(audio, "ndim", 1) > 1 else audio
    mono = np.asarray(mono, dtype=np.float32)
    if sr != 16000:
        from math import gcd

        g = gcd(int(sr), 16000)
        mono = resample_poly(mono, 16000 // g, int(sr) // g).astype(np.float32)
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), mono, 16000, subtype="PCM_16")
    return mono


def transcribe_wav(wav_path: Path, model=None) -> list[dict]:
    """Transcribe a 16 kHz WAV. Returns words with start/end in seconds.

    The file is read back from disk (the 16 kHz WAV required before recognition)
    and passed to faster-whisper as samples. That keeps us off PyAV's file
    opener, whose ``metadata_errors`` argument is not in every PyAV build.
    """
    if model is None:
        from mowtion.models import load_whisper

        model = load_whisper()
    audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = np.mean(audio, axis=1)
    audio = np.ascontiguousarray(audio, dtype=np.float32)
    if int(sr) != 16000:
        raise ValueError(f"{wav_path} is {sr} Hz. Convert to 16 kHz WAV first.")
    segments, _info = model.transcribe(
        audio,
        language="en",
        word_timestamps=True,
        beam_size=5,
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    words: list[dict] = []
    for segment in segments:
        for word in segment.words or []:
            text = (word.word or "").strip()
            if not text:
                continue
            start = float(word.start)
            end = float(word.end)
            if end < start:
                end = start + 0.04
            words.append({"text": text, "start": start, "end": end})
    return words


def align_to_script(script_text: str, heard: list[dict]) -> list[dict]:
    """Keep the typed words, borrowing timings from the transcript.

    Whisper is the timing source. If it drops a word, the gap is shared with
    the neighbors so the script still appears on screen.
    """
    import difflib

    script_words = [w for w in script_text.replace("\n", " ").split() if w.strip()]
    if not script_words:
        return heard
    if not heard:
        # Even spacing over a short span. The caller usually has audio.
        step = 0.28
        return [{"text": w, "start": i * step, "end": i * step + 0.22} for i, w in enumerate(script_words)]

    def key(text: str) -> str:
        return "".join(ch.lower() for ch in text if ch.isalnum() or ch == "'")

    heard_keys = [key(w["text"]) for w in heard]
    script_keys = [key(w) for w in script_words]
    matcher = difflib.SequenceMatcher(a=script_keys, b=heard_keys, autojunk=False)
    timed: list[dict | None] = [None] * len(script_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and (i2 - i1) == (j2 - j1)):
            for offset in range(min(i2 - i1, j2 - j1)):
                src = heard[j1 + offset]
                timed[i1 + offset] = {
                    "text": script_words[i1 + offset],
                    "start": src["start"],
                    "end": src["end"],
                }
    # Fill holes by interpolating between known neighbors.
    known = [i for i, item in enumerate(timed) if item is not None]
    if not known:
        span = heard[-1]["end"] - heard[0]["start"]
        step = span / max(1, len(script_words))
        t = heard[0]["start"]
        return [{"text": w, "start": t + i * step, "end": t + (i + 0.85) * step} for i, w in enumerate(script_words)]
    for index, item in enumerate(timed):
        if item is not None:
            continue
        prev_i = max((i for i in known if i < index), default=None)
        next_i = min((i for i in known if i > index), default=None)
        if prev_i is None and next_i is not None:
            anchor = timed[next_i]
            assert anchor is not None
            gap = max(0.18, (anchor["start"] - heard[0]["start"]) / (next_i + 1))
            start = max(0.0, anchor["start"] - gap * (next_i - index))
        elif next_i is None and prev_i is not None:
            anchor = timed[prev_i]
            assert anchor is not None
            start = anchor["end"] + 0.06 + 0.22 * (index - prev_i - 1)
        elif prev_i is not None and next_i is not None:
            left, right = timed[prev_i], timed[next_i]
            assert left is not None and right is not None
            span = right["start"] - left["end"]
            slots = next_i - prev_i
            start = left["end"] + span * (index - prev_i) / slots
        else:
            start = index * 0.28
        timed[index] = {"text": script_words[index], "start": start, "end": start + 0.2}
    return [item for item in timed if item is not None]
