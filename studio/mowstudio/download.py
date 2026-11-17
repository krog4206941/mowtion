"""Download a public YouTube or X video with yt-dlp."""

from __future__ import annotations

import urllib.parse
from pathlib import Path

from mowstudio.media import ffmpeg, has_audio, run


def check_url(url: str) -> str:
    text = (url or "").strip()
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Paste a full link that starts with https://")
    return text


def _friendly_download_error(exc: Exception) -> ValueError:
    text = str(exc)
    low = text.lower()
    if "not a bot" in low or "sign in to confirm" in low:
        return ValueError(
            "YouTube asked the downloader to sign in. Press Update the downloader and try again. "
            "Or choose a file from your computer."
        )
    if "private" in low or "login" in low or "unavailable" in low:
        return ValueError("That video is private, deleted, or blocked. Try a public link.")
    if "unsupported url" in low or "unable to extract" in low or "no video" in low:
        return ValueError(
            "This link did not work. Use a YouTube link or a public X post. Private posts cannot be downloaded."
        )
    if "403" in low or "401" in low or "forbidden" in low or "403" in text:
        return ValueError(
            "The site said no. If this is an X post, it has to be public. Then press Update the downloader and try again."
        )
    short = text.strip().splitlines()[-1] if text.strip() else "The download failed."
    if len(short) > 280:
        short = short[:280] + "..."
    return ValueError(short)


def download_url(url: str, dest_dir: Path, progress=None) -> dict:
    """Download one video into dest_dir / source.mp4 and return title metadata."""
    url = check_url(url)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.glob("source.*"):
        old.unlink()

    def hook(event: dict) -> None:
        if not progress:
            return
        status = event.get("status")
        if status == "downloading":
            total = event.get("total_bytes") or event.get("total_bytes_estimate") or 0
            done = event.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0.0
            progress(min(0.6, 0.05 + 0.55 * frac), "Downloading the video...")
        elif status == "finished":
            progress(0.62, "Preparing the video file...")

    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("The downloader is missing. Double-click install.bat again.") from exc

    outtmpl = str(dest_dir / "source.%(ext)s")
    opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "retries": 3,
        "fragment_retries": 3,
        "progress_hooks": [hook],
        "windowsfilenames": True,
        "restrictfilenames": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        raise _friendly_download_error(exc) from exc
    if info is None:
        raise ValueError("The download finished with no file.")

    path = _find_source(dest_dir)
    if path.suffix.lower() != ".mp4":
        mp4 = dest_dir / "source.mp4"
        run([ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-c", "copy", "-movflags", "+faststart", str(mp4)])
        path.unlink(missing_ok=True)
        path = mp4
    if not has_audio(path):
        raise ValueError("That video has no sound. Pick a clip with someone talking.")
    return {
        "path": path,
        "title": (info.get("title") or "Untitled").strip(),
        "channel": (info.get("channel") or info.get("uploader") or "SOURCE").strip(),
        "upload_date": info.get("upload_date") or "",
        "url": info.get("webpage_url") or url,
        "duration": float(info.get("duration") or _duration(path)),
    }


def _duration(path: Path) -> float:
    from mowstudio.media import duration_of

    return duration_of(path)


def _find_source(dest_dir: Path) -> Path:
    files = [path for path in dest_dir.glob("source.*") if path.suffix.lower() != ".part" and path.is_file()]
    if not files:
        raise ValueError("The download finished but the file is missing.")
    files.sort(key=lambda path: path.stat().st_size, reverse=True)
    return files[0]
