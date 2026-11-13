"""Clip Studio checks that do not download voice or whisper models."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio"))

import numpy as np  # noqa: E402

from mowstudio.audio import SR, build_timeline  # noqa: E402
from mowstudio.draw import BLACK, Card, render_still  # noqa: E402
from mowstudio.segments import group_words, suggest_segments  # noqa: E402
from mowstudio.timeutil import format_ts, parse_time  # noqa: E402


def _words(count: int, step: float = 0.4) -> list[dict]:
    words = []
    for index in range(count):
        start = index * step
        text = "word"
        if index % 10 == 9:
            text = "word."
        words.append({"text": text, "start": start, "end": start + 0.25})
    return words


class TimeTests(unittest.TestCase):
    def test_parse_and_format(self):
        self.assertAlmostEqual(parse_time("90"), 90)
        self.assertAlmostEqual(parse_time("1:30"), 90)
        self.assertAlmostEqual(parse_time("1:30.5"), 90.5)
        self.assertAlmostEqual(parse_time("1:02:03.25"), 3723.25)
        self.assertEqual(format_ts(90.5), "1:30.50")
        self.assertEqual(format_ts(3723.25), "1:02:03.25")
        with self.assertRaises(ValueError):
            parse_time("nope")


class SegmentTests(unittest.TestCase):
    def test_short_clip_is_the_whole_thing(self):
        ideas = suggest_segments(_words(20, 0.5), duration=10)
        self.assertEqual(len(ideas), 1)
        self.assertIn("whole", ideas[0]["label"])
        self.assertGreaterEqual(ideas[0]["end"] - ideas[0]["start"], 9)

    def test_long_clip_stays_between_90_and_120(self):
        ideas = suggest_segments(_words(500, 0.4), duration=200)
        self.assertGreaterEqual(len(ideas), 1)
        self.assertLessEqual(len(ideas), 3)
        for idea in ideas:
            length = idea["end"] - idea["start"]
            self.assertGreaterEqual(length, 85)
            self.assertLessEqual(length, 120.5)

    def test_caption_groups_break_on_a_long_line(self):
        words = [{"text": "one", "start": i * 0.2, "end": i * 0.2 + 0.1} for i in range(12)]
        groups = group_words(words, measure=lambda phrase: len(phrase) * 10, max_words=4, max_width=10_000)
        self.assertTrue(all(len(group) <= 4 for group in groups))
        self.assertEqual(sum(len(group) for group in groups), 12)


class LookTests(unittest.TestCase):
    def test_background_is_pure_black(self):
        card = Card(accents=["ONE FACT", "TWO FACTS"])
        intro = render_still(card, 0.2, speech_dur=8)
        content = render_still(card, 4.0, words=[{"text": "Hello.", "start": 0.2, "end": 0.8}], speech_dur=8)
        end = render_still(card, 20, speech_dur=8)
        tall = render_still(Card(aspect="9:16"), 0.2, speech_dur=8)
        self.assertEqual(intro.size, (1920, 1080))
        self.assertEqual(tall.size, (1080, 1920))
        for image in (intro, content, end, tall):
            for point in ((0, 0), (8, 8), (image.size[0] - 1, 0), (0, image.size[1] - 1)):
                self.assertEqual(image.getpixel(point), BLACK)
        self.assertFalse(card.music)
        titled = Card(headline="work hard, then take a risk", source="usc")
        self.assertEqual(titled.headline, "WORK HARD, THEN TAKE A RISK")
        self.assertEqual(titled.source, "USC")
        self.assertFalse(titled.music)

    def test_voice_only_is_silent_before_the_voice(self):
        speech = np.ones(SR, dtype=np.float32) * 0.2
        mix = build_timeline(speech, SR, intro=2.5, outro=2.25, music=False)
        self.assertLess(float(np.max(np.abs(mix[: int(0.4 * SR)]))), 1e-6)


class PackTests(unittest.TestCase):
    def test_prompts_cover_the_rules(self):
        text = (ROOT / "studio" / "PROMPTS.md").read_text(encoding="utf-8")
        for phrase in (
            "90 to 120",
            "Elon Musk just revealed",
            "BREAKING:",
            "7 days",
            "48 hours",
            "Elon Musk on",
            "ALT HOOK 1",
            "Attention Trap",
            "6th-grade",
            "hashtags",
            "{{TRANSCRIPT}}",
        ):
            self.assertIn(phrase, text)

    def test_page_defaults_to_no_music(self):
        html = (ROOT / "studio" / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn("No music (voice only)", html)
        self.assertIn('name="music" value="off" checked', html)
        self.assertIn("Grandfather Joe", html)

    def test_windows_scripts(self):
        install = (ROOT / "studio" / "install.bat").read_bytes()
        start = (ROOT / "studio" / "start.bat").read_bytes()
        updater = (ROOT / "studio" / "update_ytdlp.bat").read_bytes()
        ffmpeg_ps = (ROOT / "studio" / "windows" / "get-ffmpeg.ps1").read_text(encoding="utf-8")
        for blob in (install, start, updater):
            self.assertIn(b"\r\n", blob)
            text = blob.decode("utf-8")
            self.assertIn('cd /d "%~dp0"', text)
            self.assertNotIn("/workspace", text)
            self.assertNotIn("sudo", text)
            self.assertNotIn("/dev/null", text)
        install_text = install.decode("utf-8")
        self.assertIn("requirements.txt", install_text)
        self.assertIn("requirements-joe.txt", install_text)
        self.assertIn("mowstudio doctor", install_text)
        self.assertLess(install_text.index(":joe_failed"), install_text.index("mowstudio doctor"))
        joe_block = install_text.split(":joe_failed")[1].split(":joe_done")[0]
        self.assertNotIn("exit /b 1", joe_block)
        self.assertIn("fast voice", joe_block)
        start_text = start.decode("utf-8")
        self.assertIn("-m mowstudio", start_text)
        self.assertIn("PYTHONPATH", start_text)
        self.assertIn("ffmpeg.exe", ffmpeg_ps)
        self.assertIn("https://", ffmpeg_ps)

    def test_youtube_bot_check_is_not_called_private(self):
        from mowstudio.download import _friendly_download_error

        message = str(_friendly_download_error(Exception("Sign in to confirm you're not a bot")))
        self.assertIn("sign in", message.lower())
        self.assertNotIn("private", message.lower())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is required")
class RenderSmokeTest(unittest.TestCase):
    def test_voice_only_mp4(self):
        from mowstudio.qc import inspect
        from mowstudio.render import render_mp4

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            audio = folder / "talk.wav"
            video = folder / "picture.mp4"
            _write_bursts(audio, seconds=6.0)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=0x224466:s=640x360:d=6",
                    "-i",
                    str(audio),
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    str(video),
                ],
                check=True,
            )
            words = [
                {"text": "Hello" if i % 6 else "Hello.", "start": i * 0.45, "end": i * 0.45 + 0.3}
                for i in range(12)
            ]
            out = folder / "out.mp4"
            report = render_mp4(
                video=video,
                audio=audio,
                words=words,
                out=out,
                card=Card(
                    hook=("HELLO THERE.", "A SHORT TEST."),
                    headline="VOICE ONLY TEST",
                    subtitle="No music under this.",
                    source="TEST SOURCE",
                    date="13 NOV 2026",
                    end=("THAT IS THE POINT.", "FULL SOURCE IN THE POST."),
                    accents=["FIRST NOTE", "SECOND NOTE"],
                    music=False,
                    has_footage=True,
                ),
                work=folder / "build",
            )
            self.assertTrue(report["ok"], report)
            self.assertFalse(report["music"])
            checked = inspect(out, 1920, 1080)
            self.assertTrue(checked["ok"], checked)
            self.assertLess(checked["bytes"], 15_000_000)
            self.assertLessEqual(checked["true_peak"], -1.0)
            self.assertLess(abs(checked["lufs"] + 14), 0.6)


def _write_bursts(path: Path, seconds: float) -> None:
    count = int(SR * seconds)
    t = np.arange(count) / SR
    gate = (np.sin(2 * np.pi * 2.0 * t) > -0.2).astype(np.float32)
    tone = np.sin(2 * np.pi * 190 * t) + 0.35 * np.sin(2 * np.pi * 240 * t)
    audio = (0.25 * gate * tone).astype(np.float32)
    samples = np.clip(audio * 32767, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(samples.tobytes())


if __name__ == "__main__":
    unittest.main()
