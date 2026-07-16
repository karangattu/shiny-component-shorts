import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/shiny-component-shorts"
SKILL_MD = SKILL / "SKILL.md"
RECORDER_PATH = SKILL / "scripts/record_demo.py"
VALIDATOR_PATH = SKILL / "scripts/validate_demo.py"

BASE_ACTIONS = {
    "wait_for",
    "wait",
    "click",
    "drag",
    "select_option",
    "hover",
    "fill",
    "type",
    "press",
    "code",
    "screenshot",
}
OVERLAY_ACTIONS = {"caption", "beat", "label"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


recorder = load_module("claude_record_demo", RECORDER_PATH)
validator = load_module("claude_validate_demo", VALIDATOR_PATH)


class ClaudeSkillContractTest(unittest.TestCase):
    def test_skill_is_compact_and_routes_to_focused_references(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 400)
        for reference in (
            "creative-playbook.md",
            "recording-contract.md",
            "short-form-pacing.md",
            "tts-and-costs.md",
        ):
            self.assertIn(reference, text)
            self.assertTrue((SKILL / "references" / reference).is_file())

    def test_skill_uses_bundled_scripts_instead_of_generating_them(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(".claude/skills/shiny-component-shorts/scripts/record_demo.py", text)
        self.assertIn(".claude/skills/shiny-component-shorts/scripts/validate_demo.py", text)
        self.assertIn("never generate a demo-specific recorder", text)
        self.assertNotIn("Generate `scripts/record_demo.py`", text)

    def test_skill_keeps_claude_specific_cost_reporting(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("claude_session_cost.py", text)
        self.assertTrue((SKILL / "scripts/claude_session_cost.py").is_file())

    def test_multi_video_series_requires_visual_variety(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        self.assertIn("one-line visual direction", skill)
        self.assertIn("both light and dark or color-led treatments", skill)
        self.assertIn("Series visual variety", playbook)
        self.assertIn("visual-direction matrix", playbook)
        self.assertIn("Do not count a recolor as a distinct hidden behavior", playbook)

    def test_apps_use_mona_sans_and_omit_visible_titles(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        for source in (skill, playbook):
            self.assertIn("Mona Sans", source)
            self.assertIn("Mona+Sans:wght@400;500;600;700&display=swap", source)
            self.assertIn("visible app title, page title, eyebrow, kicker, series label", source)
            self.assertIn("problem-led hook", source)
        self.assertIn("--bs-body-font-family", skill)

    def test_skill_mandates_clean_recordings_and_loudness_normalization(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("clean browser recording", text)
        self.assertIn("Do not add `beat`, `label`, or `caption` actions", text)
        self.assertIn("loudnorm=I=-14", text)


class ClaudeRecorderContractTest(unittest.TestCase):
    def test_recorder_supports_the_complete_action_contract(self) -> None:
        self.assertEqual(
            set(recorder.SUPPORTED_ACTIONS), BASE_ACTIONS | OVERLAY_ACTIONS
        )
        for name in sorted(BASE_ACTIONS | OVERLAY_ACTIONS):
            payload: object = "#selector"
            if name in {"drag", "select_option", "fill", "type", "press", "code", "screenshot"}:
                payload = {"selector": "#selector"}
            elif name == "wait":
                payload = 500
            elif name == "beat":
                payload = 1
            self.assertEqual(recorder.validate_action_shape({name: payload}), name)
        with self.assertRaises(ValueError):
            recorder.validate_action_shape({"unknown": "#x"})
        with self.assertRaises(ValueError):
            recorder.validate_action_shape({"click": "#a", "wait": 500})

    def test_recorder_source_includes_overlay_and_reliability_machinery(self) -> None:
        source = RECORDER_PATH.read_text(encoding="utf-8")
        for marker in (
            "CURSOR_OVERLAY_JS",
            "RETENTION_OVERLAY_JS",
            "__code_activity_bar__",
            "__code_tab__",
            "__code_gutter__",
            "__demo_hook__",
            "__demo_state_label__",
            "__demo_caption__",
            "__demo_beat_rail__",
            "window.__demo_overlays__",
            "collect_selectors",
            "start_app_with_retry",
            "human_drag",
            "libx264",
            "--force-device-scale-factor=2",
            "viewport=viewport",
            '"-crf"',
        ):
            self.assertIn(marker, source)
        self.assertNotIn("kill -9", source)

    def test_code_hold_formula(self) -> None:
        self.assertEqual(recorder.code_hold_ms(""), 5500)
        self.assertEqual(recorder.code_hold_ms("x" * 60), 3200 + 55 * 60)
        self.assertEqual(recorder.code_hold_ms("x" * 500), 10000)
        self.assertEqual(recorder.code_hold_ms("x" * 500, override=4200), 4200)

    def test_normalize_overlays_defaults_and_rejections(self) -> None:
        self.assertIsNone(recorder.normalize_overlays({}))
        overlays = recorder.normalize_overlays({"overlays": {"hook": "Why two sliders?"}})
        self.assertEqual(overlays["hook"], "Why two sliders?")
        self.assertEqual(overlays["beats"], list(recorder.DEFAULT_BEATS))
        self.assertEqual(overlays["accent"], recorder.DEFAULT_ACCENT)
        with self.assertRaises(ValueError):
            recorder.normalize_overlays({"overlays": {"hook": "  "}})
        with self.assertRaises(ValueError):
            recorder.normalize_overlays({"overlays": {"hook": "ok", "beats": []}})

    def test_resolve_beat_index_by_number_and_name(self) -> None:
        beats = ["Reveal", "Proof", "Code", "Payoff"]
        self.assertEqual(recorder.resolve_beat_index(2, beats), 1)
        self.assertEqual(recorder.resolve_beat_index("proof", beats), 1)
        with self.assertRaises(ValueError):
            recorder.resolve_beat_index(5, beats)
        with self.assertRaises(ValueError):
            recorder.resolve_beat_index("Outro", beats)
        with self.assertRaises(ValueError):
            recorder.resolve_beat_index(True, beats)

    def test_collect_selectors_exempts_wait_for_targets(self) -> None:
        actions = [
            {"wait_for": "#async-panel"},
            {"click": "#toggle"},
            {"click": "#async-panel"},
            {"hover": "#readout"},
            {"drag": {"selector": "#handle", "delta_x": 100}},
            {"type": {"selector": "#notes", "value": "hi"}},
            {"wait": 800},
            {"caption": "Watch the window move"},
            {"screenshot": {"path": "artifacts/final.png"}},
        ]
        self.assertEqual(
            recorder.collect_selectors(actions),
            ["#toggle", "#readout", "#handle", "#notes"],
        )

    def test_start_app_with_retry_retries_then_succeeds(self) -> None:
        attempts = []

        class FakeProc:
            def poll(self):
                return 0

        original_start = recorder.start_app
        original_wait = recorder.wait_for_server
        original_sleep = recorder.time.sleep
        try:
            recorder.start_app = lambda *args: FakeProc()
            recorder.time.sleep = lambda seconds: None

            def flaky_wait(url, timeout=30.0):
                attempts.append(url)
                if len(attempts) < 3:
                    raise RuntimeError("not up yet")

            recorder.wait_for_server = flaky_wait
            proc = recorder.start_app_with_retry(
                Path("."), "python", "127.0.0.1", 65500, "http://127.0.0.1:65500"
            )
            self.assertIsInstance(proc, FakeProc)
            self.assertEqual(len(attempts), 3)

            attempts.clear()

            def dead_wait(url, timeout=30.0):
                attempts.append(url)
                raise RuntimeError("never up")

            recorder.wait_for_server = dead_wait
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                recorder.start_app_with_retry(
                    Path("."), "python", "127.0.0.1", 65500, "http://127.0.0.1:65500"
                )
            self.assertEqual(len(attempts), 3)
        finally:
            recorder.start_app = original_start
            recorder.wait_for_server = original_wait
            recorder.time.sleep = original_sleep


class ClaudeValidatorContractTest(unittest.TestCase):
    def test_overlay_actions_are_supported_but_not_meaningful(self) -> None:
        self.assertTrue(OVERLAY_ACTIONS <= set(validator.SUPPORTED_ACTIONS))
        self.assertFalse(OVERLAY_ACTIONS & set(validator.MEANINGFUL_ACTIONS))

    def test_overlay_actions_add_settle_time_to_the_estimate(self) -> None:
        base = validator.estimate_action_seconds([{"click": "#a"}])
        with_overlays = validator.estimate_action_seconds(
            [{"click": "#a"}, {"caption": "hi"}, {"beat": 1}, {"label": "X"}]
        )
        self.assertAlmostEqual(with_overlays - base, 0.9)

    def test_missing_overlays_warn_but_do_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "app.py").write_text("app\n", encoding="utf-8")
            (project / "actions.yaml").write_text(
                "actions:\n"
                "  - click: '#a'\n"
                "  - click: '#b'\n"
                "  - click: '#c'\n"
                "  - screenshot: {path: 'artifacts/final.png'}\n",
                encoding="utf-8",
            )
            errors, report = validator.validate_project(project)
            warnings = report["warnings"]
            self.assertTrue(any("hook" in warning for warning in warnings))
            self.assertTrue(any("caption" in warning for warning in warnings))
            self.assertTrue(any("beat" in warning for warning in warnings))
            self.assertFalse(any("hook" in error for error in errors))

    def test_reference_demos_pass_the_claude_validator(self) -> None:
        for demo in ("slider-range-shorts", "toolbar-button-shorts"):
            project = ROOT / demo
            if not project.is_dir():
                continue
            errors, report = validator.validate_project(project, require_audio=True)
            self.assertEqual(errors, [], f"{demo} failed: {errors}")


if __name__ == "__main__":
    unittest.main()
