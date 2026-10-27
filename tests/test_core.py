"""Fast tests. They do not download voice or transcription models."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from mowtion.cleanup import cleanup_words
from mowtion.easing import container_open, leading, spring, text_open
from mowtion.music import duck_gain, render_score
from mowtion.project import build_project, load_project, save_project
from mowtion.render import frame_size, render_frame
from mowtion.seo import build_seo
from mowtion.theme import PRESETS
from mowtion.timeline import plan_timeline


def _word(text, start, end):
    return {"text": text, "start": start, "end": end}


class EasingTests(unittest.TestCase):
    def test_spring_settles(self):
        self.assertEqual(spring(-1), 0.0)
        self.assertGreater(spring(0.4), 0.5)
        self.assertLess(abs(spring(2.5) - 1), 0.05)

    def test_container_leads_text(self):
        self.assertEqual(text_open(0.1), 0.0)
        self.assertGreater(container_open(0.12), 0.0)
        self.assertGreater(container_open(0.12), text_open(0.12))

    def test_leading_edge_grows_forward(self):
        self.assertEqual(leading(0), 0.0)
        self.assertLess(leading(0.2), leading(0.7))
        self.assertEqual(leading(2), 1.0)


class CleanupTests(unittest.TestCase):
    def test_fillers_repeats_and_you_know(self):
        words = [
            _word("So", 0.0, 0.2),
            _word("um", 0.3, 0.45),
            _word("the", 0.5, 0.7),
            _word("the", 0.72, 0.9),
            _word("idea", 1.0, 1.3),
            _word("you", 1.4, 1.55),
            _word("know", 1.56, 1.8),
            _word("stands.", 1.9, 2.3),
        ]
        cleaned = cleanup_words(words)
        self.assertEqual([w["text"] for w in cleaned], ["So", "the", "idea", "stands."])


class TimelineTests(unittest.TestCase):
    def test_dead_air_is_removed_and_scenes_hold(self):
        sr = 16000
        # Two short words with a long silent gap between them, plus a filler.
        audio = np.zeros(int(6 * sr), dtype=np.float32)
        audio[int(0.1 * sr) : int(0.4 * sr)] = 0.2
        audio[int(4.2 * sr) : int(4.6 * sr)] = 0.2
        words = [
            _word("Hello", 0.1, 0.4),
            _word("um", 0.5, 0.7),
            _word("there.", 4.2, 4.6),
        ]
        timeline = plan_timeline(words, audio, sr)
        texts = [w["text"] for w in timeline["words"]]
        self.assertNotIn("um", [t.lower().strip(".,") for t in texts])
        # Original clip was 6s of mostly silence. The rebuild should be a held graphic, not 6s of dead air.
        self.assertLess(timeline["duration"], 8)
        self.assertGreaterEqual(timeline["scenes"][0]["t1"] - timeline["scenes"][0]["t0"], 3.2)
        self.assertLessEqual(timeline["scenes"][0]["t1"] - timeline["scenes"][0]["t0"], 4.6)
        self.assertTrue(timeline["scenes"][-1]["key"])
        self.assertGreaterEqual(timeline["scenes"][-1]["breath"], 0.5)

    def test_kinds_cycle(self):
        sr = 8000
        words = []
        t = 0.2
        for i, sentence in enumerate(["One two three.", "Four five six.", "Seven eight nine."]):
            for word in sentence.split():
                words.append(_word(word, t, t + 0.25))
                t += 0.3
            t += 0.2
        audio = np.zeros(int((t + 1) * sr), dtype=np.float32)
        timeline = plan_timeline(words, audio, sr)
        kinds = [scene["kind"] for scene in timeline["scenes"]]
        self.assertGreaterEqual(len(set(kinds)), 3)


class ThemeSeoProjectTests(unittest.TestCase):
    def test_presets_include_the_required_looks(self):
        self.assertIn("dark-techy", PRESETS)
        self.assertIn("clean-light", PRESETS)
        self.assertGreaterEqual(len(PRESETS), 5)
        self.assertEqual(PRESETS["clean-light"].bg.lower(), "#edede8")
        self.assertEqual(PRESETS["clean-light"].accent.lower(), "#d7043b")

    def test_seo_pack(self):
        seo = build_seo("Mowtion draws moving pictures while you speak. Export a finished video.")
        self.assertTrue(seo["title"])
        self.assertIn("mowtion", seo["description"].lower())
        self.assertIn("motion graphics", seo["tags"])

    def test_project_roundtrip(self):
        timeline = {
            "words": [_word("Hi", 0.2, 0.5)],
            "scenes": [],
            "dips": [],
            "duration": 4,
            "pacing": {"min_scene_s": 3.4, "breath_s": 0.75, "crossfade_s": 0.65, "max_gap_s": 0.18},
        }
        project = build_project(
            script="Hi",
            source_name=None,
            preset="dark-techy",
            aspect="9:16",
            width=1080,
            height=1920,
            fps=30,
            timeline=timeline,
            music={"mood": "minor", "bpm": 90, "seed": 7},
            seo=None,
            voice={"engine": "kokoro-onnx", "speed": 1.03},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "project.json"
            save_project(path, project)
            loaded = load_project(path)
        self.assertEqual(loaded["preset"], "dark-techy")
        self.assertEqual(loaded["audio"]["lufs"], -14.0)
        self.assertEqual(loaded["words"][0]["text"], "Hi")


def _sample_project(aspect: str, preset: str) -> dict:
    w, h = frame_size(aspect)
    return {
        "preset": preset,
        "duration": 4.0,
        "format": {"aspect": aspect, "w": w, "h": h, "fps": 30},
        "music": {"bpm": 96},
        "pacing": {"crossfade_s": 0.65},
        "energy": [],
        "scenes": [
            {
                "kind": "kinetic",
                "transition": "dissolve",
                "t0": 0.0,
                "t1": 4.0,
                "speech_t0": 0.4,
                "speech_t1": 2.2,
                "key": False,
                "breath": 0.0,
                "title": "Your voice in.",
                "words": [
                    _word("Your", 0.4, 0.7),
                    _word("voice", 0.75, 1.1),
                    _word("in.", 1.2, 1.6),
                ],
                "bars": [
                    {"label": "voice", "value": 0.4},
                    {"label": "picture", "value": 0.7},
                    {"label": "music", "value": 0.55},
                    {"label": "export", "value": 0.9},
                ],
                "ring": 72,
                "points": [0.2, 0.35, 0.3, 0.55, 0.5, 0.8, 0.7, 0.92],
            }
        ],
    }


class RenderTests(unittest.TestCase):
    def test_both_aspects_and_motion(self):
        tall = render_frame(_sample_project("9:16", "dark-techy"), 1.2)
        wide = render_frame(_sample_project("16:9", "clean-light"), 1.2)
        self.assertEqual(tall.size, (1080, 1920))
        self.assertEqual(wide.size, (1920, 1080))
        self.assertNotEqual(tall.getpixel((20, 20)), wide.getpixel((20, 20)))
        later = render_frame(_sample_project("9:16", "dark-techy"), 1.5)
        self.assertNotEqual(tall.tobytes(), later.tobytes())

    def test_scene_kinds_draw(self):
        project = _sample_project("9:16", "warm-editorial")
        for kind in ("card", "bars", "ring", "line", "abstract"):
            project["scenes"][0]["kind"] = kind
            image = render_frame(project, 1.4)
            self.assertEqual(image.size, (1080, 1920))


class MusicTests(unittest.TestCase):
    def test_score_and_duck(self):
        score = render_score(3.0, mood="major", bpm=96, seed=3, sr=16000)
        self.assertEqual(score.shape[1], 2)
        self.assertGreater(float(np.max(np.abs(score))), 0.01)
        self.assertLess(float(np.max(np.abs(score))), 0.95)
        voice = np.zeros(len(score), dtype=np.float32)
        voice[4000:8000] = 0.5
        gain = duck_gain(voice, 16000, dips=[[0.1, 0.4]], pause_dip=0.4)
        # Under the voice the music is held down. In the breath it is lower still.
        self.assertLess(float(np.mean(gain[5000:7000])), 0.7)
        self.assertLess(float(np.mean(gain[int(0.2 * 16000) : int(0.35 * 16000)])), 0.7)


class MasterAndEncodeTests(unittest.TestCase):
    def test_master_and_faststart(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is not installed")
        from mowtion.master import master, write_wav
        from mowtion.pipeline import encode_video
        from mowtion.qc import qc_video

        sr = 48000
        t = np.arange(int(4 * sr)) / sr
        tone = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        stereo = np.stack([tone, tone * 0.8], axis=1)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "in.wav"
            dst = tmp / "out.wav"
            write_wav(src, stereo, sr)
            stats = master(src, dst)
            self.assertLessEqual(stats["true_peak"], -0.95)
            self.assertLess(abs(stats["lufs"] + 14), 1.5)
            project = _sample_project("16:9", "studio-blue")
            project["duration"] = 0.4
            video = tmp / "tiny.mp4"
            encode_video(project, dst, video, crf=28, preset="ultrafast")
            report = qc_video(video, width=1920, height=1080, check_loudness=False)
            self.assertTrue(report["faststart"], report)
            self.assertEqual(report["video_codec"], "h264")
            self.assertEqual(report["audio_codec"], "aac")


class ServerTests(unittest.TestCase):
    def test_pages_and_presets(self):
        from mowtion.server import serve

        httpd = serve()
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/presets") as response:
                data = json.load(response)
            ids = [item["id"] for item in data["presets"]]
            self.assertIn("dark-techy", ids)
            self.assertIn("clean-light", ids)
            self.assertGreaterEqual(len(ids), 5)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
                html = response.read().decode()
            self.assertIn("mowtion", html.lower())
            self.assertIn("Make video", html)
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/jobs",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 400)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
