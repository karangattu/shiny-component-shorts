import importlib.util
import socket
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/shiny-component-shorts"
CODEX_SKILL = SKILL / "SKILL.md"
CLAUDE_SKILL = ROOT / ".claude/skills/shiny-component-shorts/SKILL.md"
RECORDER_PATH = SKILL / "scripts/record_demo.py"
VALIDATOR_PATH = SKILL / "scripts/validate_demo.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


recorder = load_module("skill_record_demo", RECORDER_PATH)
validator = load_module("skill_validate_demo", VALIDATOR_PATH)


class CodexSkillContractTest(unittest.TestCase):
    def test_skill_is_compact_and_routes_to_focused_references(self) -> None:
        text = CODEX_SKILL.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 400)
        for reference in (
            "creative-playbook.md",
            "recording-contract.md",
            "short-form-pacing.md",
            "tts-and-costs.md",
        ):
            self.assertIn(reference, text)
            self.assertTrue((SKILL / "references" / reference).is_file())

    def test_codex_skill_is_intentionally_independent_from_claude(self) -> None:
        codex = CODEX_SKILL.read_text(encoding="utf-8")
        claude = CLAUDE_SKILL.read_text(encoding="utf-8")
        self.assertNotEqual(codex, claude)
        self.assertNotIn("claude_session_cost.py", codex)
        self.assertFalse((SKILL / "scripts/claude_session_cost.py").exists())

    def test_creative_contract_requires_visible_proof(self) -> None:
        text = CODEX_SKILL.read_text(encoding="utf-8")
        self.assertIn("direct comparison", text)
        self.assertIn("two-way proof", text)
        self.assertIn("three meaningful actions", text)
        self.assertIn("Default to a true 9:16 vertical composition", text)

    def test_codex_metadata_is_present(self) -> None:
        metadata = SKILL / "agents/openai.yaml"
        self.assertTrue(metadata.is_file())
        text = metadata.read_text(encoding="utf-8")
        self.assertIn("$shiny-component-shorts", text)


class SharedRecorderContractTest(unittest.TestCase):
    def test_orientation_precedence_and_default(self) -> None:
        self.assertEqual(recorder.resolve_orientation(None, {}), "vertical")
        self.assertEqual(
            recorder.resolve_orientation(None, {"orientation": "horizontal"}),
            "horizontal",
        )
        self.assertEqual(
            recorder.resolve_orientation("vertical", {"orientation": "horizontal"}),
            "vertical",
        )
        with self.assertRaises(ValueError):
            recorder.resolve_orientation(None, {"orientation": "square"})

    def test_recorder_supports_the_complete_action_contract(self) -> None:
        self.assertEqual(
            recorder.SUPPORTED_ACTIONS,
            {
                "wait_for",
                "wait",
                "click",
                "select_option",
                "hover",
                "fill",
                "type",
                "press",
                "code",
                "screenshot",
            },
        )
        for action in recorder.SUPPORTED_ACTIONS:
            self.assertEqual(recorder.validate_action_shape({action: None}), action)
        with self.assertRaises(ValueError):
            recorder.validate_action_shape({"wait": 1, "click": "#x"})
        with self.assertRaises(ValueError):
            recorder.validate_action_shape({"paste": "#x"})

    def test_code_hold_uses_reading_time_and_bounds(self) -> None:
        self.assertEqual(recorder.code_hold_ms("x"), 3500)
        self.assertEqual(recorder.code_hold_ms("x" * 1000), 8000)
        self.assertEqual(recorder.code_hold_ms("x", 4321), 4321)

    def test_occupied_port_is_refused_without_killing_listener(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen()
            self.assertFalse(recorder.port_is_available("127.0.0.1", port))
            self.assertEqual(listener.getsockname()[1], port)

    def test_cursor_overlay_cleanup_and_mp4_handling_are_bundled(self) -> None:
        source = RECORDER_PATH.read_text(encoding="utf-8")
        for marker in (
            "CURSOR_OVERLAY_JS",
            "CODE_OVERLAY_JS",
            "context.add_init_script(CURSOR_OVERLAY_JS)",
            "press_sequentially",
            "video.path()",
            "libx264",
            "terminate_process(proc)",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("kill -9", source)


class DemoValidatorContractTest(unittest.TestCase):
    def test_timing_estimator_includes_typing_and_code_reading(self) -> None:
        actions = [
            {"wait": 1000},
            {"click": "#go"},
            {"type": {"selector": "#notes", "value": "abcd", "delay": 50}},
            {"code": {"text": "x", "duration": 4000, "type_ms": 20}},
        ]
        self.assertAlmostEqual(validator.estimate_action_seconds(actions), 7.22)

    def test_narration_estimate_counts_spoken_words_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "narration.txt"
            path.write_text(
                "Director notes.\nTranscript:\n[curious] one two three [amazed] four five",
                encoding="utf-8",
            )
            words, tags, seconds = validator.narration_metrics(path)
        self.assertEqual(words, 5)
        self.assertEqual(tags, 2)
        self.assertEqual(seconds, 6.0)

    def test_validator_rejects_a_bare_transcript_and_long_idle_waits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "artifacts").mkdir()
            (project / "app.py").write_text("# test app\n", encoding="utf-8")
            (project / "actions.yaml").write_text(
                "actions:\n"
                "  - wait: 3800\n"
                "  - click: '#one'\n"
                "  - click: '#two'\n"
                "  - click: '#three'\n"
                "  - screenshot: {path: artifacts/final.png}\n",
                encoding="utf-8",
            )
            (project / "artifacts/narration.txt").write_text(
                "[curious] This is only a transcript.", encoding="utf-8"
            )
            errors, _ = validator.validate_project(project)
        self.assertTrue(any("over 3000 ms" in error for error in errors))
        self.assertTrue(any("missing required sections" in error for error in errors))

    def test_audio_requirement_reports_missing_audio_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            errors, _ = validator.validate_project(Path(temp_dir), require_audio=True)
        self.assertTrue(any("narration.wav" in error for error in errors))
        self.assertTrue(any("final_with_audio.mp4" in error for error in errors))

    def test_claude_reference_demos_pass_without_modification(self) -> None:
        demos = [ROOT / "textarea-shorts", ROOT / "checkbox-group-shorts"]
        if not all(demo.is_dir() for demo in demos):
            self.skipTest("Claude reference demos are not present in this checkout")
        for demo in demos:
            with self.subTest(demo=demo.name):
                errors, report = validator.validate_project(demo)
                self.assertEqual(errors, [])
                self.assertGreaterEqual(report["meaningful_actions"], 3)
                self.assertEqual(report["video"]["width"], 720)
                self.assertEqual(report["video"]["height"], 1280)


if __name__ == "__main__":
    unittest.main()
