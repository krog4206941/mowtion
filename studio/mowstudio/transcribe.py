"""Word-level transcription with faster-whisper on the CPU."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from mowstudio.media import ffmpeg, run
from mowstudio.paths import MODELS, ensure_dirs

MODEL_NAME = "small.en"
COMPUTE_TYPES = ("int8", "int8_float32", "float32")
_MODELS: dict[str, object] = {}


def to_16k(src: Path, dest: Path) -> Path:
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
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    return dest


def _model(compute_type: str):
    from faster_whisper import WhisperModel

    ensure_dirs()
    if compute_type in _MODELS:
        return _MODELS[compute_type]
    root = MODELS / "whisper"
    root.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(MODEL_NAME, device="cpu", compute_type=compute_type, download_root=str(root))
    _MODELS[compute_type] = model
    return model


def _words_from(model, samples: np.ndarray) -> list[dict]:
    segments, _info = model.transcribe(
        samples,
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
            words.append({"text": text, "start": round(start, 3), "end": round(end, 3)})
    return words


def transcribe(src: Path, work: Path, progress=None) -> list[dict]:
    """Transcribe speech to words with start and end times.

    Uses small.en in int8 (CPU friendly). If that returns no words, it retries
    a more careful setting.
    """
    if progress:
        progress(0.02, "Getting the sound ready...")
    wav = to_16k(src, work / "speech16.wav")
    audio, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    if int(sr) != 16000:
        raise RuntimeError("Could not convert the audio to 16 kHz.")
    samples = np.ascontiguousarray(audio, dtype=np.float32)
    if samples.size == 0:
        raise RuntimeError("This file has no sound.")
    last_error = None
    for index, compute in enumerate(COMPUTE_TYPES):
        if progress:
            progress(0.1 + index * 0.2, "Reading the words. A long video takes a while. Leave this window open.")
        try:
            words = _words_from(_model(compute), samples)
        except Exception as exc:
            last_error = exc
            continue
        if words:
            return words
    if last_error:
        raise RuntimeError(f"Could not read the words. {last_error}")
    raise RuntimeError("No words were found. Check that the clip has clear speech.")
