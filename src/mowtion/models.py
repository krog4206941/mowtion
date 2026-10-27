"""Download Kokoro the first time it is needed. Models are not committed."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from mowtion.paths import models_dir

KOKORO_ONNX_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
)
WHISPER_MODEL = "small.en"


def kokoro_paths() -> tuple[Path, Path]:
    root = models_dir()
    return root / "kokoro-v1.0.onnx", root / "voices-v1.0.bin"


def _download(url: str, dest: Path, progress=None) -> None:
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def hook(block, block_size, total):
        if progress and total > 0:
            frac = min(1.0, (block * block_size) / total)
            progress(frac, f"Downloading {dest.name}")

    urllib.request.urlretrieve(url, tmp, reporthook=hook)
    tmp.replace(dest)


def ensure_kokoro(progress=None) -> tuple[Path, Path]:
    onnx, voices = kokoro_paths()
    _download(KOKORO_ONNX_URL, onnx, progress)
    _download(KOKORO_VOICES_URL, voices, progress)
    return onnx, voices


def load_kokoro(progress=None):
    onnx, voices = ensure_kokoro(progress)
    from kokoro_onnx import Kokoro

    return Kokoro(str(onnx), str(voices))


def load_whisper(progress=None):
    if progress:
        progress(0.0, "Loading the transcription model")
    from faster_whisper import WhisperModel

    root = models_dir() / "whisper"
    root.mkdir(parents=True, exist_ok=True)
    # float32: int8 dropped words in our tests. The 16 kHz WAV is passed in.
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32", download_root=str(root))
    return model
