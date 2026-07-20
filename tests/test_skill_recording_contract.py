import importlib.util
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/shiny-component-shorts"
CODEX_SKILL = SKILL / "SKILL.md"
CLAUDE_SKILL = ROOT / ".claude/skills/shiny-component-shorts/SKILL.md"
RECORDER_PATH = SKILL / "scripts/record_demo.py"
VALIDATOR_PATH = SKILL / "scripts/validate_demo.py"
TTS_PATH = SKILL / "scripts/generate_tts.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


recorder = load_module("skill_record_demo", RECORDER_PATH)
validator = load_module("skill_validate_demo", VALIDATOR_PATH)
tts = load_module("skill_generate_tts", TTS_PATH)


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

    def test_multi_video_series_requires_visual_variety(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        self.assertIn("one-line visual direction", skill)
        self.assertIn("both light and dark or color-led treatments", skill)
        self.assertIn("Series visual variety", playbook)
        self.assertIn("visual-direction matrix", playbook)
        self.assertIn("Do not count a recolor as a distinct hidden behavior", playbook)

    def test_apps_rotate_four_professional_fonts_and_omit_visible_titles(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        fonts = {
            "Mona Sans": "Mona+Sans:wght@400;500;600;700&display=swap",
            "IBM Plex Sans": "IBM+Plex+Sans:wght@400;500;600;700&display=swap",
            "Source Sans 3": "Source+Sans+3:wght@400;500;600;700&display=swap",
            "Manrope": "Manrope:wght@400;500;600;700&display=swap",
        }
        for source in (skill, playbook):
            for family, google_fonts_query in fonts.items():
                self.assertIn(family, source)
                self.assertIn(google_fonts_query, source)
            self.assertIn("Mona Sans → IBM Plex Sans → Source Sans 3 → Manrope", source)
            self.assertIn("one font family consistently", source)
            self.assertIn("visible app title, page title, eyebrow, kicker, series label", source)
            self.assertIn("problem-led hook", source)
        self.assertIn("--bs-body-font-family", skill)
        self.assertIn("tags$head", skill)
        self.assertIn("ui.tags.head", skill)
        self.assertIn("| Typography |", playbook)

    def test_existing_app_workflow_preserves_source_and_selects_one_behavior(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "### Existing app",
            "R Shiny or Shiny for Python",
            "Do not modify, copy, or restyle the existing app",
            "three meaningful action → reaction beats",
            "If no behavior passes the proof rule",
            "--app-dir",
            "sidecar",
        ):
            self.assertIn(marker, skill)
        self.assertIn("--app-dir", recording)
        self.assertIn("existing app remains unchanged", recording)

    def test_shiny_branding_safe_area_and_horizontal_code_contract(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        pacing = (SKILL / "references/short-form-pacing.md").read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(encoding="utf-8")
        tts = (SKILL / "references/tts-and-costs.md").read_text(encoding="utf-8")

        for source in (skill, playbook, pacing):
            self.assertIn("top 20%", source)
            self.assertIn("bottom 20%", source)
            self.assertIn("available horizontal space", source)
        for source in (skill, playbook, pacing, recording):
            self.assertIn("#007BC2", source)
            self.assertIn("#1D1F21", source)
            self.assertIn("#FFFFFF", source)
        self.assertIn("side-by-side", pacing)
        self.assertIn("side-by-side", recording)
        self.assertIn("Do not laugh, giggle, or chuckle", tts)

    def test_codex_metadata_is_present(self) -> None:
        metadata = SKILL / "agents/openai.yaml"
        self.assertTrue(metadata.is_file())
        text = metadata.read_text(encoding="utf-8")
        self.assertIn("$shiny-component-shorts", text)


class SharedRecorderContractTest(unittest.TestCase):
    def test_main_can_record_an_existing_app_into_a_sidecar_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "video"
            app_dir = root / "existing-app"
            project.mkdir()
            app_dir.mkdir()
            (project / "actions.yaml").write_text("actions: []\n", encoding="utf-8")
            calls = []
            original_argv = sys.argv
            original_record_project = recorder.record_project
            try:
                sys.argv = [
                    "record_demo.py",
                    "--project-dir",
                    str(project),
                    "--app-dir",
                    str(app_dir),
                    "--app-type",
                    "r",
                    "--port",
                    "8200",
                ]
                recorder.record_project = lambda *args: calls.append(args) or project / "demo.mp4"
                self.assertEqual(recorder.main(), 0)
            finally:
                sys.argv = original_argv
                recorder.record_project = original_record_project

        self.assertEqual(calls[0][0], project.resolve())
        self.assertEqual(calls[0][1], "r")
        self.assertEqual(calls[0][4], app_dir.resolve())
        self.assertEqual(calls[0][5], 8200)

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
                "drag",
                "select_option",
                "hover",
                "fill",
                "type",
                "press",
                "code",
                "zoom",
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
        self.assertEqual(recorder.code_hold_ms("x"), 5500)
        self.assertEqual(recorder.code_hold_ms("x" * 1000), 10000)
        self.assertEqual(recorder.code_hold_ms("x", 4321), 4321)

    def test_horizontal_code_uses_a_side_panel_and_shiny_palette(self) -> None:
        horizontal = recorder.code_overlay_config(
            "horizontal", {"title": "app.py", "text": "ui.input_slider(...)"}
        )
        vertical = recorder.code_overlay_config(
            "vertical", {"title": "app.py", "text": "ui.input_slider(...)"}
        )

        self.assertEqual(horizontal["layout"], "side")
        self.assertEqual(vertical["layout"], "overlay")
        self.assertIn("__demo_code_side__", recorder.CODE_OVERLAY_JS)
        self.assertIn("top:20%", recorder.CODE_OVERLAY_JS)
        self.assertIn("bottom:20%", recorder.CODE_OVERLAY_JS)
        self.assertNotIn("#4285f4", recorder.CURSOR_OVERLAY_JS + recorder.CODE_OVERLAY_JS)
        self.assertIn("#007bc2", (recorder.CURSOR_OVERLAY_JS + recorder.CODE_OVERLAY_JS).lower())
        self.assertIn(
            "const uiFont = getComputedStyle(document.body).fontFamily;",
            recorder.CODE_OVERLAY_JS,
        )
        self.assertNotIn("font:11px 'Mona Sans'", recorder.CODE_OVERLAY_JS)

    def test_occupied_port_is_refused_without_killing_listener(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen()
            self.assertFalse(recorder.port_is_available("127.0.0.1", port))
            self.assertEqual(listener.getsockname()[1], port)

    def test_port_override_preserves_url_path_query_and_fragment(self) -> None:
        self.assertEqual(
            recorder.url_with_port("http://localhost:8000/demo?x=1#state", 8200),
            "http://localhost:8200/demo?x=1#state",
        )

    def test_failed_typing_is_not_retried(self) -> None:
        class Locator:
            calls = 0

            def press_sequentially(self, value, delay):
                self.calls += 1
                raise RuntimeError("partial typing failure")

        class Page:
            def __init__(self):
                self.target = Locator()

            def eval_on_selector(self, *args):
                pass

            def locator(self, selector):
                return self.target

        page = Page()
        original_click = recorder.human_click
        try:
            recorder.human_click = lambda *args: None
            with self.assertRaisesRegex(RuntimeError, "partial typing failure"):
                recorder.run_actions(
                    page,
                    [{"type": {"selector": "#notes", "value": "hello"}}],
                    Path("."),
                )
        finally:
            recorder.human_click = original_click
        self.assertEqual(page.target.calls, 1)

    def test_cursor_overlay_cleanup_and_mp4_handling_are_bundled(self) -> None:
        source = RECORDER_PATH.read_text(encoding="utf-8")
        for marker in (
            "CURSOR_OVERLAY_JS",
            "CODE_OVERLAY_JS",
            "__code_activity_bar__",
            "__code_tab__",
            "__code_gutter__",
            "context.add_init_script(CURSOR_OVERLAY_JS)",
            "press_sequentially",
            "human_drag",
            "video.path()",
            "libx264",
            "--force-device-scale-factor=2",
            "viewport=viewport",
            '"-crf"',
            "terminate_process(proc)",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("kill -9", source)


class DemoValidatorContractTest(unittest.TestCase):
    def test_sidecar_validation_accepts_an_external_app_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "video"
            app_dir = root / "existing-app"
            project.mkdir()
            app_dir.mkdir()
            (app_dir / "app.R").write_text("shinyApp(ui, server)\n", encoding="utf-8")
            errors, _ = validator.validate_project(project, app_dir=app_dir)

        self.assertFalse(any("contain app.py or app.R" in error for error in errors))

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

    def test_validator_rejects_laughing_and_giggling_cues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "artifacts").mkdir()
            (project / "app.py").write_text("# test app\n", encoding="utf-8")
            (project / "actions.yaml").write_text(
                "actions:\n"
                "  - click: '#one'\n"
                "  - click: '#two'\n"
                "  - click: '#three'\n"
                "  - screenshot: {path: artifacts/final.png}\n",
                encoding="utf-8",
            )
            transcript = " ".join(["word"] * 60)
            (project / "artifacts/narration.txt").write_text(
                "Audio profile:\nCalm.\n\nScene:\nA demo.\n\n"
                "Director's notes:\nRead only the transcript.\n\nTranscript:\n"
                f"[short pause] {transcript} [laughing] [giggles]",
                encoding="utf-8",
            )
            errors, _ = validator.validate_project(project)

        self.assertTrue(any("laughing or giggling" in error for error in errors))

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
                self.assertEqual(report["video"]["width"], 1440)
                self.assertEqual(report["video"]["height"], 2560)

    def test_new_generated_demos_pass_validation(self) -> None:
        demos = [ROOT / "modal-shorts", ROOT / "tooltip-shorts"]
        if not all(demo.is_dir() for demo in demos):
            self.skipTest("New generated demos are not present in this checkout")
        for demo in demos:
            with self.subTest(demo=demo.name):
                errors, report = validator.validate_project(demo, require_audio=True)
                self.assertEqual(errors, [], f"{demo.name} validation failed: {errors}")




class GeminiTTSContractTest(unittest.TestCase):
    def test_generate_content_fallback_extracts_audio_and_usage(self) -> None:
        response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b"pcm"))]
                    )
                )
            ],
            usage_metadata=SimpleNamespace(
                prompt_token_count=123,
                candidates_token_count=456,
            ),
        )

        class Models:
            def generate_content(self, **kwargs):
                self.kwargs = kwargs
                return response

        models = Models()
        client = SimpleNamespace(models=models)
        pcm, input_tokens, output_tokens, source = tts.generate_pcm(
            client,
            model="gemini-3.1-flash-tts-preview",
            prompt="Read this",
            voice="Charon",
        )

        self.assertEqual(pcm, b"pcm")
        self.assertEqual(input_tokens, 123)
        self.assertEqual(output_tokens, 456)
        self.assertEqual(source, "Gemini Generate Content API fallback")
        self.assertEqual(models.kwargs["contents"], "Read this")

    def test_interactions_api_remains_preferred_when_available(self) -> None:
        interaction = SimpleNamespace(
            output_audio=SimpleNamespace(data="cGNt"),
            usage=SimpleNamespace(total_input_tokens=12, total_output_tokens=34),
        )

        class Interactions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return interaction

        interactions = Interactions()
        client = SimpleNamespace(interactions=interactions)
        pcm, input_tokens, output_tokens, source = tts.generate_pcm(
            client,
            model="gemini-3.1-flash-tts-preview",
            prompt="Read this",
            voice="Kore",
        )

        self.assertEqual(pcm, b"pcm")
        self.assertEqual((input_tokens, output_tokens), (12, 34))
        self.assertEqual(source, "Gemini Interactions API")
        self.assertEqual(interactions.kwargs["input"], "Read this")


if __name__ == "__main__":
    unittest.main()
