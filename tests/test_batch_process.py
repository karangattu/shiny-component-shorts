#!/usr/bin/env python3
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / ".agents" / "skills" / "shiny-component-shorts" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import batch_process
import build_cache


def make_project(root: Path, name: str = "video") -> Path:
    project = root / name
    project.mkdir()
    (project / "app.py").write_text("# app\n", encoding="utf-8")
    (project / "actions.yaml").write_text("actions: []\n", encoding="utf-8")
    artifacts = project / "artifacts"
    artifacts.mkdir()
    (artifacts / "narration.txt").write_text("Transcript:\nHello\n", encoding="utf-8")
    return project


class BuildCacheTest(unittest.TestCase):
    def test_cache_invalidates_when_an_input_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            source = project / "app.py"
            output = project / "demo.mp4"
            source.write_text("one", encoding="utf-8")
            output.write_text("video", encoding="utf-8")

            build_cache.update_cache(project, "recording", [source])
            self.assertTrue(build_cache.check_cache(project, "recording", [source], [output]))
            source.write_text("two", encoding="utf-8")
            self.assertFalse(build_cache.check_cache(project, "recording", [source], [output]))

    def test_project_inputs_exclude_generated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifact = project / "artifacts" / "demo.mp4"
            artifact.write_text("video", encoding="utf-8")

            inputs = build_cache.collect_project_inputs(project)

            self.assertIn(project / "app.py", inputs)
            self.assertIn(project / "actions.yaml", inputs)
            self.assertNotIn(artifact, inputs)


class BatchProcessTest(unittest.TestCase):
    def test_discover_projects_and_assign_distinct_port_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = make_project(root, "first")
            second = make_project(root, "second")

            self.assertEqual(batch_process.discover_projects(root), [first, second])
            self.assertEqual(batch_process.start_port_for(0), 8000)
            self.assertEqual(batch_process.start_port_for(1), 8100)
            with self.assertRaises(ValueError):
                batch_process.start_port_for(1000)

    def test_discover_projects_accepts_absolute_directory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = make_project(root, "absolute")

            self.assertEqual(
                batch_process.discover_projects(ROOT_DIR, [str(project)]),
                [project.resolve()],
            )

    def test_cli_has_two_phases_and_conservative_stage_defaults(self) -> None:
        narration = batch_process.parse_args(["--phase", "narration"])
        finish = batch_process.parse_args(["--phase", "finish"])

        self.assertEqual(narration.tts_concurrency, 3)
        self.assertEqual(finish.record_concurrency, 2)
        self.assertEqual(finish.merge_concurrency, 2)
        self.assertEqual(finish.validate_concurrency, 3)

    def test_narration_phase_runs_multiple_projects_concurrently(self) -> None:
        lock = threading.Lock()
        active = 0
        peak = 0

        def worker(project: Path, _force: bool) -> dict:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return batch_process.new_result(project)

        with patch.object(batch_process, "generate_narration", side_effect=worker):
            results = batch_process.run_narration_phase(
                [Path("one"), Path("two"), Path("three")],
                force=False,
                max_workers=3,
            )

        self.assertEqual(len(results), 3)
        self.assertGreaterEqual(peak, 2)

    def test_legacy_combined_flags_are_rejected_with_migration_guidance(self) -> None:
        with self.assertRaisesRegex(ValueError, "--phase narration"):
            batch_process.validate_cli_args(
                batch_process.parse_args(["--phase", "finish", "--tts", "--merge"])
            )

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_narration_phase_generates_measurements_and_then_uses_cache(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mock_measure.return_value = {
            "duration_seconds": 12.5,
            "sentence_windows": [{"start": 0.0, "end": 3.0}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            first = batch_process.generate_narration(project, force=True)
            second = batch_process.generate_narration(project, force=False)

            self.assertEqual(first["tts"], "SUCCESS")
            self.assertEqual(second["tts"], "CACHED")
            timing = json.loads((artifacts / "narration-timing.json").read_text())
            self.assertEqual(timing["duration_seconds"], 12.5)
            self.assertEqual(mock_run.call_count, 1)

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_narration_cache_and_command_include_per_video_tts_settings(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mock_measure.return_value = {"duration_seconds": 10.0, "sentence_windows": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            settings = project / "tts-settings.json"
            settings.write_text(
                json.dumps({"voice": "Kore", "model": "custom-tts"}),
                encoding="utf-8",
            )
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "SUCCESS")
            self.assertIn(settings, batch_process.narration_inputs(project))
            command = mock_run.call_args.args[0]
            self.assertEqual(command[command.index("--voice") + 1], "Kore")
            self.assertEqual(command[command.index("--model") + 1], "custom-tts")

    def test_timing_approval_is_bound_to_audio_timing_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration-timing.json").write_text("{}\n", encoding="utf-8")

            batch_process.approve_timing(project)
            self.assertTrue(batch_process.timing_is_approved(project))
            (project / "actions.yaml").write_text("actions:\n  - wait: 500\n", encoding="utf-8")
            self.assertFalse(batch_process.timing_is_approved(project))

    def test_finish_preflight_rejects_missing_or_unapproved_timing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            result = batch_process.new_result(project)

            self.assertFalse(batch_process.prepare_finish(project, result, approve=False))
            self.assertEqual(result["record"], "BLOCKED")
            self.assertTrue(any("timing approval" in error for error in result["errors"]))

    @patch("subprocess.run")
    def test_recording_cache_still_runs_validation(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifacts = project / "artifacts"
            for name, content in (
                ("narration.wav", "wav"),
                ("narration-timing.json", "{}"),
                ("demo.mp4", "video"),
                ("recording.json", "{}"),
                ("final.png", "png"),
                ("final_with_audio.mp4", "final"),
            ):
                (artifacts / name).write_text(content, encoding="utf-8")
            batch_process.approve_timing(project)
            inputs = batch_process.recording_inputs(project)
            build_cache.update_cache(project, "recording", inputs)

            result = batch_process.new_result(project)
            self.assertTrue(batch_process.prepare_finish(project, result, approve=False))
            batch_process.record_project(project, 8100, result, force=False)
            batch_process.validate_project(project, result)

            self.assertEqual(result["record"], "CACHED")
            self.assertEqual(result["validate"], "PASSED")
            self.assertEqual(mock_run.call_count, 1)
            self.assertIn("validate_demo.py", str(mock_run.call_args.args[0]))

    @patch("subprocess.run")
    def test_merge_invokes_quality_preserving_shared_script(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="merged", stderr="")
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "demo.mp4").write_bytes(b"video")
            (artifacts / "final_with_audio.mp4").write_bytes(b"final")
            result = batch_process.new_result(project)

            batch_process.merge_project(project, result, force=True)

            command = mock_run.call_args.args[0]
            self.assertEqual(result["merge"], "SUCCESS")
            self.assertIn("merge_audio.py", str(command))
            self.assertNotEqual(command[0], "ffmpeg")

    def test_stage_specific_inputs_invalidate_only_dependent_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            artifacts = project / "artifacts"
            for name in ("narration.wav", "narration-timing.json", "timing-approval.json"):
                (artifacts / name).write_text(name, encoding="utf-8")
            narration_inputs = batch_process.narration_inputs(project)
            recording_inputs = batch_process.recording_inputs(project)
            merge_inputs = batch_process.merge_inputs(project)

            self.assertIn(artifacts / "narration.txt", narration_inputs)
            self.assertNotIn(project / "app.py", narration_inputs)
            self.assertIn(project / "app.py", recording_inputs)
            self.assertIn(artifacts / "narration.wav", recording_inputs)
            self.assertIn(artifacts / "narration.wav", merge_inputs)
            self.assertNotIn(project / "actions.yaml", merge_inputs)

    def test_failure_or_blocked_stage_causes_batch_failure(self) -> None:
        result = batch_process.new_result(Path("video"))
        result["merge"] = "BLOCKED"
        self.assertTrue(batch_process.has_failures([result]))


if __name__ == "__main__":
    unittest.main()
