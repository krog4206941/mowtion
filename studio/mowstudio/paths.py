"""Folders for Clip Studio. Paths stay inside this project."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent
REPO = ROOT.parent
UI_DIR = ROOT / "ui"
ASSETS = ROOT / "assets"
VOICE_REF_WAV = ASSETS / "voice" / "grandfather_joe_ref.wav"
VOICE_REF_TXT = ASSETS / "voice" / "grandfather_joe_ref.txt"
PROMPTS_PATH = ROOT / "PROMPTS.md"
WORK = ROOT / "work"
MODELS = ROOT / "models"
FONT_DIR = REPO / "src" / "mowtion" / "assets" / "fonts"


def ensure_dirs() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HOME", str(MODELS / "hf"))
