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

import batch_process  # noqa: E402
import build_cache  # noqa: E402


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

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_local_voice_provider_resolves_a_saved_voice_and_uses_the_local_adapter(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mock_measure.return_value = {"duration_seconds": 10.0, "sentence_windows": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = make_project(root)
            engine = root / "local-voice-cloning"
            samples = engine / "voice_samples"
            samples.mkdir(parents=True)
            saved_voice = samples / "karan.wav"
            saved_voice.write_bytes(b"reference voice")
            (project / "tts-settings.json").write_text(
                json.dumps(
                    {
                        "provider": "local-voice-cloning",
                        "saved_voice": "karan",
                        "engine_dir": str(engine),
                        "quality": "high",
                        "language": "English",
                    }
                ),
                encoding="utf-8",
            )
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "SUCCESS", result["errors"])
            self.assertIn(saved_voice, batch_process.narration_inputs(project))
            command = mock_run.call_args.args[0]
            self.assertIn("generate_local_voice.py", str(command))
            self.assertEqual(
                command[command.index("--reference") + 1], str(saved_voice)
            )
            self.assertEqual(command[command.index("--quality") + 1], "high")
            self.assertEqual(command[command.index("--language") + 1], "English")

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_local_voice_provider_accepts_a_reference_voice_with_its_transcript(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mock_measure.return_value = {"duration_seconds": 10.0, "sentence_windows": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = make_project(root)
            reference = root / "speaker.m4a"
            reference.write_bytes(b"reference voice")
            engine = root / "local-voice-cloning"
            engine.mkdir()
            (project / "tts-settings.json").write_text(
                json.dumps(
                    {
                        "provider": "local-voice-cloning",
                        "reference_voice": str(reference),
                        "reference_text": "The exact words spoken in the sample.",
                        "engine_dir": str(engine),
                    }
                ),
                encoding="utf-8",
            )
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "SUCCESS", result["errors"])
            self.assertIn(reference, batch_process.narration_inputs(project))
            command = mock_run.call_args.args[0]
            self.assertEqual(command[command.index("--reference") + 1], str(reference))
            self.assertEqual(
                command[command.index("--ref-text") + 1],
                "The exact words spoken in the sample.",
            )

    def test_saved_voice_must_be_a_name_not_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir))
            (project / "tts-settings.json").write_text(
                json.dumps(
                    {
                        "provider": "local-voice-cloning",
                        "saved_voice": "../speaker",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "saved_voice.*name"):
                batch_process.load_tts_settings(project)

    def test_default_saved_voice_and_adjustable_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            path = project / "tts-settings.json"
            settings = {"provider": "local-voice-cloning", "api_url": "http://127.0.0.1:8001", "speaking_rate": 1.0}
            path.write_text(json.dumps(settings))
            self.assertEqual(batch_process.load_tts_settings(project)["saved_voice"], "karan")
            for bad in (0, 0.4, 0.49, 1.51, 1.6, 2, 3, True, "fast"):
                path.write_text(json.dumps({**settings, "speaking_rate": bad}))
                with self.assertRaises(ValueError):
                    batch_process.load_tts_settings(project)
            for good in (0.5, 0.75, 0.9, 1.0, 1.25, 1.5):
                path.write_text(json.dumps({**settings, "speaking_rate": good}))
                self.assertEqual(batch_process.load_tts_settings(project)["speaking_rate"], good)
            for good in (0, 120, 160.5):
                path.write_text(json.dumps({**settings, "max_wpm": good}))
                self.assertEqual(batch_process.load_tts_settings(project)["max_wpm"], good)
            for bad in (-1, True, "fast"):
                path.write_text(json.dumps({**settings, "max_wpm": bad}))
                with self.assertRaises(ValueError):
                    batch_process.load_tts_settings(project)

    def test_local_voice_command_forwards_speed_and_pace_gate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = make_project(root)
            engine = root / "local-voice-cloning"
            samples = engine / "voice_samples"
            samples.mkdir(parents=True)
            saved_voice = samples / "karan.wav"
            saved_voice.write_bytes(b"reference voice")
            (project / "tts-settings.json").write_text(
                json.dumps(
                    {
                        "provider": "local-voice-cloning",
                        "saved_voice": "karan",
                        "engine_dir": str(engine),
                        "speaking_rate": 0.9,
                        "max_wpm": 150,
                    }
                ),
                encoding="utf-8",
            )
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            with patch.object(batch_process, "measure_narration") as mock_measure, patch(
                "subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
                mock_measure.return_value = {"duration_seconds": 10.0, "sentence_windows": []}
                result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "SUCCESS", result["errors"])
            command = mock_run.call_args.args[0]
            self.assertEqual(command[command.index("--speaking-rate") + 1], "0.9")
            self.assertEqual(command[command.index("--max-wpm") + 1], "150")

    def test_voice_change_invalidates_approval_and_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            artifacts = project / "artifacts"
            for name in ("narration.wav", "narration-timing.json", "narration.usage.json"):
                (artifacts / name).write_text("data")
            reference = project / "voice.wav"
            reference.write_bytes(b"reference")
            settings = {"provider": "local-voice-cloning", "reference_voice": "voice.wav"}
            path = project / "tts-settings.json"
            path.write_text(json.dumps(settings))
            build_cache.update_cache(project, "tts", batch_process.narration_inputs(project))
            self.assertTrue(batch_process.prepare_finish(project, batch_process.new_result(project), True))
            path.write_text(json.dumps({**settings, "quality": "fast"}))
            self.assertFalse(batch_process.timing_is_approved(project))
            result = batch_process.new_result(project)
            self.assertFalse(batch_process.prepare_finish(project, result, True))
            self.assertIn("stale", str(result["errors"]))

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
            commands = [str(call.args[0]) for call in mock_run.call_args_list]
            # The recording came from cache; validation and the review sheet did not.
            self.assertEqual(len(commands), 2)
            self.assertIn("validate_demo.py", commands[0])
            self.assertIn("review_frames.py", commands[1])

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
