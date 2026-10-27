"""Cache and output locations."""

from __future__ import annotations

import os
from pathlib import Path


def cache_dir() -> Path:
    override = os.environ.get("MOWTION_CACHE")
    path = Path(override) if override else Path.home() / ".cache" / "mowtion"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = cache_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path
