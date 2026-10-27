"""One project.json per video, enough to see how a render was made."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mowtion import __version__


def build_project(
    *,
    script: str | None,
    source_name: str | None,
    preset: str,
    aspect: str,
    width: int,
    height: int,
    fps: int,
    timeline: dict,
    music: dict,
    seo: dict | None,
    voice: dict,
    qc: dict | None = None,
    seed: int = 7,
) -> dict:
    pacing = dict(timeline.get("pacing") or {})
    # The audio buffer itself is not JSON.
    return {
        "mowtion": 1,
        "version": __version__,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title": (seo or {}).get("title") or "",
        "input": {
            "kind": "script" if script else "file",
            "script": script or "",
            "filename": source_name,
        },
        "format": {"aspect": aspect, "w": width, "h": height, "fps": fps},
        "preset": preset,
        "voice": voice,
        "audio": {"lufs": -14.0, "true_peak": -1.0, "pause_dip": 0.4, "sample_rate": 48000},
        "pacing": {
            "hold_s": pacing.get("min_scene_s", 3.4),
            "breath_s": pacing.get("breath_s", 0.75),
            "crossfade_s": pacing.get("crossfade_s", 0.65),
            "max_gap_s": pacing.get("max_gap_s", 0.18),
        },
        "music": music,
        "words": timeline["words"],
        "scenes": timeline["scenes"],
        "dips": timeline["dips"],
        "duration": timeline["duration"],
        "seed": seed,
        "seo": seo,
        "qc": qc,
    }


def save_project(path: Path, project: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project, indent=2), encoding="utf-8")


def load_project(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
