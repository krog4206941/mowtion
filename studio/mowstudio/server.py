"""Local web app. It listens only on this computer."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from mowstudio import __version__
from mowstudio.cut import cut_media
from mowstudio.doctor import checks
from mowstudio.download import download_url
from mowstudio.draw import Card
from mowstudio.media import duration_of, has_video
from mowstudio.paths import PROMPTS_PATH, UI_DIR, ensure_dirs
from mowstudio.project import create, folder_for, load, public, save
from mowstudio.render import render_mp4
from mowstudio.segments import format_transcript, slice_words, suggest_segments
from mowstudio.timeutil import date_label, iso_date, parse_time
from mowstudio.transcribe import transcribe
from mowstudio.voice import speak

ALLOWED_UPLOAD = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
BUSY = threading.Lock()
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 800 * 1024 * 1024


def _poke(job: dict, frac: float, message: str) -> None:
    frac = max(0.0, min(1.0, float(frac)))
    with LOCK:
        last = float(job.get("_printed", -1))
        changed = message != job.get("message") or frac - last >= 0.02 or frac >= 1
        job["progress"] = frac
        job["message"] = message
        if changed:
            job["_printed"] = frac
    if changed:
        print(f"[{int(frac * 100):3d}%] {message}", flush=True)


def _friendly(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    text = str(exc).strip() or exc.__class__.__name__
    low = text.lower()
    if "private" in low or "video unavailable" in low:
        return "That video is private or blocked. Try a public link."
    if "unsupported url" in low:
        return "This link did not work. Use a YouTube link or a public X post."
    if "403" in low or "forbidden" in low:
        return "The site said no. If this is an X post, it has to be public. Then press Update the downloader and try again."
    if "video tool is missing" in low or "ffmpeg" in low and "not found" in low:
        return "The video tool is missing. Double-click install.bat again."
    line = text.splitlines()[-1].strip()
    if len(line) > 320:
        line = line[:320] + "..."
    return line or "Something went wrong. Read the black window, then try again."


def _launch(fn) -> str | None:
    if not BUSY.acquire(blocking=False):
        return None
    import uuid

    job = {
        "id": uuid.uuid4().hex[:12],
        "status": "running",
        "progress": 0.0,
        "message": "Starting...",
        "result": None,
        "error": None,
    }
    with LOCK:
        JOBS[job["id"]] = job

    def wrap() -> None:
        try:
            result = fn(job)
            with LOCK:
                job["status"] = "done"
                job["progress"] = 1.0
                job["message"] = "Done."
                job["result"] = result
        except Exception as exc:
            message = _friendly(exc)
            print("ERROR:", message, flush=True)
            with LOCK:
                job["status"] = "error"
                job["error"] = message
                job["message"] = message
        finally:
            BUSY.release()

    threading.Thread(target=wrap, daemon=True).start()
    return job["id"]


def _job_view(job: dict) -> dict:
    with LOCK:
        return {
            "id": job["id"],
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "result": job["result"],
            "error": job["error"],
        }


def _blank_meta(pid: str, source: Path, title: str, channel: str, upload: str, url: str) -> dict:
    return {
        "id": pid,
        "title": title,
        "channel": channel,
        "upload_date": iso_date(upload) if upload and upload.isdigit() else (upload or ""),
        "date_label": date_label(upload),
        "url": url,
        "source_name": source.name,
        "has_video": has_video(source),
        "duration": duration_of(source),
        "words": [],
        "transcript": "",
        "suggestions": [],
        "clip": None,
        "clip_start": None,
        "clip_end": None,
        "voice": None,
        "voice_engine": "",
        "voice_words": [],
    }


def _read_words(job: dict, source: Path, folder: Path, start_frac: float) -> list[dict]:
    def progress(frac: float, message: str) -> None:
        _poke(job, start_frac + (1 - start_frac) * frac, message)

    return transcribe(source, folder / "asr", progress)


def _finish_media(job: dict, pid: str, folder: Path, meta: dict) -> dict:
    _poke(job, 0.72, "Reading the words. Leave this window open.")
    words = _read_words(job, folder / meta["source_name"], folder, 0.72)
    meta["words"] = words
    meta["transcript"] = format_transcript(words)
    meta["suggestions"] = suggest_segments(words, duration=meta["duration"])
    save(folder, meta)
    return public(meta)


def _import_url(job: dict, url: str) -> dict:
    pid, folder = create()

    def progress(frac: float, message: str) -> None:
        _poke(job, frac * 0.7, message)

    info = download_url(url, folder, progress)
    path: Path = info["path"]
    meta = _blank_meta(pid, path, info["title"], info["channel"], info["upload_date"], info["url"])
    meta["source_name"] = path.name
    meta["has_video"] = has_video(path)
    meta["duration"] = duration_of(path)
    save(folder, meta)
    return _finish_media(job, pid, folder, meta)


def _import_saved(job: dict, pid: str, folder: Path, path: Path, title: str) -> dict:
    meta = _blank_meta(pid, path, title, "YOUR FILE", "", "")
    save(folder, meta)
    return _finish_media(job, pid, folder, meta)


def _flag(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _up(value: str, fallback: str, limit: int = 90) -> str:
    text = " ".join((value or "").split())
    if not text:
        text = fallback
    return text.upper()[:limit]


def _card(body: dict, aspect: str, has_footage: bool) -> Card:
    raw_notes = body.get("accents") or ""
    notes = [" ".join(line.split()).upper()[:42] for line in str(raw_notes).splitlines() if line.strip()][:6]
    return Card(
        hook=(_up(body.get("hook1", ""), "WATCH THIS."), _up(body.get("hook2", ""), "IN THEIR OWN WORDS.")),
        headline=_up(body.get("headline", ""), "IN THEIR OWN WORDS", 120),
        subtitle=" ".join(str(body.get("subtitle") or "").split())[:140],
        source=_up(body.get("source", ""), "SOURCE", 48),
        date=_up(body.get("date", ""), "", 24),
        end=(_up(body.get("end1", ""), "THAT IS THE POINT."), _up(body.get("end2", ""), "FULL SOURCE IN THE POST.")),
        accents=notes,
        music=_flag(body.get("music")),
        aspect=aspect,
        has_footage=has_footage,
    )


def _range(body: dict, duration: float) -> tuple[float, float]:
    start_raw = str(body.get("start") or "").strip()
    end_raw = str(body.get("end") or "").strip()
    start = 0.0 if not start_raw else parse_time(start_raw)
    end = duration if not end_raw else parse_time(end_raw)
    if start < 0 or end < 0:
        raise ValueError("Times cannot be negative.")
    if end > duration + 0.25:
        raise ValueError("The end time is past the end of the file.")
    end = min(end, duration)
    if end - start < 1:
        raise ValueError("That part is too short. Pick at least one second.")
    if start >= end:
        raise ValueError("The start time has to be before the end time.")
    return start, end


def _render(job: dict, body: dict) -> dict:
    folder = folder_for(body.get("project") or "")
    meta = load(folder)
    start, end = _range(body, float(meta["duration"]))
    same = (
        meta.get("clip")
        and meta.get("clip_start") is not None
        and abs(float(meta["clip_start"]) - start) < 0.05
        and abs(float(meta["clip_end"]) - end) < 0.05
        and (folder / meta["clip"]).is_file()
    )
    if not same:
        _poke(job, 0.03, "Cutting the clip...")
        clip = folder / "clip.mp4"
        cut_media(folder / meta["source_name"], clip, start, end)
        meta["clip"] = clip.name
        meta["clip_start"] = start
        meta["clip_end"] = end
        meta["clip_words"] = slice_words(meta.get("words") or [], start, end)
        save(folder, meta)
    clip_path = folder / meta["clip"]
    use_voice = body.get("audio") == "voice"
    if use_voice:
        if not meta.get("voice") or not (folder / meta["voice"]).is_file():
            raise ValueError("Make a voice first, or use the clip's own sound.")
        audio = folder / meta["voice"]
        words = meta.get("voice_words") or []
        if not words:
            _poke(job, 0.08, "Reading the voice...")
            words = transcribe(audio, folder / "voice_asr")
            meta["voice_words"] = words
            save(folder, meta)
    else:
        audio = clip_path
        words = meta.get("clip_words") or slice_words(meta.get("words") or [], start, end)
    footage = clip_path if meta.get("has_video") else None
    built = []

    def make(aspect: str, filename: str, frac0: float, frac1: float) -> None:
        card = _card(body, aspect, footage is not None)
        out = folder / filename

        def progress(frac: float, message: str) -> None:
            _poke(job, frac0 + (frac1 - frac0) * frac, message)

        render_mp4(video=footage, audio=audio, words=words, out=out, card=card, work=folder / f"build-{aspect.replace(':', 'x')}", progress=progress)
        built.append(filename)

    vertical = _flag(body.get("vertical"))
    if vertical:
        make("16:9", "output.mp4", 0.1, 0.55)
        make("9:16", "output_vertical.mp4", 0.55, 1.0)
    else:
        make("16:9", "output.mp4", 0.1, 1.0)
    meta["outputs"] = built
    save(folder, meta)
    view = public(meta)
    view["message"] = "Your video is ready."
    return view


def _speak(job: dict, body: dict) -> dict:
    text = str(body.get("text") or "").strip()
    engine = str(body.get("engine") or "kokoro")
    voice = str(body.get("voice") or "male")
    pid = str(body.get("project") or "").strip()
    if pid:
        folder = folder_for(pid)
    else:
        _pid, folder = create()
        pid = _pid
        save(folder, {"id": pid, "title": "Voice", "words": [], "source_name": "", "duration": 0, "has_video": False})
    dest = folder / "voice.wav"

    def progress(frac: float, message: str) -> None:
        _poke(job, frac * 0.8, message)

    info = speak(text, dest, engine=engine, voice=voice, progress=progress)
    _poke(job, 0.85, "Reading the new voice so the captions match...")
    words = transcribe(dest, folder / "voice_asr")
    meta_path = folder / "meta.json"
    if meta_path.is_file():
        meta = load(folder)
    else:
        meta = {"id": pid}
    meta["voice"] = dest.name
    meta["voice_engine"] = info["engine"]
    meta["voice_words"] = words
    meta["voice_transcript"] = format_transcript(words)
    save(folder, meta)
    view = public(meta) if meta.get("source_name") else {"id": pid, "voice": True, "voice_engine": info["engine"]}
    view["voice"] = True
    view["voice_engine"] = info["engine"]
    view["voice_transcript"] = format_transcript(words)
    return view


def load_prompts() -> list[dict]:
    text = PROMPTS_PATH.read_text(encoding="utf-8")
    parts = re.split(r"\n(?=## )", text)
    prompts = []
    for part in parts:
        if not part.startswith("## "):
            continue
        title, _, body = part.partition("\n")
        name = title[3:].strip()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        prompts.append({"id": slug, "title": name, "body": body.strip()})
    return prompts


@app.get("/")
def home():
    return send_from_directory(UI_DIR, "index.html")


@app.get("/styles.css")
def styles():
    return send_from_directory(UI_DIR, "styles.css")


@app.get("/app.js")
def script():
    return send_from_directory(UI_DIR, "app.js")


@app.errorhandler(413)
def too_big(_error):
    return jsonify({"error": "That file is too big. Try a shorter video."}), 413


@app.get("/api/health")
def health():
    rows = []
    for label, good, detail, required in checks():
        rows.append({"label": label, "ok": good, "detail": detail, "required": required})
    return jsonify({"app": "clip-studio", "version": __version__, "checks": rows})


@app.get("/api/prompts")
def prompts():
    return jsonify({"prompts": load_prompts()})


@app.get("/api/job/<job_id>")
def job(job_id: str):
    with LOCK:
        found = JOBS.get(job_id)
    if not found:
        return jsonify({"error": "That task is gone. Try again."}), 404
    return jsonify(_job_view(found))


@app.get("/api/media/<pid>/<name>")
def media(pid: str, name: str):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name or ""):
        abort(404)
    try:
        folder = folder_for(pid)
        meta = load(folder)
    except ValueError:
        abort(404)
    allowed = {
        meta.get("source_name"),
        meta.get("clip"),
        meta.get("voice"),
        "clip.mp4",
        "voice.wav",
        "output.mp4",
        "output_vertical.mp4",
    }
    if name not in allowed:
        abort(404)
    path = folder / name
    if not path.is_file():
        abort(404)
    return send_file(path)


@app.post("/api/import-url")
def import_url():
    body = request.get_json(silent=True) or {}
    url = str(body.get("url") or "")
    job_id = _launch(lambda job: _import_url(job, url))
    if job_id is None:
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    return jsonify({"job": job_id})


@app.post("/api/import-file")
def import_file():
    if BUSY.locked():
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "Choose a video or audio file first."}), 400
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD:
        return jsonify({"error": "Use an mp4, mov, webm, mp3, or wav file."}), 400
    pid, folder = create()
    dest = folder / f"source{ext}"
    upload.save(dest)
    title = Path(upload.filename).stem.replace("_", " ")

    def work(job):
        return _import_saved(job, pid, folder, dest, title)

    job_id = _launch(work)
    if job_id is None:
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    return jsonify({"job": job_id})


@app.post("/api/render")
def render():
    body = request.get_json(silent=True) or {}
    job_id = _launch(lambda job: _render(job, body))
    if job_id is None:
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    return jsonify({"job": job_id})


@app.post("/api/speak")
def speak_route():
    body = request.get_json(silent=True) or {}
    job_id = _launch(lambda job: _speak(job, body))
    if job_id is None:
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    return jsonify({"job": job_id})


@app.post("/api/update-ytdlp")
def update_ytdlp():
    def work(job):
        _poke(job, 0.2, "Updating the downloader...")
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.returncode != 0:
            tail = (proc.stdout or "").strip().splitlines()
            raise RuntimeError(tail[-1] if tail else "The downloader did not update.")
        _poke(job, 0.9, "Downloader updated.")
        return {
            "message": "Downloader updated. If a link still fails, close the black window and double-click start.bat."
        }

    job_id = _launch(work)
    if job_id is None:
        return jsonify({"error": "The app is busy. Wait for the current step to finish."}), 409
    return jsonify({"job": job_id})


def _studio_running(port: int) -> bool:
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("app") == "clip-studio"
    except Exception:
        return False


def _free_port(start: int = 7860) -> int:
    import socket

    for port in range(start, start + 20):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No free port. Close other copies of Clip Studio and try again.")


def serve() -> int:
    ensure_dirs()
    if _studio_running(7860):
        webbrowser.open("http://127.0.0.1:7860/")
        print("Clip Studio is already open in your browser.")
        print("Leave the first black window open.")
        return 0
    port = _free_port(7860)
    from werkzeug.serving import make_server

    httpd = make_server("127.0.0.1", port, app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/"
    print("")
    print("Clip Studio is running.")
    print(url)
    print("Leave this window open. Close it when you are finished.")
    print("")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.shutdown()
    return 0
