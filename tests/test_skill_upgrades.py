"""Tests for upgraded caption alignment, highlight layout, overlays, and quality gates."""
from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".agents/skills/shiny-component-shorts/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))

import align_narration  # noqa: E402
import batch_process  # noqa: E402
import build_cache  # noqa: E402
import burn_captions  # noqa: E402
import check_narration_voice  # noqa: E402
import prepare_editorial  # noqa: E402
import pronunciations  # noqa: E402
import stitch_reel as reel  # noqa: E402
import validate_editorial  # noqa: E402
from test_editorial_polish import frame_at  # noqa: E402


class PronunciationsAndCaptionsTest(unittest.TestCase):
    def test_editing_pronunciations_invalidates_cached_narration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            prompt = artifacts / "narration.txt"
            prompt.write_text("Transcript: Zyphix updates.")
            lexicon = project / "pronunciations.yaml"
            lexicon.write_text("spoken:\n  Zyphix: zie fix\n")
            audio = artifacts / "narration.wav"
            audio.write_bytes(b"cached audio")
            build_cache.update_cache(project, "tts", batch_process.narration_inputs(project))

            lexicon.write_text("spoken:\n  Zyphix: zip ticks\n")

            self.assertFalse(build_cache.check_cache(project, "tts", batch_process.narration_inputs(project), [audio]))

    def test_editing_pronunciations_invalidates_cached_takes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            prompt = project / "artifacts" / "narration.txt"
            prompt.parent.mkdir()
            prompt.write_text("Transcript: Zyphix updates.")
            lexicon = project / "pronunciations.yaml"
            lexicon.write_text("spoken:\n  Zyphix: zie fix\n")
            original = batch_process.take_fingerprint(prompt, {})

            lexicon.write_text("spoken:\n  Zyphix: zip ticks\n")

            self.assertNotEqual(batch_process.take_fingerprint(prompt, {}), original)

    def test_lexicon_maps_spoken_and_display_terms(self) -> None:
        lexicon = pronunciations.load_lexicon()
        spoken = pronunciations.to_spoken(
            "py-shinywidgets links shinywidgets, RDKit, MDTraj, rioxarray, and stdlib.",
            lexicon,
        )
        self.assertIn("pie shiny widgets", spoken)
        self.assertIn("Shiny Widgets", spoken)
        self.assertIn("R D Kit", spoken)
        self.assertIn("M D traj", spoken)
        self.assertIn("rio x array", spoken)
        self.assertIn("standard lib", spoken)
        self.assertEqual(
            pronunciations.to_display("Shiny Widgets and R D Kit via Rio xarray", lexicon),
            "shinywidgets and RDKit via rioxarray",
        )

    def test_cardinal_numbers_and_technical_names_do_not_duplicate_in_captions(self) -> None:
        spoken_text = "I click 3 to cut 1,797 digits to 183. shinywidgets updates in Python."
        heard = [
            {"word": token, "start": i * 0.2, "end": (i + 1) * 0.2}
            for i, token in enumerate(
                "i click three to cut one thousand seven hundred ninety seven digits "
                "to one hundred eighty three shiny widgets updates in python".split()
            )
        ]
        report = align_narration.align(spoken_text, heard, 6.0)
        self.assertEqual(report["word_error_rate"], 0.0)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            (artifacts / "narration.txt").write_text(
                "Audio profile:\nDev.\nScene:\nDemo.\nDirector's notes:\nClear.\nTranscript:\n"
                + spoken_text,
                encoding="utf-8",
            )
            timing = artifacts / "narration-timing.json"
            timing.write_text(json.dumps(report), encoding="utf-8")
            words, _ = burn_captions.load_words(timing)
            rendered = " ".join(w["word"] for w in words)
            self.assertIn("1,797", rendered)
            self.assertIn("183.", rendered)
            self.assertIn("shinywidgets", rendered)
            self.assertNotIn("thousand", rendered)
            self.assertNotIn("hundred", rendered)

    def test_end_card_cutoff_uses_cut_lead_and_reel_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            video = artifacts / "clean.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=black:s=1440x2560:r=30:d=5",
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-t", "5", "-c:v", "libx264", "-c:a", "aac", str(video),
                ],
                check=True,
            )
            transcript = "Here is the result. To try this integration, go away."
            (artifacts / "narration.txt").write_text(
                f"Audio profile:\nDev.\nScene:\nDemo.\nDirector's notes:\nClear.\nTranscript:\n{transcript}",
                encoding="utf-8",
            )
            timing_data = {
                "narration_offset_seconds": 0.15,
                "words": [
                    {"word": "here", "sentence": 0, "start": 0.2, "end": 0.4},
                    {"word": "is", "sentence": 0, "start": 0.4, "end": 0.6},
                    {"word": "the", "sentence": 0, "start": 0.6, "end": 0.8},
                    {"word": "result", "sentence": 0, "start": 0.8, "end": 1.6},
                    {"word": "to", "sentence": 1, "start": 2.0, "end": 2.2},
                    {"word": "try", "sentence": 1, "start": 2.2, "end": 2.4},
                    {"word": "this", "sentence": 1, "start": 2.4, "end": 2.6},
                    {"word": "integration", "sentence": 1, "start": 2.6, "end": 3.0},
                    {"word": "go", "sentence": 1, "start": 3.0, "end": 3.2},
                    {"word": "away", "sentence": 1, "start": 3.2, "end": 3.5},
                ],
            }
            timing = artifacts / "narration-timing.json"
            timing.write_text(json.dumps(timing_data), encoding="utf-8")
            reel_json = artifacts / "reel.json"
            reel_json.write_text(
                json.dumps({"shots": [{"label": "End card", "start": 1.933, "end": 5.0}]}),
                encoding="utf-8",
            )
            out_video = artifacts / "captioned.mp4"
            out_srt = artifacts / "captioned.srt"
            rc = burn_captions.main([
                "--video", str(video),
                "--timing", str(timing),
                "--style", "series",
                "--accent", "#00BF7F",
                "--stop-at", "To try this",
                "--reel-json", str(reel_json),
                "--out-video", str(out_video),
                "--out-srt", str(out_srt),
            ])
            self.assertEqual(rc, 0)
            cues = validate_editorial.parse_srt(out_srt)
            self.assertTrue(cues)
            self.assertLessEqual(cues[-1][1], 1.904)
            ass = (artifacts / "captioned.ass").read_text(encoding="utf-8")
            style = next(line for line in ass.splitlines() if line.startswith("Style: Caption,"))
            fields = style.split(",")
            self.assertEqual(fields[3:5], ["&H00FFFFFF", "&H00FFFFFF"])
            self.assertEqual(fields[15], "4")  # A single panel behind the whole cue.
            self.assertNotIn(r"{\k", ass)


class CodeCardAndOverlayTest(unittest.TestCase):
    def test_basename_header_rejects_layout_copy_and_renders_overlay_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            app_dir = project / "app"
            app_dir.mkdir()
            (app_dir / "app.py").write_text("\n" * 117 + "def config():\n    cfg = grid.view_config()\n    return cfg\n")
            (app_dir / "app_portrait.py").write_text("x = 1\n")
            (project / "source-shots.yaml").write_text("""orientations: [vertical]
shots:
- cue: Read the view
  views:
    vertical:
      overlay_card: true
      code_theme: dark
      code_wrap: false
      accent: "#03C7E8"
      panels:
      - {kind: code, file: app/app.py, lines: [118, 120], highlight: 119}
""")
            result = prepare_editorial.prepare(project)
            view = result["shots"][0]["views"]["vertical"]
            html_doc = (project / view["file"]).with_suffix(".html").read_text()
            self.assertIn('<p class="filename">app.py</p>', html_doc)
            self.assertTrue((project / view["card_file"]).is_file())
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 720, "height": 1280})
                page.goto((project / view["file"]).with_suffix(".html").as_uri())
                num_box = page.locator("[data-highlight] .number").bounding_box()
                browser.close()
            assert num_box
            self.assertGreater(view["highlight"][0] * 720, num_box["x"] + num_box["width"])

            (project / "source-shots.yaml").write_text("""orientations: [vertical]
shots:
- cue: Read the view
  views:
    vertical:
      panels:
      - {kind: code, file: app/app_portrait.py, lines: [1, 1]}
""")
            with self.assertRaisesRegex(ValueError, "app_portrait.py"):
                prepare_editorial.prepare(project)

    def test_hook_badge_code_overlay_and_audio_bed_render_in_editorial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            audio = artifacts / "narration.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                stream.writeframes(
                    b"".join(struct.pack("<h", int(1200 * math.sin(i * 0.1))) for i in range(96000))
                )
            timing = {
                "audio_sha256": align_narration.sha256(audio),
                "duration_seconds": 4.0,
                "words": [
                    {"word": "start", "start": 0.0, "end": 0.5, "sentence": 0},
                    {"word": "code", "start": 2.0, "end": 2.6, "sentence": 1},
                ],
                "transcript_check": {"word_error_rate": 0, "vocalizations": []},
            }
            (artifacts / "narration-timing.json").write_text(json.dumps(timing))
            # Green live video with shifting bright rectangle so it has real motion.
            live = project / "live.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=green:s=144x256:r=30:d=6",
                    "-vf", "drawbox=x='10+20*t':y=120:w=24:h=24:color=white:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(live),
                ],
                check=True,
            )
            Image.new("RGB", (144, 256), "#202020").save(project / "cover.png")
            card = project / "card.png"
            Image.new("RGBA", (288, 80), (15, 25, 40, 245)).save(card)
            editorial_cfg = {
                "orientations": ["vertical"],
                "context": {
                    "layout": "showcase",
                    "label": "Shiny · K3D",
                    "title": "Test overlay badge",
                    "captures": {"vertical": "cover.png"},
                    "hook_badge": {"label": "Shiny · K3D", "title": "Overlay", "accent": "#03C7E8", "seconds": 1.6},
                },
                "shots": [
                    {
                        "cue": "start",
                        "chapter": "Hook",
                        "views": {"vertical": {"file": "live.mp4", "in": 0, "fit": "contain"}},
                    },
                    {
                        "cue": "code",
                        "chapter": "Code",
                        "views": {"vertical": {"file": "live.mp4", "in": 2.0, "fit": "contain", "code_overlay": "card.png", "code_position": "bottom"}},
                    },
                ],
            }
            (project / "editorial.yaml").write_text(yaml.safe_dump(editorial_cfg))
            (project / "reel.yaml").write_text(
                yaml.safe_dump({"style": "editorial", "orientation": "vertical", "title": "Test", "bed": "default", "outro": False, "features": [{"title": "Test", "dir": "."}]})
            )
            old_sizes = reel.SIZES
            try:
                reel.SIZES = {"vertical": (144, 256), "horizontal": (256, 144)}
                report = reel.build(project, "vertical")
                video = Path(report["reel"])
                self.assertTrue(video.is_file())
                # Badge sits at top ~1.8-6% at t=0.6s and clears by t=1.8s.
                early_top = frame_at(str(video), 0.6, project / "t06.png").getpixel((144, 20))
                late_top = frame_at(str(video), 1.75, project / "t175.png").getpixel((144, 20))
                self.assertNotEqual(early_top, late_top)
                # Overlay code card sits at bottom above 75% at t=2.6s.
                bottom_px = frame_at(str(video), 2.6, project / "t26.png").getpixel((144, 340))
                assert isinstance(bottom_px, tuple)
                self.assertGreater(bottom_px[2], bottom_px[1])
                checked = validate_editorial.validate_report(report, max_static_hold=4.0)
                self.assertEqual(checked["decode"], "passed")
            finally:
                reel.SIZES = old_sizes


class ValidationAndVoiceChecksTest(unittest.TestCase):
    def test_validate_editorial_flags_static_holds_and_caption_bleed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            frozen = project / "frozen.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=navy:s=144x256:r=30:d=8",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(frozen),
                ],
                check=True,
            )
            hold = validate_editorial.longest_static_hold(
                frozen, [{"start": 0.0, "end": 8.0, "source": "frozen.mp4"}], 144, 256
            )
            self.assertGreaterEqual(hold, 7.0)
            bad_srt = project / "bad.srt"
            bad_srt.write_text("1\n00:00:00,000 --> 00:00:04,500\nto 183. hundred\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Corrupted"):
                validate_editorial.check_captions(bad_srt, [])
            bleed_srt = project / "bleed.srt"
            bleed_srt.write_text("1\n00:00:00,000 --> 00:00:04,500\nClean text.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Caption bleed"):
                validate_editorial.check_captions(bleed_srt, [{"start": 4.2, "label": "End card", "source": "end-card.png"}])

    def test_series_voice_check_flags_repeated_i_openers_and_portrait_terms(self) -> None:
        def make(opener: str) -> str:
            return (
                "Audio profile:\nDev.\nScene:\nDemo.\nDirector's notes:\nClear.\nTranscript:\n"
                f"{opener} Then the card updates in Python. Quick update."
            )

        warnings = check_narration_voice.series_problems({
            "ep1": make("I click the terrain."),
            "ep2": make("I lasso the points."),
            "ep3": make("I draw a rectangle."),
            "ep4": make("The viewport filter narrows the list."),
        })
        self.assertTrue(any('open with "I <verb>' in w for w in warnings))
        portrait_warn = check_narration_voice.portrait_spatial_warnings(
            "Transcript:\nThe sidebar updates while the left viewer stays fixed beside the scene."
        )
        self.assertEqual(len(portrait_warn), 1)
        self.assertIn("sidebar", portrait_warn[0])

    def test_spoken_end_card_passes_validate_editorial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            artifacts = project / "artifacts"
            sources = project / "sources"
            artifacts.mkdir()
            sources.mkdir()
            audio = artifacts / "narration.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                stream.writeframes(
                    b"".join(struct.pack("<h", int(1200 * math.sin(i * 0.1))) for i in range(96000))
                )
            timing = {
                "audio_sha256": align_narration.sha256(audio),
                "duration_seconds": 4.0,
                "words": [
                    {"word": "start", "start": 0.0, "end": 0.5, "sentence": 0},
                    {"word": "to", "start": 2.2, "end": 2.4, "sentence": 1},
                    {"word": "try", "start": 2.4, "end": 2.7, "sentence": 1},
                    {"word": "this", "start": 2.7, "end": 3.0, "sentence": 1},
                ],
                "transcript_check": {"word_error_rate": 0, "vocalizations": []},
            }
            (artifacts / "narration-timing.json").write_text(json.dumps(timing))
            live = sources / "hook.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=navy:s=144x256:r=30:d=4",
                    "-vf", "drawbox=x='10+25*t':y=100:w=20:h=20:color=white:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(live),
                ],
                check=True,
            )
            Image.new("RGB", (144, 256), "#202020").save(sources / "cover.png")
            Image.new("RGB", (288, 512), "#1D1F21").save(sources / "end-card-vertical.png")
            editorial_cfg = {
                "orientations": ["vertical"],
                "context": {
                    "layout": "showcase",
                    "label": "Shiny · K3D",
                    "title": "Test spoken outro",
                    "captures": {"vertical": "sources/cover.png"},
                },
                "shots": [
                    {
                        "cue": "start",
                        "chapter": "Hook",
                        "views": {"vertical": {"file": "sources/hook.mp4", "in": 0, "fit": "contain"}},
                    },
                    {
                        "cue": "to try this",
                        "chapter": "Use the K3D integration in Shiny apps",
                        "views": {"vertical": {"file": "sources/end-card-vertical.png", "fit": "contain"}},
                    },
                ],
            }
            (project / "editorial.yaml").write_text(yaml.safe_dump(editorial_cfg))
            (project / "reel.yaml").write_text(
                yaml.safe_dump({
                    "style": "editorial",
                    "orientation": "vertical",
                    "title": "Test",
                    "outro": {"widget": "K3D", "command": "", "link": "shinywidgets.org", "spoken": "to try this"},
                    "features": [{"title": "Test", "dir": "."}],
                })
            )
            old_sizes = reel.SIZES
            try:
                reel.SIZES = {"vertical": (144, 256), "horizontal": (256, 144)}
                report = reel.build(project, "vertical")
                self.assertEqual(len(report["shots"]), 2)
                self.assertGreater(report["shots"][-1]["end"], report["shots"][-1]["start"])
                checked = validate_editorial.validate_report(report, max_static_hold=4.0)
                self.assertEqual(checked["decode"], "passed")
            finally:
                reel.SIZES = old_sizes


if __name__ == "__main__":
    unittest.main()
