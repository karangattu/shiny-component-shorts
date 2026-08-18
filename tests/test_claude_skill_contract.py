import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_project  # noqa: E402  (needs the path insert above)

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/shiny-component-shorts"
SKILL_MD = SKILL / "SKILL.md"
RECORDER_PATH = SKILL / "scripts/record_demo.py"
VALIDATOR_PATH = SKILL / "scripts/validate_demo.py"
REVIEW_PATH = SKILL / "scripts/review_frames.py"
TTS_PATH = SKILL / "scripts/generate_tts.py"

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


def load_module(name: str, path: Path) -> Any:
    """Load a script as a module; typed as Any because tests monkeypatch it."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder = load_module("claude_record_demo", RECORDER_PATH)
validator = load_module("claude_validate_demo", VALIDATOR_PATH)
review = load_module("claude_review_frames", REVIEW_PATH)
tts = load_module("claude_generate_tts", TTS_PATH)


def run_main(module: Any, argv: list[str]) -> tuple[int, str]:
    """Run a script's main() with argv, capturing what it prints."""
    original_argv = sys.argv
    printed = io.StringIO()
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(printed):
            exit_code = module.main()
    finally:
        sys.argv = original_argv
    return exit_code, printed.getvalue()


class ClaudeSkillContractTest(unittest.TestCase):
    def test_skill_is_compact_and_routes_to_focused_references(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertLess(len(text.splitlines()), 400)
        for reference in (
            "creative-playbook.md",
            "recording-contract.md",
            "short-form-pacing.md",
            "tts-and-costs.md",
            "changeset-sourcing.md",
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

    def test_dont_do_this_workflow_is_documented(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Don't do this, do this instead", skill)
        self.assertIn("Anti-pattern comparison (Don't do this -> Do this instead)", playbook)

    def test_contextual_code_window_is_documented_across_repo_contracts(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "Focus the decisive code line; keep any real source context dimmed",
            skill,
        )
        for marker in ("syntax-highlighted", "before", "after", "start_line"):
            self.assertIn(marker, recording)
        self.assertIn("syntax-highlighted code card", readme)
        self.assertIn("real source context", readme)

    def test_recording_contract_forbids_shiny_client_error_panels(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(
            encoding="utf-8"
        )
        for source in (skill, recording):
            self.assertIn("Shiny Client Errors", source)
            self.assertIn("unique output IDs", source)
            self.assertIn("blocking failure", source)

    def test_multi_video_series_requires_visual_variety(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        self.assertIn("one-line visual direction", skill)
        self.assertIn("both light and dark or color-led treatments", skill)
        self.assertIn("Series visual variety", playbook)
        self.assertIn("visual-direction matrix", playbook)
        self.assertIn("Do not count a recolor as a distinct hidden behavior", playbook)

    def test_multi_video_series_documents_hybrid_two_phase_production(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        for marker in (
            "lead agent",
            "up to three subagents",
            "--phase narration",
            "--phase finish --approve-timing",
            "--record-concurrency 2",
            "narration-timing.json",
            "merge_audio.py",
            "verify every requested output independently",
        ):
            self.assertIn(marker, skill)

    def test_apps_rotate_four_professional_fonts_and_omit_visible_titles(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
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
        skill = SKILL_MD.read_text(encoding="utf-8")
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

    def test_changeset_workflow_covers_every_supported_repo(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        changeset = (SKILL / "references/changeset-sourcing.md").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("### Changeset: pull request, commit, or SHA", skill)
        for repo in ("rstudio/shiny", "posit-dev/py-shiny", "posit-dev/shinychat"):
            for source in (skill, changeset, readme):
                self.assertIn(repo, source)
        for marker in (
            "gh pr view",
            "gh api repos/owner/repo/commits/<sha>",
            "pkg-py",
            "pkg-r",
            "one video",
            "not in the diff",
        ):
            self.assertIn(marker, skill + changeset)
        self.assertIn("Never manufacture a demo for an internal change", skill)
        self.assertIn("changeset.md", skill)

    def test_changeset_demos_run_the_changed_build_not_the_release(self) -> None:
        changeset = (SKILL / "references/changeset-sourcing.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("git+https://github.com/posit-dev/py-shiny@<sha>", changeset)
        self.assertIn("not `#subdirectory=pkg-py`", changeset)
        self.assertIn('pak::pak("posit-dev/shinychat/pkg-r@<sha>")', changeset)
        self.assertIn("sys.executable -m shiny run", changeset)
        self.assertIn(
            ".claude/skills/shiny-component-shorts/scripts/record_demo.py", changeset
        )
        self.assertIn("inspect.signature", changeset)
        self.assertIn("just landed", changeset)

    def test_shinychat_demos_stay_offline_and_keyless(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        changeset = (SKILL / "references/changeset-sourcing.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("never call a real LLM", skill)
        self.assertIn("shinychat", skill)
        for marker in (
            "Never point a demo at a real LLM",
            "append_message_stream",
            "chat_append",
            "Chat history requires a client",
            "_user_input",
            'width="100%"',
        ):
            self.assertIn(marker, changeset)

    def test_shiny_branding_safe_area_and_horizontal_code_contract(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
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

    def test_skill_budgets_the_session_as_well_as_the_video(self) -> None:
        skill = SKILL_MD.read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Session and context budget", skill)
        for marker in (
            "video per session",
            "subagent",
            "--dry-run",
            "review_frames.py",
            "artifacts/validation.json",
        ):
            self.assertIn(marker, skill)
        for marker in (
            "## Preflight",
            "## Review sheet",
            "artifacts/preflight.png",
            "artifacts/review.png",
            "artifacts/validation.json",
        ):
            self.assertIn(marker, recording)
        self.assertTrue(REVIEW_PATH.is_file())

    def test_skill_mandates_clean_recordings_and_loudness_normalization(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("clean browser recording", text)
        self.assertIn("Do not add `beat`, `label`, or `caption` actions", text)
        self.assertIn("merge_audio.py", text)
        self.assertIn("-14 LUFS", text)


class ClaudeRecorderContractTest(unittest.TestCase):
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
                    "python",
                    "--port",
                    "8200",
                ]
                recorder.record_project = lambda *args: calls.append(args) or project / "demo.mp4"
                self.assertEqual(recorder.main(), 0)
            finally:
                sys.argv = original_argv
                recorder.record_project = original_record_project

        self.assertEqual(calls[0][0], project.resolve())
        self.assertEqual(calls[0][1], "python")
        self.assertEqual(calls[0][4], app_dir.resolve())
        self.assertEqual(calls[0][5], 8200)

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

    def test_dry_run_preflights_instead_of_recording(self) -> None:
        clean = {
            "app_dir": "/tmp/app",
            "app_type": "python",
            "url": "http://127.0.0.1:8000",
            "orientation": "vertical",
            "selectors": ["#seven"],
            "deferred": ["#label"],
            "screenshot": "artifacts/preflight.png",
            "phone_screenshot": "artifacts/preflight-phone.png",
            "app_log": "artifacts/preflight-app.log",
            "problems": [],
        }
        broken = {**clean, "problems": ["Selectors not found on the initial page: #x"]}

        for report, expected_code, expected_text in (
            (clean, 0, "Preflight OK"),
            (broken, 1, "Preflight FAILED"),
        ):
            with self.subTest(problems=report["problems"]), tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir)
                (project / "app.py").write_text("# app\n", encoding="utf-8")
                (project / "actions.yaml").write_text("actions: []\n", encoding="utf-8")
                calls = []
                original_preflight = recorder.preflight_project
                original_record = recorder.record_project
                try:
                    recorder.preflight_project = (
                        lambda *args: calls.append(args) or report
                    )
                    recorder.record_project = lambda *args: self.fail(
                        "--dry-run must not record"
                    )
                    exit_code, printed = run_main(
                        recorder,
                        ["record_demo.py", "--project-dir", str(project), "--dry-run"],
                    )
                finally:
                    recorder.preflight_project = original_preflight
                    recorder.record_project = original_record

                self.assertEqual(exit_code, expected_code)
                self.assertEqual(len(calls), 1)
                self.assertIn(expected_text, printed)
                self.assertFalse((project / "artifacts" / "demo.mp4").exists())

    def test_preflight_reports_action_problems_before_starting_a_browser(self) -> None:
        run = {"orientation": "vertical", "overlays": None}
        actions = [
            {"click": "#go"},
            {"press": "#notes"},
            {"caption": "hello"},
            {"code": {"title": "app.py"}},
        ]
        problems = recorder.action_shape_problems(actions, run)

        self.assertEqual(len(problems), 3, problems)
        self.assertIn("Action 2", problems[0])
        self.assertIn("selector", problems[0])
        self.assertIn("Action 3", problems[1])
        self.assertIn("overlays", problems[1])
        self.assertIn("Action 4", problems[2])
        self.assertEqual(recorder.action_shape_problems([{"click": "#go"}], run), [])

    def test_preflight_defers_wait_for_targets_and_sizes_the_viewport(self) -> None:
        actions = [
            {"wait_for": "#async-panel"},
            {"click": "#toggle"},
            {"wait_for": "#async-panel"},
        ]
        self.assertEqual(recorder.deferred_selectors(actions), ["#async-panel"])
        self.assertEqual(recorder.viewport_size("vertical"), (720, 1280))
        self.assertEqual(recorder.viewport_size("horizontal"), (1280, 720))

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
        self.assertIn("cfg.title + ' — Visual Studio Code'", source)
        self.assertNotIn("Shiny component short", source)
        self.assertNotIn("kill -9", source)

    def test_every_recording_is_stamped_with_the_shiny_wordmark(self) -> None:
        asset = SKILL / "assets/shiny-logo.png"
        self.assertTrue(asset.is_file())
        self.assertGreater(asset.stat().st_size, 0)
        self.assertEqual(recorder.resolve_logo_path(), asset.resolve())

        vertical = recorder.logo_overlay_config("vertical", asset)
        horizontal = recorder.logo_overlay_config("horizontal", asset)
        self.assertTrue(vertical["src"].startswith("data:image/png;base64,"))
        self.assertEqual((vertical["top"], vertical["left"]), ("4%", "8%"))
        self.assertEqual(vertical["width"], 168)
        self.assertEqual(horizontal["width"], 190)
        self.assertEqual(vertical["darkThreshold"], 0.5)
        self.assertNotIn("color", vertical)
        with self.assertRaises(ValueError):
            recorder.logo_overlay_config("square", asset)
        with self.assertRaises(FileNotFoundError):
            recorder.resolve_logo_path(Path("does-not-exist.png"))

        source = RECORDER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'context.add_init_script(f"({LOGO_OVERLAY_JS})({json.dumps(logo)})")', source
        )
        self.assertIn('"logo": {', source)

    def test_wordmark_matches_the_shared_recorder_exactly(self) -> None:
        """Both skill copies must stamp the same mark at the same size."""
        shared = load_module(
            "shared_record_demo",
            ROOT / ".agents/skills/shiny-component-shorts/scripts/record_demo.py",
        )
        self.assertEqual(recorder.LOGO_OVERLAY_JS, shared.LOGO_OVERLAY_JS)
        self.assertEqual(recorder.LOGO_WIDTHS, shared.LOGO_WIDTHS)
        self.assertEqual(recorder.LOGO_INSET, shared.LOGO_INSET)
        self.assertEqual(recorder.LOGO_DARK_THRESHOLD, shared.LOGO_DARK_THRESHOLD)
        self.assertEqual(
            recorder.resolve_logo_path().read_bytes(),
            shared.resolve_logo_path().read_bytes(),
        )

    def test_code_hold_formula(self) -> None:
        self.assertEqual(recorder.code_hold_ms(""), 5500)
        self.assertEqual(recorder.code_hold_ms("x" * 60), 3200 + 55 * 60)
        self.assertEqual(
            recorder.code_hold_ms("x" * 60, context="y" * 100),
            3200 + 55 * 60 + 14 * 100,
        )
        self.assertEqual(recorder.code_hold_ms("x" * 500), 11000)
        self.assertEqual(recorder.code_hold_ms("x" * 500, override=4200), 4200)

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

    def test_code_overlay_accepts_real_context_around_the_focus_line(self) -> None:
        config = recorder.code_overlay_config(
            "vertical",
            {
                "title": "app.py",
                "before": "@render.ui\ndef retry_state():\n",
                "text": "    attempt = input.retry()\n",
                "after": "    checks = (...)\n    completed = min(attempt, 3)\n",
                "start_line": 117,
            },
        )

        self.assertEqual(config["before"], "@render.ui\ndef retry_state():")
        self.assertEqual(config["text"], "    attempt = input.retry()")
        self.assertEqual(
            config["after"], "    checks = (...)\n    completed = min(attempt, 3)"
        )
        self.assertEqual(config["startLine"], 117)
        self.assertEqual(config["language"], "python")

    def test_code_overlay_marks_a_syntax_highlighted_vscode_focus_line(self) -> None:
        source = recorder.CODE_OVERLAY_JS

        for marker in (
            "highlightCode",
            "__code_focus_block__",
            "__code_status_bar__",
            "tok-keyword",
            "tok-string",
            "tok-comment",
            "Visual Studio Code",
            "cfg.before",
            "cfg.after",
            "cfg.startLine",
        ):
            self.assertIn(marker, source)

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

    def test_shiny_client_error_panel_stops_recording(self) -> None:
        class Page:
            def evaluate(self, script):
                return (
                    "Shiny Client Errors\nDuplicate output IDs were found\n"
                    "The following IDs were used for more than one output: plot"
                )

        with self.assertRaisesRegex(RuntimeError, "Duplicate output IDs"):
            recorder.assert_no_shiny_client_errors(Page())

    def test_shiny_client_error_guard_remembers_a_removed_panel(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context()
            context.add_init_script(recorder.SHINY_CLIENT_ERROR_GUARD_JS)
            page = context.new_page()
            page.set_content("<main>Demo</main>")
            page.evaluate(
                """() => {
                    const panel = document.createElement('section');
                    panel.textContent =
                        'Shiny Client Errors Duplicate output IDs were found: plot';
                    document.body.appendChild(panel);
                    panel.remove();
                }"""
            )
            with self.assertRaisesRegex(RuntimeError, "Duplicate output IDs"):
                recorder.assert_no_shiny_client_errors(page)
            context.close()
            browser.close()


class ClaudeValidatorContractTest(unittest.TestCase):
    def test_sidecar_validation_accepts_an_external_app_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "video"
            app_dir = root / "existing-app"
            project.mkdir()
            app_dir.mkdir()
            (app_dir / "app.py").write_text("# existing app\n", encoding="utf-8")
            errors, _ = validator.validate_project(project, app_dir=app_dir)

        self.assertFalse(any("contain app.py or app.R" in error for error in errors))

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

    def test_narrated_demo_passes_the_claude_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            errors, report = validator.validate_project(built.project, require_audio=True)

        self.assertEqual(errors, [])
        self.assertGreaterEqual(report["meaningful_actions"], 3)
        self.assertEqual(report["video"]["width"], 1440)
        self.assertEqual(report["video"]["height"], 2560)
        self.assertEqual(len(report["narration_sentences"]), len(built.windows))

    def test_console_gets_a_summary_and_the_full_report_goes_to_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            argv = [
                "validate_demo.py",
                "--project-dir",
                str(built.project),
                "--require-audio",
            ]
            exit_code, printed = run_main(validator, argv)
            _, as_json = run_main(validator, argv + ["--json"])
            report_path = built.artifacts / "validation.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        # Everything is still recorded, just not in the reader's face.
        self.assertIn("action_timeline", report)
        self.assertIn("narration_sentences", report)
        self.assertNotIn("action_timeline", printed)
        self.assertIn("validation.json", printed)
        self.assertLess(len(printed), len(as_json))
        self.assertIn("action_timeline", as_json)
        # The timing comparison arrives resolved instead of as two arrays.
        self.assertIn("timing (visible action → narration sentence)", printed)
        self.assertIn("sentence 1", printed)

    def test_timing_lines_flag_an_action_outside_every_sentence(self) -> None:
        report = {
            "action_timeline": [
                {"action": "click", "start": 0.2, "end": 1.0},
                {"action": "wait", "start": 1.0, "end": 2.0},
                {"action": "code", "start": 30.0, "end": 40.0},
            ],
            "narration_sentences": [
                {"start": 0.0, "end": 3.0},
                {"start": 3.6, "end": 6.2},
            ],
        }
        lines = validator.timing_lines(report)

        # Waits are not visible reactions, so they stay out of the comparison.
        self.assertEqual(len(lines), 2)
        self.assertIn("sentence 1", lines[0])
        self.assertIn("no sentence", lines[1])
        self.assertEqual(validator.timing_lines({}), [])

    def test_claude_validator_matches_the_shared_validator_verdict(self) -> None:
        """Both skill copies must judge the same project identically."""
        shared = load_module(
            "shared_validate_demo",
            ROOT / ".agents/skills/shiny-component-shorts/scripts/validate_demo.py",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), resolution=(720, 1280)
            )
            claude_errors, _ = validator.validate_project(built.project)
            shared_errors, _ = shared.validate_project(built.project)

        self.assertEqual(claude_errors, shared_errors)
        self.assertTrue(
            any("expected 1440x2560" in error for error in claude_errors), claude_errors
        )


class ClaudeReviewSheetTest(unittest.TestCase):
    def test_marks_follow_the_recorded_reveal_and_code_beats(self) -> None:
        timeline = [
            {"action": "wait", "start": 0.0, "end": 1.0},
            {"action": "click", "start": 1.0, "end": 2.0},
            {"action": "click", "start": 4.0, "end": 5.0},
            {"action": "code", "start": 10.0, "end": 20.0},
        ]
        marks = dict(review.review_marks(timeline, 30.0))

        self.assertEqual(marks["first"], 0.4)
        # Just after the first reaction completes, and inside the code hold.
        self.assertEqual(marks["reveal"], 2.6)
        self.assertEqual(marks["code"], 16.0)
        self.assertEqual(marks["final"], 29.7)

    def test_marks_fall_back_to_even_spacing_without_a_timeline(self) -> None:
        marks = review.review_marks([], 30.0)

        self.assertEqual(
            [name for name, _ in marks], ["first", "reveal", "code", "final"]
        )
        self.assertEqual(dict(marks)["reveal"], 10.0)
        self.assertEqual(dict(marks)["code"], 20.0)

    def test_sheet_tiles_every_required_frame_at_phone_width(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = review.main(["--project-dir", str(built.project)])
            sheet = built.artifacts / "review.png"
            width, height = review.frame_size(sheet)

        self.assertEqual(exit_code, 0)
        tile_height = round(review.PHONE_WIDTH * 2560 / 1440)
        # Four 9:16 frames in a 2x2 grid, each at phone width.
        self.assertEqual((width, height), (2 * review.PHONE_WIDTH, 2 * tile_height))

    def test_sheet_accepts_explicit_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(Path(temp_dir))
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = review.main(
                    [
                        "--project-dir",
                        str(built.project),
                        "--images",
                        "artifacts/final.png",
                        "--output",
                        "artifacts/one.png",
                    ]
                )
            width, _ = review.frame_size(built.artifacts / "one.png")

        self.assertEqual(exit_code, 0)
        self.assertEqual(width, review.PHONE_WIDTH)

    def test_missing_recording_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                exit_code = review.main(["--project-dir", temp_dir])

        self.assertEqual(exit_code, 1)
        self.assertIn("Could not build the review sheet", printed.getvalue())

    def test_logo_overlay_contains_content_collision_detection(self) -> None:
        self.assertIn("hasCollision", recorder.LOGO_OVERLAY_JS)
        self.assertIn("elementsFromPoint", recorder.LOGO_OVERLAY_JS)
        self.assertIn("logo.style.opacity = '0'", recorder.LOGO_OVERLAY_JS)
        self.assertIn("logo.style.opacity = '1'", recorder.LOGO_OVERLAY_JS)

    def test_recorder_uses_fast_encoding_preset(self) -> None:
        script_text = RECORDER_PATH.read_text(encoding="utf-8")
        self.assertIn('"-preset"', script_text)
        self.assertIn('"fast"', script_text)

    def test_generate_tts_validates_prompt_statically(self) -> None:
        valid_prompt = (
            "Audio profile:\nA clear developer voice.\n\n"
            "Scene:\nTesting the app.\n\n"
            "Director's notes:\nFast pace, no laughing.\n\n"
            "Transcript:\n"
            "Why is your Shiny text box three lines tall? [short pause] "
            "Typing more lines makes this field grow smoothly while the other scrolls inside the container. "
            "Clearing it returns the box to its starting size. [medium pause] "
            "Here is the exact code that controls the auto resize behavior in your dashboard. "
            "Notice how simple this one parameter makes your layout and design. [slightly firmer] "
            "That is the whole change."
        )
        self.assertEqual(tts.validate_narration_prompt(valid_prompt), [])

        laugh_prompt = valid_prompt.replace("[short pause]", "[laughs]")
        errors = tts.validate_narration_prompt(laugh_prompt)
        self.assertTrue(any("laughing or giggling" in e for e in errors))

    def test_validate_demo_supports_timing_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(Path(temp_dir), with_audio=False)
            (built.project / "artifacts" / "demo.mp4").unlink(missing_ok=True)
            (built.project / "artifacts" / "final.png").unlink(missing_ok=True)

            errors, report = validator.validate_project(
                built.project, simulate_timing=True
            )
            self.assertTrue(report.get("simulated_timing"))
            self.assertIn("action_timeline", report)
            self.assertIn("narration_sentences", report)
            summary = validator.summary_lines(report)
            self.assertTrue(any("simulated timing" in line for line in summary))


if __name__ == "__main__":
    unittest.main()
