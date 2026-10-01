#!/usr/bin/env python3
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / ".agents" / "skills" / "shiny-component-shorts" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import batch_process  # noqa: E402
import check_local_voice  # noqa: E402
import check_narration_voice  # noqa: E402
import generate_tts  # noqa: E402
import narration_map  # noqa: E402


def make_project(root: Path, prompt: str) -> Path:
    project = root / "video"
    artifacts = project / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "narration.txt").write_text(prompt, encoding="utf-8")
    return project


class NarrationVoiceLintTest(unittest.TestCase):
    def test_good_script_passes_both_gates(self) -> None:
        prompt = check_narration_voice.GOOD_PROMPT

        self.assertEqual(check_narration_voice.voice_problems(prompt), [])
        self.assertEqual(generate_tts.validate_narration_prompt(prompt), [])

    def test_written_sounding_script_is_flagged_for_every_shape(self) -> None:
        flagged = " ".join(
            check_narration_voice.voice_problems(
                check_narration_voice.WRITTEN_SOUNDING_PROMPT
            )
        )

        for marker in (
            "[long pause]",
            "repeats back to back",
            "Banned stock phrase",
            "not just",
            "parallel cadence",
            "Em dashes",
            "three-item list",
            "within 4 words",
            'start with "watch"',
            "contraction",
            "fragment",
            "long sentence",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, flagged)

    def test_missing_transcript_section_is_reported(self) -> None:
        self.assertEqual(
            check_narration_voice.voice_problems("Audio profile:\nVoice.\n"),
            ["Narration prompt is missing the Transcript: section"],
        )

    def test_cli_reports_problems_and_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            narration = artifacts / "narration.txt"

            narration.write_text(
                check_narration_voice.WRITTEN_SOUNDING_PROMPT, encoding="utf-8"
            )
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                exit_code = check_narration_voice.main(["--project-dir", str(project)])
            self.assertEqual(exit_code, 1)
            self.assertIn("does not sound spoken yet", printed.getvalue())

            narration.write_text(check_narration_voice.GOOD_PROMPT, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                exit_code = check_narration_voice.main(["--project-dir", str(project)])
            self.assertEqual(exit_code, 0)
            self.assertIn("voice check passed", printed.getvalue())

    def test_self_test_passes(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_narration_voice.main(["--self-test"]), 0)

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_batch_narration_fails_before_any_synthesis_spend(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir), check_narration_voice.WRITTEN_SOUNDING_PROMPT)

            result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "FAILED")
            self.assertTrue(any("voice check" in error for error in result["errors"]))
            mock_run.assert_not_called()
            mock_measure.assert_not_called()

    @patch.object(batch_process, "measure_narration")
    @patch("subprocess.run")
    def test_batch_narration_says_nothing_about_imported_audio_wording(
        self, mock_run: MagicMock, mock_measure: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        mock_measure.return_value = {"duration_seconds": 10.0, "sentence_windows": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            project = make_project(Path(temp_dir), check_narration_voice.WRITTEN_SOUNDING_PROMPT)
            (project / "tts-settings.json").write_text(
                json.dumps({"audio_source": "narrated.mp4"}), encoding="utf-8"
            )
            (project / "narrated.mp4").write_bytes(b"video")
            artifacts = project / "artifacts"
            (artifacts / "narration.wav").write_bytes(b"wav")
            (artifacts / "narration.usage.json").write_text("{}", encoding="utf-8")

            result = batch_process.generate_narration(project, force=True)

            self.assertEqual(result["tts"], "SUCCESS", result["errors"])
            self.assertIn("import_narration.py", str(mock_run.call_args.args[0]))

    def test_both_skill_copies_ship_the_same_voice_lint(self) -> None:
        claude_copy = (
            ROOT_DIR / ".claude" / "skills" / "shiny-component-shorts" / "scripts"
            / "check_narration_voice.py"
        )
        self.assertEqual(
            (SCRIPTS_DIR / "check_narration_voice.py").read_text(encoding="utf-8"),
            claude_copy.read_text(encoding="utf-8"),
        )


class NarrationMapTest(unittest.TestCase):
    def make_timing_project(self, root: Path) -> Path:
        project = root / "demo"
        artifacts = project / "artifacts"
        artifacts.mkdir(parents=True)
        audio = artifacts / "narration.wav"
        audio.write_bytes(b"fake wav bytes")
        timing = {
            "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            "duration_seconds": 2.3,
            "words": [
                {"word": "watch", "sentence": 0, "start": 0.1, "end": 0.4, "matched": True},
                {"word": "the", "sentence": 0, "start": 0.4, "end": 0.5, "matched": True},
                {"word": "wire", "sentence": 0, "start": 0.5, "end": 0.9, "matched": True},
                {"word": "now", "sentence": 1, "start": 1.4, "end": 1.8, "matched": True},
                {"word": "again", "sentence": 1, "start": 1.8, "end": 2.3, "matched": True},
            ],
            "sentences": [
                {"text": "Watch the wire", "start": 0.1, "end": 0.9},
                {"text": "Now again", "start": 1.4, "end": 2.3},
            ],
        }
        (artifacts / "narration-timing.json").write_text(json.dumps(timing), encoding="utf-8")
        return project

    def test_map_prints_sentences_and_resolves_phrases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.make_timing_project(Path(temp_dir))
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                exit_code = narration_map.main(
                    ["--project-dir", str(project), "--phrase", "the wire"]
                )

            self.assertEqual(exit_code, 0)
            out = printed.getvalue()
            self.assertIn("Watch the wire", out)
            self.assertIn(
                "'the wire' (occurrence 1): narration 0.40-0.90s -> video 0.55s (sentence 1)",
                out,
            )

    def test_map_requires_measured_timing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "demo"
            (project / "artifacts").mkdir(parents=True)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                exit_code = narration_map.main(["--project-dir", str(project)])

            self.assertEqual(exit_code, 1)
            self.assertIn("No usable word timing", printed.getvalue())

    def test_narration_tools_are_documented(self) -> None:
        references = ROOT_DIR / ".agents" / "skills" / "shiny-component-shorts" / "references"
        recording = (references / "recording-contract.md").read_text(encoding="utf-8")
        tts_reference = (references / "tts-and-costs.md").read_text(encoding="utf-8")
        self.assertIn("narration_map.py", recording)
        self.assertIn("check_local_voice.py", tts_reference)
        self.assertIn("stale code", tts_reference)


class LocalVoiceDoctorTest(unittest.TestCase):
    def make_engine(self, root: Path) -> Path:
        engine = root / "local-voice-cloning"
        samples = engine / "voice_samples"
        samples.mkdir(parents=True)
        (samples / "karan.wav").write_bytes(b"reference voice")
        (samples / "karan.json").write_text(json.dumps({"transcript": "Hello there."}))
        return engine

    def run_doctor(self, engine: Path, health: dict, durations: tuple[float, float]) -> tuple[int, str]:
        def fake_multipart(url, fields, files, timeout=600.0):
            if url.endswith("/synthesize"):
                speed = float(fields["speed"])
                return {"x-duration-seconds": str(durations[0] if speed == 1.0 else durations[1])}, b"x" * 2048
            return {}, b""

        printed = io.StringIO()
        with patch.object(check_local_voice, "request_json", return_value=health), patch.object(
            check_local_voice, "request_multipart", side_effect=fake_multipart
        ), contextlib.redirect_stdout(printed):
            exit_code = check_local_voice.main(
                ["--engine-dir", str(engine), "--saved-voice", "karan"]
            )
        return exit_code, printed.getvalue()

    def test_stale_service_and_ignored_speed_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.make_engine(Path(temp_dir))

            exit_code, out = self.run_doctor(
                engine, {"status": "ok", "model_loaded": True}, (2.0, 2.1)
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("may be running stale code", out)
            self.assertIn("speed is not honored", out)
            self.assertIn("doctor: OK with", out)

    def test_current_service_with_working_speed_reports_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.make_engine(Path(temp_dir))

            exit_code, out = self.run_doctor(
                engine,
                {"status": "ok", "model_loaded": True, "version": "1.2.3"},
                (2.0, 3.5),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("version: 1.2.3", out)
            self.assertNotIn("speed is not honored", out)
            self.assertIn("doctor: OK", out)
            self.assertNotIn("warning", out.split("doctor: OK")[1])

    def test_unreachable_service_fails_with_startup_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.make_engine(Path(temp_dir))
            printed = io.StringIO()
            with patch.object(
                check_local_voice, "request_json", side_effect=OSError("refused")
            ), contextlib.redirect_stdout(printed):
                exit_code = check_local_voice.main(
                    ["--engine-dir", str(engine), "--saved-voice", "karan"]
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("uvicorn src.api:app", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
