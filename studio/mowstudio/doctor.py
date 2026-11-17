"""Check that Clip Studio can start. Joe's voice is optional."""

from __future__ import annotations

from mowstudio import __version__
from mowstudio.fonts import fonts_ready
from mowstudio.transcribe import MODEL_NAME
from mowstudio.voice import joe_ready, kokoro_import_ready, ytdlp_version


def checks() -> list[tuple[str, bool, str, bool]]:
    """Return label, ok, detail, required."""
    rows: list[tuple[str, bool, str, bool]] = []
    try:
        from mowstudio.media import ffmpeg, ffprobe

        ffmpeg()
        ffprobe()
        rows.append(("Video tool", True, "ffmpeg and ffprobe", True))
    except Exception as exc:
        rows.append(("Video tool", False, str(exc), True))
    rows.append(("Fonts", fonts_ready(), "Inter and JetBrains Mono, or a system font", True))
    rows.append(("Word reader", _imports("faster_whisper"), f"{MODEL_NAME}, int8, CPU", True))
    rows.append(("Fast voice", kokoro_import_ready(), "Kokoro", True))
    rows.append(("Downloader", ytdlp_version() != "missing", ytdlp_version(), True))
    if joe_ready():
        rows.append(("Grandfather Joe", True, "F5-TTS is installed", False))
    else:
        rows.append(("Grandfather Joe", False, "not installed. The fast voice still works.", False))
    return rows


def _imports(name: str) -> bool:
    try:
        __import__(name)
    except Exception:
        return False
    return True


def run() -> int:
    print(f"Clip Studio {__version__}")
    ok = True
    for label, good, detail, required in checks():
        state = "OK" if good else "MISSING"
        print(f"  {label}: {state}  {detail}")
        if required and not good:
            ok = False
    if ok:
        print("Ready. Double-click start.bat")
        return 0
    print("Something important is missing. Double-click install.bat again.")
    return 1
