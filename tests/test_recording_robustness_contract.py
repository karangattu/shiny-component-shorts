"""Reel transitions, app start failures, and the Shiny-ready wait, in both skill copies."""

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COPIES = [
    ROOT / ".claude/skills/shiny-component-shorts",
    ROOT / ".agents/skills/shiny-component-shorts",
]


def load(name: str, copy: Path) -> Any:
    sys.path.insert(0, str(copy / "scripts"))
    spec = importlib.util.spec_from_file_location(
        f"{name}_robust_{copy.parent.parent.name}", copy / "scripts" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mean_volume(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", f"{start}", "-t", f"{duration}", "-i", str(path),
         "-af", "volumedetect", "-vn", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    match = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", result.stderr)
    assert match, result.stderr
    return float(match.group(1))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class ReelLeadContractTest(unittest.TestCase):
    def test_feature_clips_hold_their_first_frame_through_the_transition(self) -> None:
        stitch = load("stitch_reel", COPIES[0])
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / "clip.mp4", Path(temp) / "piece.mp4"
            # A clip that speaks from its very first sample.
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=white:s=720x1280:r=30:d=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)],
                check=True,
            )
            lead = stitch.TRANSITION_SECONDS
            duration = stitch.normalize(source, output, "vertical", lead)
            self.assertAlmostEqual(duration, stitch.probe_duration(source) + lead, places=2)
            self.assertAlmostEqual(stitch.probe_duration(output), duration, delta=0.1)
            self.assertLess(mean_volume(output, 0.0, lead - 0.1), -60)
            self.assertGreater(mean_volume(output, lead + 0.1, 0.3), -30)

    def test_only_transitions_into_feature_clips_get_the_lead(self) -> None:
        for copy in COPIES:
            source = (copy / "scripts/stitch_reel.py").read_text()
            self.assertIn(
                "lead = TRANSITION_SECONDS if transition == TRANSITION_OUT else 0.0", source
            )
            self.assertIn("tpad=start_duration=", source)
            self.assertIn("adelay=", source)


class AppStartFailureContractTest(unittest.TestCase):
    def test_import_error_stops_retrying_and_quotes_the_app_output(self) -> None:
        for copy in COPIES:
            recorder = load("record_demo", copy)
            with self.subTest(copy=copy.parent.name), tempfile.TemporaryDirectory() as temp:
                app_dir = Path(temp)
                (app_dir / "app.py").write_text("import pandas_missing_for_test\n")
                port = recorder.find_available_port("127.0.0.1", 18400)
                with self.assertRaises(RuntimeError) as raised:
                    recorder.start_app_with_retry(
                        app_dir, "python", "127.0.0.1", port,
                        f"http://127.0.0.1:{port}", app_dir / "app.log",
                    )
                message = str(raised.exception)
                self.assertIn("after 1 attempt:", message)
                self.assertIn("exited with code", message)
                self.assertIn("ModuleNotFoundError: No module named 'pandas_missing_for_test'", message)
                self.assertIn("Last 20 lines of app output", message)

    def test_log_tail_keeps_the_last_lines(self) -> None:
        recorder = load("record_demo", COPIES[1])
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "app.log"
            log.write_text("".join(f"line {n}\n" for n in range(50)))
            tail = recorder.log_tail(log)
            self.assertEqual(tail.splitlines(), [f"line {n}" for n in range(30, 50)])
            self.assertEqual(recorder.log_tail(Path(temp) / "missing.log"), "")


if __name__ == "__main__":
    unittest.main()
