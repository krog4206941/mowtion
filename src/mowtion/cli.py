"""Command line. With no arguments, mowtion opens its window."""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser

from mowtion import __version__
from mowtion.server import serve


def _open(url: str) -> None:
    try:
        import webview

        webview.create_window("mowtion", url, width=1120, height=820)
        webview.start()
        return
    except Exception:
        pass
    webbrowser.open(url)
    print(f"mowtion is open at {url}")
    print("Press Ctrl+C to quit.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")


def run_app() -> int:
    httpd = serve()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    url = f"http://{host}:{port}"
    try:
        _open(url)
    finally:
        httpd.shutdown()
    return 0


def _print_progress(frac: float, message: str) -> None:
    print(f"[{int(frac * 100):3d}%] {message}", flush=True)


def run_render(args) -> int:
    from mowtion.pipeline import render_from_project, render_job

    if args.project:
        result = render_from_project(args.project, out=args.out, progress=_print_progress)
        print(result["video"])
        qc = result.get("qc") or {}
        if not qc.get("ok", True):
            print("QC notes:", "; ".join(qc.get("issues") or []))
            return 2
        return 0
    script = args.script
    if args.script_file:
        script = open(args.script_file, encoding="utf-8").read()
    if not script and not args.input:
        print("Pass --script, --script-file, --input, or --project.", file=sys.stderr)
        return 2
    results = render_job(
        script=script,
        media=args.input,
        presets=args.preset or ["clean-light"],
        aspects=args.aspect or ["9:16"],
        out=args.out,
        out_dir=args.out_dir,
        seo=args.seo,
        title=args.title,
        description=args.description,
        tags=args.tags,
        fps=args.fps,
        crf=args.crf,
        seed=args.seed,
        progress=_print_progress,
    )
    failed = False
    for result in results:
        print(result["video"])
        qc = result.get("qc") or {}
        loud = (qc.get("loudness") or {})
        if loud:
            print(f"  loudness {loud.get('lufs')} LUFS, true peak {loud.get('true_peak')} dBTP")
        if not qc.get("ok", True):
            print("  QC:", "; ".join(qc.get("issues") or []))
            failed = True
    return 2 if failed else 0


def run_doctor() -> int:
    import shutil

    from mowtion.fonts import fonts_ok
    from mowtion.models import WHISPER_MODEL, kokoro_paths

    onnx, voices = kokoro_paths()
    print(f"mowtion {__version__}")
    print(f"ffmpeg: {shutil.which('ffmpeg') or 'missing'}")
    print(f"ffprobe: {shutil.which('ffprobe') or 'missing'}")
    print(f"fonts: {'ok' if fonts_ok() else 'missing'}")
    print(f"kokoro model: {'cached' if onnx.is_file() else 'will download on first render'} ({onnx})")
    print(f"kokoro voices: {'cached' if voices.is_file() else 'will download on first render'}")
    print(f"whisper: {WHISPER_MODEL}, compute_type float32, downloads on first transcription")
    return 0 if shutil.which("ffmpeg") and fonts_ok() else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mowtion",
        description="Turn a voice or a script into a finished motion-graphics video.",
    )
    parser.add_argument("--version", action="version", version=f"mowtion {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("app", help="Open the mowtion window (this is also the default)")
    sub.add_parser("doctor", help="Check ffmpeg, fonts, and whether models are downloaded")
    render = sub.add_parser("render", help="Render a video")
    render.add_argument("--script", help="Script text to speak")
    render.add_argument("--script-file", help="Text file to speak")
    render.add_argument("--input", help="Audio or video file to transcribe")
    render.add_argument("--project", help="Re-render from a project.json")
    render.add_argument("--preset", action="append", help="Style preset. Repeat to render several.")
    render.add_argument("--aspect", action="append", choices=["9:16", "16:9"], help="9:16 or 16:9")
    render.add_argument("--out", help="Output mp4 (one preset)")
    render.add_argument("--out-dir", help="Folder for outputs")
    render.add_argument("--seo", action="store_true", help="Also write title, description, tags, and images")
    render.add_argument("--title")
    render.add_argument("--description")
    render.add_argument("--tags", help="Comma-separated tags")
    render.add_argument("--fps", type=int, default=30)
    render.add_argument("--crf", type=int, default=20)
    render.add_argument("--seed", type=int, default=7)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd in (None, "app"):
        return run_app()
    if args.cmd == "doctor":
        return run_doctor()
    if args.cmd == "render":
        return run_render(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
