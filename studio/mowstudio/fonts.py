"""Find a bold, a regular, and a mono font. Inter is preferred."""

from __future__ import annotations

from pathlib import Path

from mowstudio.paths import FONT_DIR

_CANDIDATES = {
    "bold": [
        FONT_DIR / "Inter-Bold.ttf",
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ],
    "regular": [
        FONT_DIR / "Inter-Regular.ttf",
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ],
    "mono": [
        FONT_DIR / "JetBrainsMono-Regular.ttf",
        Path(r"C:\Windows\Fonts\consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
    ],
}


def font_file(kind: str) -> Path:
    for path in _CANDIDATES[kind]:
        if path.is_file():
            return path
    names = ", ".join(str(path) for path in _CANDIDATES[kind])
    raise FileNotFoundError(
        f"Could not find a {kind} font. Keep the whole project folder. Looked in: {names}"
    )


def fonts_ready() -> bool:
    try:
        font_file("bold")
        font_file("regular")
        font_file("mono")
    except FileNotFoundError:
        return False
    return True
