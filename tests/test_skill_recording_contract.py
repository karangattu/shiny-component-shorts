import contextlib
import importlib.util
import io
import json
import re
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_project  # noqa: E402  (needs the path insert above)

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/shiny-component-shorts"
CODEX_SKILL = SKILL / "SKILL.md"
CLAUDE_SKILL = ROOT / ".claude/skills/shiny-component-shorts/SKILL.md"
RECORDER_PATH = SKILL / "scripts/record_demo.py"
VALIDATOR_PATH = SKILL / "scripts/validate_demo.py"
REVIEW_PATH = SKILL / "scripts/review_frames.py"
TTS_PATH = SKILL / "scripts/generate_tts.py"


def load_module(name: str, path: Path) -> Any:
    """Load a script as a module; typed as Any because tests monkeypatch it."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder = load_module("skill_record_demo", RECORDER_PATH)
validator = load_module("skill_validate_demo", VALIDATOR_PATH)
review = load_module("skill_review_frames", REVIEW_PATH)
tts = load_module("skill_generate_tts", TTS_PATH)


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


class CodexSkillContractTest(unittest.TestCase):
    def test_skill_is_compact_and_routes_to_focused_references(self) -> None:
        text = CODEX_SKILL.read_text(encoding="utf-8")
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

    def test_dont_do_this_workflow_is_documented(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Don't do this, do this instead", skill)
        self.assertIn("Anti-pattern comparison (Don't do this -> Do this instead)", playbook)

    def test_recording_contract_forbids_shiny_client_error_panels(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        recording = (SKILL / "references/recording-contract.md").read_text(
            encoding="utf-8"
        )
        for source in (skill, recording):
            self.assertIn("Shiny Client Errors", source)
            self.assertIn("unique output IDs", source)
            self.assertIn("blocking failure", source)

    def test_generated_demo_projects_are_disposable_not_test_fixtures(self) -> None:
        ignore_lines = {
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertIn("/generated/", ignore_lines)
        self.assertIn("/*-shorts/", ignore_lines)
        self.assertIn("**/artifacts/", ignore_lines)

        for skill_path in (CODEX_SKILL, CLAUDE_SKILL):
            skill = skill_path.read_text(encoding="utf-8")
            self.assertIn("generated/demo-name", skill)
            self.assertIn("never add generated demo directories", skill)

        named_demo_path = re.compile(r"Path\(\s*['\"][^/'\"]+-shorts(?:/|['\"])")
        offenders = [
            path.name
            for path in (ROOT / "tests").glob("test_*.py")
            if named_demo_path.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

    def test_multi_video_series_requires_visual_variety(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        playbook = (SKILL / "references/creative-playbook.md").read_text(encoding="utf-8")
        self.assertIn("one-line visual direction", skill)
        self.assertIn("both light and dark or color-led treatments", skill)
        self.assertIn("Series visual variety", playbook)
        self.assertIn("visual-direction matrix", playbook)
        self.assertIn("Do not count a recolor as a distinct hidden behavior", playbook)

    def test_multi_video_series_documents_hybrid_two_phase_production(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
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

    def test_changeset_workflow_covers_every_supported_repo(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
        changeset = (SKILL / "references/changeset-sourcing.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("### Changeset: pull request, commit, or SHA", skill)
        for repo in ("rstudio/shiny", "posit-dev/py-shiny", "posit-dev/shinychat"):
            for source in (skill, changeset):
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
            ".agents/skills/shiny-component-shorts/scripts/record_demo.py", changeset
        )
        self.assertNotIn(".claude/skills", changeset)
        self.assertIn("inspect.signature", changeset)
        self.assertIn("just landed", changeset)

    def test_shinychat_demos_stay_offline_and_keyless(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
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

    def test_skill_budgets_the_session_as_well_as_the_video(self) -> None:
        skill = CODEX_SKILL.read_text(encoding="utf-8")
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
        self.assertNotIn(".claude/skills", recording)
        self.assertTrue(REVIEW_PATH.is_file())

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
        self.assertEqual(recorder.code_hold_ms("x" * 1000), 11000)
        self.assertEqual(
            recorder.code_hold_ms("x" * 60, context="y" * 100),
            3200 + 55 * 60 + 14 * 100,
        )
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
        self.assertIn("cfg.title + ' — Visual Studio Code'", source)
        self.assertNotIn("Shiny component short", source)

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

    def test_wordmark_renders_as_is_and_only_flips_on_dark_backdrops(self) -> None:
        from playwright.sync_api import sync_playwright

        logo = recorder.logo_overlay_config("vertical", recorder.resolve_logo_path())
        painted = {}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 720, "height": 1280})
            context.add_init_script(f"({recorder.LOGO_OVERLAY_JS})({json.dumps(logo)})")
            page = context.new_page()
            backdrops = (("light", "#F8F8F8"), ("dark", "#1D1F21"), ("blue", "#007BC2"))
            for name, background in backdrops:
                # Quoted so the color's `#` cannot be read as a URL fragment.
                page.goto(
                    "data:text/html,"
                    + quote(
                        f"<body style='margin:0;background:{background}'>"
                        "<div style='height:1400px'></div></body>"
                    )
                )
                page.wait_for_selector("#__demo_logo__", state="attached", timeout=5000)
                page.wait_for_timeout(700)
                painted[name] = page.eval_on_selector(
                    "#__demo_logo__", "el => el.style.filter"
                )
            box = page.eval_on_selector(
                "#__demo_logo__", "el => el.getBoundingClientRect().toJSON()"
            )
            tag = page.eval_on_selector("#__demo_logo__", "el => el.tagName")
            context.close()
            browser.close()

        # The artwork ships untouched except where a dark backdrop hides it.
        self.assertEqual(tag, "IMG")
        self.assertEqual(painted["light"], "none")
        self.assertEqual(painted["dark"], "invert(1)")
        self.assertEqual(painted["blue"], "invert(1)")
        # Phone-legible, in proportion, inside the reserved top-left band.
        self.assertEqual(round(box["width"]), 168)
        self.assertLess(box["height"], box["width"])
        self.assertLess(box["bottom"], 1280 * 0.2)
        self.assertLess(box["right"], 720 * 0.4)

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

    def test_preflight_checks_shapes_and_selectors_before_a_browser_starts(self) -> None:
        run = {"orientation": "vertical"}
        actions = [
            {"wait_for": "#async-panel"},
            {"click": "#toggle"},
            {"press": "#notes"},
        ]
        problems = recorder.action_shape_problems(actions, run)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("Action 3", problems[0])
        self.assertIn("selector", problems[0])
        # A wait_for target is declared asynchronous, so it is not demanded up front.
        self.assertEqual(recorder.collect_selectors(actions[:2]), ["#toggle"])
        self.assertEqual(recorder.deferred_selectors(actions), ["#async-panel"])
        self.assertEqual(recorder.viewport_size("vertical"), (720, 1280))
        self.assertEqual(recorder.viewport_size("horizontal"), (1280, 720))

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

    def test_unbranded_recordings_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            recording_path = built.artifacts / "recording.json"
            recording = json.loads(recording_path.read_text(encoding="utf-8"))
            self.assertTrue(recording.pop("logo"))
            recording_path.write_text(json.dumps(recording), encoding="utf-8")
            errors, _ = validator.validate_project(built.project)

        self.assertTrue(
            any("no Shiny wordmark" in error for error in errors), errors
        )

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

    def test_complete_vertical_demo_passes_every_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            for name in (
                "app.py",
                "actions.yaml",
                "artifacts/narration.txt",
                "artifacts/narration.wav",
                "artifacts/demo.mp4",
                "artifacts/final.png",
                "artifacts/final_with_audio.mp4",
            ):
                self.assertTrue((built.project / name).is_file(), f"{name} missing")
            errors, report = validator.validate_project(built.project, require_audio=True)

        self.assertEqual(errors, [])
        self.assertGreaterEqual(report["meaningful_actions"], 3)
        self.assertEqual(report["video"]["width"], 1440)
        self.assertEqual(report["video"]["height"], 2560)
        self.assertAlmostEqual(
            report["measured_narration_seconds"], built.narration_seconds, places=1
        )

    def test_sentence_windows_come_from_the_silences_in_the_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(Path(temp_dir))
            windows = validator.narration_sentence_windows(
                built.artifacts / "narration.wav"
            )

        self.assertEqual(len(windows), len(built.windows))
        for measured, expected in zip(windows, built.windows):
            self.assertAlmostEqual(measured["start"], expected["start"], places=1)
            self.assertAlmostEqual(measured["end"], expected["end"], places=1)

    def test_horizontal_demo_requires_landscape_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), orientation="horizontal"
            )
            errors, report = validator.validate_project(built.project, require_audio=True)

        self.assertEqual(errors, [])
        self.assertEqual((report["video"]["width"], report["video"]["height"]), (2560, 1440))

    def test_wrong_resolution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), resolution=(720, 1280)
            )
            errors, _ = validator.validate_project(built.project)

        self.assertTrue(
            any("expected 1440x2560" in error for error in errors), errors
        )

    def test_video_must_outlive_the_narration_by_one_to_three_seconds(self) -> None:
        for pad in (0.1, 5.0):
            with self.subTest(pad=pad), tempfile.TemporaryDirectory() as temp_dir:
                built = demo_project.build_demo_project(
                    Path(temp_dir), video_pad_seconds=pad
                )
                errors, _ = validator.validate_project(built.project)
                self.assertTrue(
                    any("past the narration" in error for error in errors), errors
                )

    def test_actions_after_the_narration_ends_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(Path(temp_dir), timeline=[])
            late = demo_project.default_timeline()
            narration_end = built.windows[-1]["end"]
            late.append(
                {"action": "click", "start": narration_end + 1.0, "end": narration_end + 1.5}
            )
            (built.artifacts / "recording.json").write_text(
                json.dumps({"action_timeline": late}), encoding="utf-8"
            )
            errors, _ = validator.validate_project(built.project)

        self.assertTrue(
            any("after the narration ends" in error for error in errors), errors
        )


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
            report = json.loads(
                (built.artifacts / "validation.json").read_text(encoding="utf-8")
            )

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


class SharedReviewSheetTest(unittest.TestCase):
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

    def test_sheet_tiles_every_required_frame_at_phone_width(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(
                Path(temp_dir), timeline=demo_project.default_timeline()
            )
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = review.main(["--project-dir", str(built.project)])
            width, height = review.frame_size(built.artifacts / "review.png")

        self.assertEqual(exit_code, 0)
        tile_height = round(review.PHONE_WIDTH * 2560 / 1440)
        # Four 9:16 frames in a 2x2 grid, each at phone width.
        self.assertEqual((width, height), (2 * review.PHONE_WIDTH, 2 * tile_height))

    def test_missing_recording_fails_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                exit_code = review.main(["--project-dir", temp_dir])

        self.assertEqual(exit_code, 1)
        self.assertIn("Could not build the review sheet", printed.getvalue())

    def test_both_skill_copies_ship_the_same_review_sheet(self) -> None:
        claude_copy = ROOT / ".claude/skills/shiny-component-shorts/scripts/review_frames.py"
        self.assertEqual(
            REVIEW_PATH.read_text(encoding="utf-8"),
            claude_copy.read_text(encoding="utf-8"),
        )


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

    def test_missing_narrated_outputs_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            built = demo_project.build_demo_project(Path(temp_dir), with_audio=False)
            errors, _ = validator.validate_project(built.project, require_audio=True)

        self.assertTrue(any("narration.wav" in error for error in errors), errors)
        self.assertTrue(any("final_with_audio.mp4" in error for error in errors), errors)

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

        short_prompt = (
            "Audio profile:\nVoice.\n\nScene:\nScene.\n\nDirector's notes:\nNotes.\n\n"
            "Transcript:\nToo short text [short pause] [medium pause] [long pause]."
        )
        errors = tts.validate_narration_prompt(short_prompt)
        self.assertTrue(any("60–85 spoken words" in e for e in errors))

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
