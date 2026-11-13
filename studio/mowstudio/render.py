"""Turn a clip, words, and titles into a finished MP4."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from mowstudio.audio import SR, build_timeline, load_mono, master, write_wav
from mowstudio.draw import INTRO, OUTRO, FPS, Card, FontBook, Layout, _chrome, draw_content, draw_end, draw_intro, layout_for, prepare_groups
from mowstudio.media import ffmpeg, run
from mowstudio.qc import inspect


def _encode(visual: Path, audio: Path, out: Path, duration: float, work: Path) -> None:
    """H.264 + AAC, fast start, under 15 MB. Two passes when the cap needs it."""
    out.parent.mkdir(parents=True, exist_ok=True)
    audio_bytes = audio.stat().st_size
    budget = 14_200_000 - audio_bytes
    kbps = max(400, int((budget * 8) / max(duration, 0.5) / 1000 * 0.88))

    def two_pass(rate: int, dest: Path) -> None:
        logfile = work / "x264pass"
        for leftover in work.glob("x264pass*"):
            leftover.unlink()
        video_args = [
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-b:v",
            f"{rate}k",
            "-maxrate",
            f"{int(rate * 1.15)}k",
            "-bufsize",
            f"{rate * 2}k",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-passlogfile",
            str(logfile),
            "-threads",
            "4",
        ]
        run(
            [ffmpeg(), "-y", "-hide_banner", "-i", str(visual), *video_args, "-pass", "1", "-an", "-f", "null", "-"],
            log=work / "pass1.log",
        )
        run(
            [
                ffmpeg(),
                "-y",
                "-hide_banner",
                "-i",
                str(visual),
                "-i",
                str(audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                *video_args,
                "-pass",
                "2",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                "-t",
                f"{duration:.3f}",
                str(dest),
            ],
            log=work / "pass2.log",
        )

    two_pass(kbps, out)
    if out.stat().st_size >= 15_000_000:
        smaller = max(280, int(kbps * (14_000_000 / out.stat().st_size) * 0.9))
        two_pass(smaller, out)
    if out.stat().st_size >= 15_000_000:
        raise RuntimeError("The video was still over 15 MB. Try a shorter clip.")


def render_mp4(
    *,
    video: Path | None,
    audio: Path,
    words: list[dict],
    out: Path,
    card: Card,
    work: Path,
    progress=None,
) -> dict:
    """Render one MP4. ``card.music`` defaults to off (voice only)."""

    def poke(frac: float, message: str) -> None:
        if progress:
            progress(frac, message)

    work.mkdir(parents=True, exist_ok=True)
    poke(0.02, "Reading the sound...")
    speech = load_mono(audio, work / "speech.wav", SR)
    if speech.size == 0 or float(abs(speech).max()) < 1e-4:
        raise RuntimeError("This clip has no sound to use.")
    speech_dur = len(speech) / SR
    layout: Layout = layout_for(card.aspect)
    fonts = FontBook()
    groups = prepare_groups(words, layout, fonts)
    n_intro = int(round(INTRO * FPS))
    n_outro = int(round(OUTRO * FPS))
    n_content = max(1, int(round(speech_dur * FPS)))
    n_frames = n_intro + n_content + n_outro
    duration = n_frames / FPS
    timeline_intro = n_intro / FPS
    timeline_outro = n_outro / FPS

    poke(0.08, "Setting the loudness..." if not card.music else "Adding quiet music and setting the loudness...")
    mix = build_timeline(speech, SR, timeline_intro, timeline_outro, music=card.music)
    # Match the picture length exactly.
    target_n = int(round(duration * SR))
    if len(mix) < target_n:
        pad = np.zeros((target_n - len(mix), 2), dtype=np.float32)
        mix = np.concatenate([mix, pad], axis=0)
    elif len(mix) > target_n:
        mix = mix[:target_n]
    write_wav(work / "mix.wav", mix, SR)
    master(work / "mix.wav", work / "audio_final.m4a", work)

    poke(0.22, "Drawing the frames...")
    visual = work / "visual_master.mp4"
    vw, vh = layout.video_size
    decoder = None
    if video is not None and card.has_footage:
        vf = (
            f"fps={FPS},scale={vw}:{vh}:force_original_aspect_ratio=decrease,"
            f"pad={vw}:{vh}:(ow-iw)/2:(oh-ih)/2:black"
        )
        decoder = subprocess.Popen(
            [ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    log = open(work / "draw.log", "w", encoding="utf-8")
    encoder = subprocess.Popen(
        [
            ffmpeg(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{layout.w}x{layout.h}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "4",
            str(visual),
        ],
        stdin=subprocess.PIPE,
        stderr=log,
    )
    chrome = _chrome(card, layout, fonts)
    last = None
    frame_bytes = vw * vh * 3
    assert encoder.stdin is not None
    try:
        for index in range(n_frames):
            t = index / FPS
            if index < n_intro:
                frame = draw_intro(card, layout, fonts, t)
            elif index < n_intro + n_content:
                if decoder is not None and decoder.stdout is not None:
                    raw = decoder.stdout.read(frame_bytes)
                    if len(raw) == frame_bytes:
                        last = Image.frombytes("RGB", (vw, vh), raw)
                frame = draw_content(card, layout, fonts, chrome, last, groups, t, speech_dur)
            else:
                frame = draw_end(card, layout, fonts)
            if frame.getpixel((0, 0)) != (0, 0, 0):
                raise RuntimeError("A frame was not on a black background.")
            encoder.stdin.write(frame.tobytes())
            if index % 48 == 0:
                poke(0.22 + 0.55 * (index / n_frames), "Drawing the frames...")
    finally:
        encoder.stdin.close()
        encoder.wait()
        log.close()
        if decoder is not None:
            if decoder.stdout:
                decoder.stdout.close()
            decoder.wait()
    if encoder.returncode:
        raise RuntimeError("Drawing the video failed. See the black window for details.")

    poke(0.82, "Saving the MP4...")
    _encode(visual, work / "audio_final.m4a", out, duration, work)
    poke(0.94, "Checking the video...")
    report = inspect(out, layout.w, layout.h)
    if not report["ok"]:
        raise RuntimeError("The video did not pass the checks: " + "; ".join(report["issues"]))
    try:
        visual.unlink()
    except OSError:
        pass
    poke(1.0, "Done.")
    report["video"] = str(out)
    report["music"] = bool(card.music)
    return report
