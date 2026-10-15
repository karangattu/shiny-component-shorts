import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COPIES = [ROOT / ".claude/skills/shiny-component-shorts", ROOT / ".agents/skills/shiny-component-shorts"]


def load(name: str, copy: Path = COPIES[0]):
    sys.path.insert(0, str(copy / "scripts"))
    spec = importlib.util.spec_from_file_location(
        f"{name}_{copy.parent.parent.name}_pair", copy / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def color_clip(path: Path, size: str, seconds: float = 1.0) -> Path:
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         f"color=c=blue:s={size}:d={seconds}", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path


def probe(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


class CompanionTest(unittest.TestCase):
    def make_demo(self, base: Path, orientation: str | None = None) -> Path:
        demo = base / "demo"
        (demo / "artifacts").mkdir(parents=True)
        (demo / "app.py").write_text("")
        config = {"actions": [{"click": "#go"}, {"wait": 500}]}
        if orientation:
            config = {"orientation": orientation, **config}
        (demo / "actions.yaml").write_text(yaml.safe_dump(config))
        (demo / "artifacts" / "narration.txt").write_text("Click go.")
        (demo / "artifacts" / "narration.wav").write_bytes(b"RIFF")
        (demo / "tts-settings.json").write_text(json.dumps({"music_bed": "bed.mp3", "audio_processing": "preserve"}))
        return demo

    def test_companion_flips_orientation_and_reuses_narration(self):
        for copy in COPIES:
            companion = load("companion", copy)
            with tempfile.TemporaryDirectory() as temp:
                demo = self.make_demo(Path(temp))
                target = companion.prepare_companion(demo)
                self.assertEqual(target, demo.resolve() / "artifacts" / "horizontal")
                config = yaml.safe_load((target / "actions.yaml").read_text())
                self.assertEqual(config["orientation"], "horizontal")
                self.assertEqual(config["actions"], [{"click": "#go"}, {"wait": 500}])
                self.assertEqual((target / "artifacts" / "narration.wav").read_bytes(), b"RIFF")
                settings = json.loads((target / "tts-settings.json").read_text())
                self.assertEqual(settings["music_bed"], str(demo.resolve() / "bed.mp3"))
                self.assertEqual(
                    companion.deliverable(demo), demo / "artifacts" / "final_with_audio-horizontal.mp4"
                )
                # Regenerating leaves unchanged files alone, and drops stale narration.
                stamp = (target / "actions.yaml").stat().st_mtime_ns
                (demo / "artifacts" / "narration.wav").unlink()
                companion.prepare_companion(demo)
                self.assertEqual((target / "actions.yaml").stat().st_mtime_ns, stamp)
                self.assertFalse((target / "artifacts" / "narration.wav").exists())
                self.assertEqual(companion.deliverable(demo), demo / "artifacts" / "demo-horizontal.mp4")

    def test_horizontal_primary_gets_a_vertical_companion(self):
        companion = load("companion")
        with tempfile.TemporaryDirectory() as temp:
            demo = self.make_demo(Path(temp), "horizontal")
            target = companion.prepare_companion(demo)
            self.assertEqual(target.name, "vertical")
            self.assertEqual(yaml.safe_load((target / "actions.yaml").read_text())["orientation"], "vertical")

    def test_companion_dir_stays_out_of_cache_inputs_and_discovery(self):
        build_cache = load("build_cache")
        batch = load("batch_process")
        companion = load("companion")
        with tempfile.TemporaryDirectory() as temp:
            demo = self.make_demo(Path(temp))
            companion.prepare_companion(demo)
            inputs = build_cache.collect_project_inputs(demo)
            self.assertFalse(any("artifacts" in path.relative_to(demo).parts for path in inputs))
            self.assertEqual(batch.discover_projects(Path(temp)), [demo])

    def test_batch_finish_records_the_companion(self):
        for copy in COPIES:
            batch = load("batch_process", copy)
            self.assertTrue(callable(batch.companion_project))
            result = batch.new_result(Path("demo"))
            self.assertEqual(result["companion"], "SKIPPED")
            result["companion"] = "FAILED"
            self.assertTrue(batch.has_failures([result]))
            source = (copy / "scripts/batch_process.py").read_text()
            self.assertIn("companion_project,", source)

    def test_skill_docs_require_both_orientations(self):
        for copy in COPIES:
            skill = (copy / "SKILL.md").read_text()
            self.assertIn("Every recorded video ships as a pair", skill)
            self.assertIn(f"{copy.relative_to(ROOT)}/scripts/companion.py", skill)
            self.assertEqual(
                (copy / "scripts/companion.py").read_text(),
                (COPIES[0] / "scripts/companion.py").read_text(),
            )


class EncodeLengthTest(unittest.TestCase):
    def test_screencast_encode_matches_the_recording_window(self):
        for copy in COPIES:
            recorder = load("record_demo", copy)
            with tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                frames = []
                for index, stamp in enumerate([100.0, 101.0, 102.0, 110.0]):
                    frame = work / f"f{index}.png"
                    subprocess.run(
                        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                         "color=c=red:s=64x64", "-frames:v", "1", str(frame)],
                        check=True,
                    )
                    frames.append((stamp, frame))
                for start, end in [(100.5, 103.0), (100.5, 112.0)]:
                    output = work / "out.mp4"
                    recorder.encode_screencast(frames, start, end, output, 64, 64)
                    self.assertAlmostEqual(probe(output), end - start, delta=0.05)


class ReelOrientationTest(unittest.TestCase):
    def test_segment_clip_picks_the_matching_orientation(self):
        stitch = load("stitch_reel")
        with tempfile.TemporaryDirectory() as temp:
            artifacts = Path(temp) / "seg" / "artifacts"
            artifacts.mkdir(parents=True)
            vertical = color_clip(artifacts / "final_with_audio.mp4", "72x128")
            feature = {"path": artifacts.parent}
            self.assertEqual(stitch.segment_clip(feature, "vertical"), vertical)
            self.assertIsNone(stitch.segment_clip(feature, "horizontal"))
            horizontal = color_clip(artifacts / "final_with_audio-horizontal.mp4", "128x72")
            self.assertEqual(stitch.segment_clip(feature, "horizontal"), horizontal)


if __name__ == "__main__":
    unittest.main()
