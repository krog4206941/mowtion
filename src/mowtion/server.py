"""Local desktop UI. The window talks only to 127.0.0.1."""

from __future__ import annotations

import json
import mimetypes
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mowtion.paths import cache_dir
from mowtion.theme import list_themes

MAX_UPLOAD = 400 * 1024 * 1024
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def ui_dir() -> Path:
    here = Path(__file__).resolve().parent / "ui"
    if (here / "index.html").is_file():
        return here
    import sys

    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for candidate in (root / "mowtion" / "ui", root / "ui"):
            if (candidate / "index.html").is_file():
                return candidate
    return here


def _job_dir(job_id: str) -> Path:
    path = cache_dir() / "jobs" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _start_job(job_id: str, script: str | None, media: Path | None, preset: str, aspect: str, seo: bool, title: str, description: str, tags: str):
    def progress(frac: float, message: str):
        with _LOCK:
            _JOBS[job_id]["progress"] = frac
            _JOBS[job_id]["message"] = message

    try:
        from mowtion.pipeline import render_job

        tag_list = [part.strip() for part in tags.split(",") if part.strip()] if tags else None
        results = render_job(
            script=script,
            media=media,
            presets=[preset],
            aspects=[aspect],
            out_dir=_job_dir(job_id),
            seo=seo,
            title=title or None,
            description=description or None,
            tags=tag_list,
            progress=progress,
            work=_job_dir(job_id) / "work",
        )
        with _LOCK:
            _JOBS[job_id]["status"] = "done"
            _JOBS[job_id]["progress"] = 1
            _JOBS[job_id]["message"] = "Your video is ready."
            _JOBS[job_id]["result"] = results[0]
    except Exception as exc:  # noqa: BLE001 — shown to the person in the window
        with _LOCK:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["message"] = str(exc)
            _JOBS[job_id]["detail"] = traceback.format_exc()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def _read(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_UPLOAD:
            raise ValueError("That file is larger than 400 MB.")
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            body = (ui_dir() / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            file = (ui_dir() / name).resolve()
            if not str(file).startswith(str(ui_dir().resolve())) or not file.is_file():
                self._json(404, {"error": "Not found"})
                return
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self._send(200, file.read_bytes(), mime)
            return
        if path == "/api/presets":
            self._json(200, {"presets": list_themes()})
            return
        if path == "/api/health":
            import shutil

            from mowtion.fonts import fonts_ok
            from mowtion.models import kokoro_paths

            onnx, voices = kokoro_paths()
            self._json(
                200,
                {
                    "ffmpeg": bool(shutil.which("ffmpeg")),
                    "fonts": fonts_ok(),
                    "kokoro": onnx.is_file() and voices.is_file(),
                },
            )
            return
        if path.startswith("/api/jobs/"):
            parts = path.strip("/").split("/")
            # api / jobs / id / [video|project|thumb|cover|seo]
            if len(parts) < 3:
                self._json(404, {"error": "Not found"})
                return
            job_id = parts[2]
            with _LOCK:
                job = dict(_JOBS.get(job_id) or {})
            if not job:
                self._json(404, {"error": "No such job"})
                return
            if len(parts) == 3:
                public = {k: job.get(k) for k in ("status", "progress", "message", "result", "detail")}
                self._json(200, public)
                return
            result = job.get("result") or {}
            key = {"video": "video", "project": "project", "thumb": "thumbnail", "cover": "cover", "seo": "seo"}.get(parts[3])
            target = result.get(key) if key else None
            if not target or not Path(target).is_file():
                self._json(404, {"error": "Not ready"})
                return
            file = Path(target)
            mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self._send(200, file.read_bytes(), mime)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/jobs":
            self._json(404, {"error": "Not found"})
            return
        try:
            query = parse_qs(parsed.query)
            raw = self._read()
            content = self.headers.get("Content-Type", "")
            script = None
            media = None
            preset = (query.get("preset") or ["clean-light"])[0]
            aspect = (query.get("aspect") or ["9:16"])[0]
            seo = (query.get("seo") or ["0"])[0] in {"1", "true", "on"}
            title = (query.get("title") or [""])[0]
            description = (query.get("description") or [""])[0]
            tags = (query.get("tags") or [""])[0]
            if "application/json" in content:
                data = json.loads(raw.decode("utf-8") or "{}")
                script = (data.get("script") or "").strip()
                preset = data.get("preset") or preset
                aspect = data.get("aspect") or aspect
                seo = bool(data.get("seo"))
                title = data.get("title") or ""
                description = data.get("description") or ""
                tags = data.get("tags") or ""
                if isinstance(tags, list):
                    tags = ", ".join(tags)
            else:
                filename = (query.get("filename") or ["clip"])[0]
                safe = Path(filename).name or "clip"
                if not raw:
                    raise ValueError("That file was empty.")
                job_id = uuid.uuid4().hex[:12]
                media = _job_dir(job_id) / safe
                media.write_bytes(raw)
            if not script and media is None:
                raise ValueError("Type a script or drop a clip first.")
            if aspect not in {"9:16", "16:9"}:
                raise ValueError("Pick vertical (9:16) or widescreen (16:9).")
            from mowtion.theme import get_theme

            get_theme(preset)
            if "job_id" not in locals():
                job_id = uuid.uuid4().hex[:12]
            with _LOCK:
                _JOBS[job_id] = {"status": "running", "progress": 0.02, "message": "Starting", "result": None}
            thread = threading.Thread(
                target=_start_job,
                args=(job_id, script, media, preset, aspect, seo, title, description, tags),
                daemon=True,
            )
            thread.start()
            self._json(200, {"id": job_id})
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})


def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)
