"""Cut a start-to-end clip with ffmpeg."""

from __future__ import annotations

from pathlib import Path

from mowstudio.media import ffmpeg, has_audio, has_video, run


def cut_media(src: Path, dest: Path, start: float, end: float) -> None:
    if end - start < 0.4:
        raise ValueError("That part is too short. Pick at least one second.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Seek near the start, then decode a few seconds for a clean cut.
    lead = min(start, 8.0)
    rough = max(0.0, start - lead)
    length = end - start
    maps = ["-map", "0:a:0"]
    video_args: list[str] = []
    if has_video(src):
        maps = ["-map", "0:v:0", "-map", "0:a:0"]
        video_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
    if not has_audio(src):
        raise ValueError("This file has no sound.")
    run(
        [
            ffmpeg(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{rough:.3f}",
            "-i",
            str(src),
            "-ss",
            f"{start - rough:.3f}",
            "-t",
            f"{length:.3f}",
            *maps,
            *video_args,
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
