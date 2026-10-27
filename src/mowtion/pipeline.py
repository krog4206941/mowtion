"""From a script or a clip to a finished MP4, plus project.json."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from mowtion.master import master, write_wav
from mowtion.music import mix_voice_music, render_score
from mowtion.project import build_project, load_project, save_project
from mowtion.qc import qc_video
from mowtion.render import frame_size, render_frame
from mowtion.seo import build_seo
from mowtion.theme import get_theme
from mowtion.timeline import plan_timeline
from mowtion.voice import DEFAULT_BLEND, DEFAULT_LANG, DEFAULT_SPEED

ROOT_VOICE = {
    "engine": "kokoro-onnx",
    "blend": DEFAULT_BLEND,
    "speed": DEFAULT_SPEED,
    "lang": DEFAULT_LANG,
}


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError(
            "mowtion needs ffmpeg on your PATH. "
            "Windows: winget install ffmpeg.  Mac: brew install ffmpeg.  "
            "Linux: install the ffmpeg package from your distro, then try again."
        )


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return np.asarray(audio, dtype=np.float32)
    from math import gcd

    g = gcd(int(src_sr), int(dst_sr))
    return resample_poly(audio, dst_sr // g, int(src_sr) // g).astype(np.float32)


def _rms(voice: np.ndarray, sr: int, fps: int, frames: int) -> list[float]:
    hop = sr / fps
    values = []
    for index in range(frames):
        a = int(index * hop)
        b = max(a + 1, int((index + 1) * hop))
        chunk = voice[a:b]
        values.append(float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0)
    peak = max(values) or 1.0
    return [round(v / peak, 4) for v in values]


def _ffmpeg_wav(src: Path, dst: Path, sr: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )


def prepare_voice(script: str | None, media: Path | None, work: Path, progress, voice_settings: dict | None = None):
    """Return (audio 48 kHz mono, words from whisper, script text or None)."""
    from mowtion.models import load_whisper
    from mowtion.transcribe import align_to_script, ffmpeg_to_16k, transcribe_wav, write_16k

    work.mkdir(parents=True, exist_ok=True)
    wav16 = work / "speech-16k.wav"
    settings = dict(ROOT_VOICE)
    if voice_settings:
        settings.update(voice_settings)
    if script:
        from mowtion.voice import synthesize

        if progress:
            progress(0.08, "Speaking the script")
        audio, sr = synthesize(
            script,
            speed=float(settings.get("speed") or DEFAULT_SPEED),
            lang=settings.get("lang") or DEFAULT_LANG,
            blend=settings.get("blend") or DEFAULT_BLEND,
            phoneme_fix=settings.get("phoneme_fix"),
            progress=progress,
        )
        audio = _resample(audio, sr, 48000)
        write_16k(audio, 48000, wav16)
    elif media:
        if progress:
            progress(0.08, "Reading the clip")
        _ffmpeg_wav(media, work / "speech-48k.wav", 48000)
        audio, sr = sf.read(work / "speech-48k.wav", dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        audio = _resample(np.asarray(audio, dtype=np.float32), sr, 48000)
        ffmpeg_to_16k(media, wav16)
        script = None
    else:
        raise ValueError("Add a script or drop a clip.")
    if progress:
        progress(0.22, "Transcribing, word by word")
    model = load_whisper(progress)
    heard = transcribe_wav(wav16, model)
    del model
    if script:
        words = align_to_script(script, heard)
    else:
        words = heard
        script = " ".join(word["text"] for word in words)
    if not words:
        raise RuntimeError("No words were heard. Try a clearer clip, or type a script.")
    return audio, words, script, settings


def encode_video(project: dict, audio_path: Path, out_path: Path, crf: int = 20, preset: str = "medium", progress=None):
    w = project["format"]["w"]
    h = project["format"]["h"]
    fps = project["format"]["fps"]
    frames = int(round(float(project["duration"]) * fps))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-shortest",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for index in range(frames):
            image = render_frame(project, index / fps)
            proc.stdin.write(image.convert("RGB").tobytes())
            if progress and index % 15 == 0:
                progress(0.55 + 0.38 * (index / max(1, frames)), f"Drawing frame {index + 1} of {frames}")
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise RuntimeError("ffmpeg could not encode the video.")
    return frames


def render_one(
    *,
    audio: np.ndarray,
    words: list[dict],
    script: str,
    source_name: str | None,
    preset: str,
    aspect: str,
    out_path: Path,
    voice_settings: dict,
    seo_on: bool = False,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    fps: int = 30,
    crf: int = 20,
    seed: int = 7,
    work: Path,
    progress=None,
    encoder_preset: str = "medium",
) -> dict:
    theme = get_theme(preset)
    w, h = frame_size(aspect)
    if progress:
        progress(0.4, "Tightening the edit")
    timeline = plan_timeline(words, audio, 48000)
    if progress:
        progress(0.46, "Writing the score")
    music = render_score(
        timeline["duration"],
        mood=theme.mood,
        bpm=theme.bpm,
        seed=seed,
        sr=48000,
        dips=timeline["dips"],
    )
    mix = mix_voice_music(timeline["audio"], music, 48000, timeline["dips"], pause_dip=0.4)
    premix = work / f"{preset}-{aspect.replace(':', 'x')}-premix.wav"
    final_wav = work / f"{preset}-{aspect.replace(':', 'x')}-mix.wav"
    write_wav(premix, mix, 48000)
    if progress:
        progress(0.52, "Mastering")
    stats = master(premix, final_wav, lufs=-14.0, true_peak=-1.0)
    frames = int(round(timeline["duration"] * fps))
    seo = build_seo(script, title, description, tags) if seo_on or title or description or tags else None
    project = build_project(
        script=script,
        source_name=source_name,
        preset=preset,
        aspect=aspect,
        width=w,
        height=h,
        fps=fps,
        timeline=timeline,
        music={"mood": theme.mood, "bpm": theme.bpm, "seed": seed, "lufs": stats.get("lufs"), "true_peak": stats.get("true_peak")},
        seo=seo,
        voice=voice_settings,
        seed=seed,
    )
    project["format"] = {"aspect": aspect, "w": w, "h": h, "fps": fps}
    project["energy"] = _rms(timeline["audio"], 48000, fps, frames)
    project["duration"] = frames / fps
    if progress:
        progress(0.55, "Drawing the pictures")
    encode_video(project, final_wav, out_path, crf=crf, preset=encoder_preset, progress=progress)
    report = qc_video(out_path, width=w, height=h, check_loudness=True)
    project["qc"] = {k: v for k, v in report.items() if k != "ok"}
    project_path = out_path.with_suffix(".project.json")
    # energy makes the json large; keep a short copy for the file on disk.
    stored = dict(project)
    stored.pop("energy", None)
    save_project(project_path, stored)
    extras = {"project": str(project_path)}
    if seo_on:
        from mowtion.thumbs import save_pack

        thumb = out_path.with_name(out_path.stem + "-thumb.png")
        cover = out_path.with_name(out_path.stem + "-cover.png")
        save_pack(theme, seo["title"] if seo else script[:80], aspect, thumb, cover)
        seo_path = out_path.with_name(out_path.stem + "-seo.json")
        seo_path.write_text(json.dumps(seo, indent=2), encoding="utf-8")
        extras.update({"thumbnail": str(thumb), "cover": str(cover), "seo": str(seo_path)})
    if progress:
        progress(1.0, "Done")
    return {"video": str(out_path), "qc": report, "preset": preset, "aspect": aspect, **extras}


def render_job(
    *,
    script: str | None = None,
    media: str | Path | None = None,
    presets: list[str] | None = None,
    aspects: list[str] | None = None,
    out: str | Path | None = None,
    out_dir: str | Path | None = None,
    seo: bool = False,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    fps: int = 30,
    crf: int = 20,
    seed: int = 7,
    progress=None,
    work: str | Path | None = None,
    encoder_preset: str = "medium",
) -> list[dict]:
    """Speak or transcribe once, then render each preset."""
    require_ffmpeg()
    presets = presets or ["clean-light"]
    aspects = aspects or ["9:16"]
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    if len(aspects) == 1:
        aspects = aspects * len(presets)
    if len(aspects) != len(presets):
        raise ValueError("Pass one aspect, or one aspect per preset.")
    for preset in presets:
        get_theme(preset)
    for aspect in aspects:
        frame_size(aspect)
    media_path = Path(media) if media else None
    if media_path and not media_path.is_file():
        raise FileNotFoundError(f"Could not find {media_path}")
    destination = Path(out_dir) if out_dir else (Path(out).parent if out else Path.cwd())
    destination.mkdir(parents=True, exist_ok=True)
    work_dir = Path(work) if work else destination / ".mowtion-work"
    audio, words, spoken, settings = prepare_voice(script, media_path, work_dir, progress)
    results = []
    for preset, aspect in zip(presets, aspects):
        if out and len(presets) == 1:
            out_path = Path(out)
        else:
            slug = aspect.replace(":", "x")
            out_path = destination / f"{preset}-{slug}.mp4"
        results.append(
            render_one(
                audio=audio,
                words=words,
                script=spoken or script or "",
                source_name=media_path.name if media_path else None,
                preset=preset,
                aspect=aspect,
                out_path=out_path,
                voice_settings=settings,
                seo_on=seo,
                title=title,
                description=description,
                tags=tags,
                fps=fps,
                crf=crf,
                seed=seed,
                work=work_dir,
                progress=progress,
                encoder_preset=encoder_preset,
            )
        )
    return results


def render_from_project(path: str | Path, out: str | Path | None = None, progress=None) -> dict:
    """Re-run a saved project.json (same script, preset, aspect, and seed)."""
    project = load_project(Path(path))
    kind = project.get("input", {}).get("kind")
    if kind != "script" or not project.get("input", {}).get("script"):
        raise ValueError("This project.json has no script to re-speak. Drop the original clip again.")
    out_path = Path(out) if out else Path(path).with_suffix(".mp4")
    results = render_job(
        script=project["input"]["script"],
        presets=[project["preset"]],
        aspects=[project["format"]["aspect"]],
        out=out_path,
        seo=bool(project.get("seo")),
        title=(project.get("seo") or {}).get("title"),
        description=(project.get("seo") or {}).get("description"),
        tags=(project.get("seo") or {}).get("tags"),
        fps=int(project["format"].get("fps") or 30),
        seed=int(project.get("seed") or 7),
        progress=progress,
    )
    return results[0]
