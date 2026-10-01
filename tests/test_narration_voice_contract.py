#!/usr/bin/env python3
import contextlib
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
import check_narration_voice  # noqa: E402
import generate_tts  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
