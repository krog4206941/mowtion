"""Speak text with Kokoro, or with the Grandfather Joe F5-TTS clone when it is installed."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf

from mowstudio.paths import MODELS, VOICE_REF_TXT, VOICE_REF_WAV, ensure_dirs

KOKORO_ONNX_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
KOKORO_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
KOKORO_VOICES = {
    "male": "am_michael",
    "female": "af_bella",
}


def joe_ready() -> bool:
    if not VOICE_REF_WAV.is_file() or not VOICE_REF_TXT.is_file():
        return False
    try:
        import f5_tts.api  # noqa: F401
    except Exception:
        return False
    return True


def kokoro_import_ready() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
    except Exception:
        return False
    return True


def kokoro_files() -> tuple[Path, Path]:
    root = MODELS / "kokoro"
    return root / "kokoro-v1.0.onnx", root / "voices-v1.0.bin"


def _download(url: str, dest: Path, progress=None) -> None:
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request

    tmp = dest.with_suffix(dest.suffix + ".part")
    seen = {"step": -1}

    def hook(block, block_size, total):
        if not progress or total <= 0:
            return
        frac = min(0.9, (block * block_size) / total)
        step = int(frac * 20)
        if step == seen["step"]:
            return
        seen["step"] = step
        progress(frac, f"Downloading the fast voice ({dest.name})...")

    urllib.request.urlretrieve(url, tmp, reporthook=hook)
    tmp.replace(dest)


def ensure_kokoro(progress=None) -> tuple[Path, Path]:
    ensure_dirs()
    onnx, voices = kokoro_files()
    _download(KOKORO_ONNX_URL, onnx, progress)
    _download(KOKORO_VOICES_URL, voices, progress)
    return onnx, voices


@lru_cache(maxsize=1)
def _kokoro():
    onnx, voices = ensure_kokoro()
    from kokoro_onnx import Kokoro

    return Kokoro(str(onnx), str(voices))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def speak_kokoro(text: str, dest: Path, voice: str = "male", progress=None) -> Path:
    spoken = " ".join(text.split())
    if not spoken:
        raise ValueError("Type the words you want spoken.")
    if progress:
        progress(0.05, "Loading the fast voice...")
    ensure_kokoro(progress)
    engine = _kokoro()
    name = KOKORO_VOICES.get(voice, KOKORO_VOICES["male"])
    chunks = []
    pieces = _sentences(spoken)
    for index, piece in enumerate(pieces):
        if progress:
            progress(0.15 + 0.7 * (index / max(1, len(pieces))), "Speaking...")
        audio, sr = engine.create(piece, voice=name, speed=1.0, lang="en-us", trim=True)
        audio = np.asarray(audio, dtype=np.float32)
        chunks.append(audio)
        chunks.append(np.zeros(int(sr * 0.18), dtype=np.float32))
        sample_rate = int(sr)
    if not chunks:
        raise RuntimeError("The fast voice did not return any sound.")
    audio = np.concatenate(chunks)
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio / peak * 0.8
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), audio, sample_rate, subtype="PCM_16")
    return dest


def speak_joe(text: str, dest: Path, progress=None) -> Path:
    spoken = " ".join(text.split())
    if not spoken:
        raise ValueError("Type the words you want spoken.")
    if not VOICE_REF_WAV.is_file() or not VOICE_REF_TXT.is_file():
        raise RuntimeError("Grandfather Joe's reference clip is missing from the app folder.")
    if not joe_ready():
        raise RuntimeError("Grandfather Joe's voice is not installed. Use the fast voice. It still works.")
    if progress:
        progress(0.1, "Loading Grandfather Joe. The first time downloads a large model...")
    from f5_tts.api import F5TTS

    ref_text = VOICE_REF_TXT.read_text(encoding="utf-8").strip()
    engine = F5TTS(model="F5TTS_v1_Base", device="cpu")
    if progress:
        progress(0.35, "Speaking in Joe's voice. On a normal PC this is slow...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    engine.infer(
        ref_file=str(VOICE_REF_WAV),
        ref_text=ref_text,
        gen_text=spoken,
        nfe_step=32,
        speed=0.95,
        file_wave=str(dest),
    )
    if not dest.is_file() or dest.stat().st_size < 1000:
        raise RuntimeError("Joe's voice did not make a sound file. Try the fast voice.")
    return dest


def speak(text: str, dest: Path, engine: str = "kokoro", voice: str = "male", progress=None) -> dict:
    """Make a wav. ``engine`` is 'kokoro' or 'joe'. Joe falls back with a clear error, not a crash of the app."""
    choice = (engine or "kokoro").lower()
    if choice == "joe":
        path = speak_joe(text, dest, progress)
        used = "joe"
    else:
        path = speak_kokoro(text, dest, voice=voice, progress=progress)
        used = "kokoro"
    return {"path": str(path), "engine": used}


def ytdlp_version() -> str:
    try:
        import yt_dlp

        return getattr(yt_dlp.version, "__version__", "installed")
    except Exception:
        return "missing"


