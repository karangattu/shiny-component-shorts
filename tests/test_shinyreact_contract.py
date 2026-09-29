"""Frontend recording contracts shared by both shipped skills."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [ROOT / folder / "skills/shiny-component-shorts" for folder in (".agents", ".claude")]


def load_script(skill: Path, script: str) -> Any:
    spec = importlib.util.spec_from_file_location(script, skill / "scripts" / f"{script}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShinyReactContractTest(unittest.TestCase):
    def test_both_skills_route_shinyreact_requests(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertIn("references/shinyreact.md", (skill / "SKILL.md").read_text())
                self.assertIn("posit-dev/shinyreact", (skill / "references/changeset-sourcing.md").read_text())
                self.assertTrue((skill / "references/shinyreact.md").is_file())

    def test_frontend_cards_validate_against_the_selected_app_source(self) -> None:
        for skill in SKILLS:
            validator = load_script(skill, "validate_demo")
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                app = root / "app"
                project = root / "video"
                (app / "www").mkdir(parents=True)
                project.mkdir()
                (app / "app.py").write_text("server_only = True\n")
                (app / "www/ui.js").write_text('function Demo() {\n  const count = useShinyOutputValue("count", 0);\n}\n')
                (root / "outside.js").write_text("outside();\n")
                (app / "www/link.js").symlink_to(root / "outside.js")
                base = {"source_file": "www/ui.js", "title": "React UI", "text": '  const count = useShinyOutputValue("count", 0);'}
                cases = [
                    (base, None),
                    ({**base, "before": "// A server value"}, None),
                    ({**base, "text": "server_only = True"}, "not in the app source"),
                    ({**base, "before": "function Demo() {", "text": base["text"].strip()}, "indentation"),
                    ({**base, "source_file": "www/missing.js"}, "cannot read code source_file"),
                    ({**base, "source_file": "../outside.js"}, "inside the app directory"),
                    ({**base, "source_file": str(root / "outside.js")}, "inside the app directory"),
                    ({**base, "source_file": "www/link.js"}, "inside the app directory"),
                    ({**base, "source_file": ""}, "non-empty relative path"),
                    ({**base, "source_file": None}, "non-empty relative path"),
                    ({"text": "server_only = True"}, None),
                    ({"title": "www/ui.js", "text": base["text"]}, "not in the app source"),
                ]
                for card, expected in cases:
                    with self.subTest(card=card):
                        (project / "actions.yaml").write_text(yaml.safe_dump({"actions": [{"code": card}]}))
                        errors, _ = validator.validate_project(project, app_dir=app)
                        code_errors = [error for error in errors if error.startswith("Action 1")]
                        if expected:
                            self.assertTrue(any(expected in error for error in code_errors), errors)
                        else:
                            self.assertEqual(code_errors, [])

    def test_frontend_edits_invalidate_recording_cache(self) -> None:
        for skill in SKILLS:
            cache = load_script(skill, "build_cache")
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                sources = ["app.py", "src/ui.tsx", "www/ui.js", "www/ui.css", "package-lock.json"]
                for name in sources + ["node_modules/react/index.js", "artifacts/demo.mp4"]:
                    path = project / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("original")
                inputs = cache.collect_project_inputs(project)
                self.assertEqual(set(inputs), {project / name for name in sources})
                output = project / "artifacts/demo.mp4"
                for name in sources:
                    cache.update_cache(project, "recording", inputs)
                    self.assertTrue(cache.check_cache(project, "recording", inputs, [output]))
                    (project / name).write_text("changed")
                    self.assertFalse(cache.check_cache(project, "recording", inputs, [output]))

    def test_frontend_language_and_highlighting_render_in_browser(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for skill in SKILLS:
                    recorder = load_script(skill, "record_demo")
                    for suffix, language, label in (("js", "javascript", "JavaScript"), ("jsx", "javascript", "JavaScript"), ("ts", "typescript", "TypeScript"), ("tsx", "typescript", "TypeScript")):
                        with self.subTest(skill=skill, suffix=suffix):
                            config = recorder.code_overlay_config("vertical", {
                                "source_file": f"src/ui.{suffix}", "title": "Shared state",
                                "before": "// Real frontend code", "text": 'const value = "#007BC2";',
                            })
                            self.assertEqual(config["language"], language)
                            page = browser.new_page()
                            try:
                                page.evaluate(recorder.CODE_OVERLAY_JS, config)
                                self.assertGreater(page.locator(".tok-keyword").count(), 0)
                                self.assertEqual(page.locator(".tok-comment").first.inner_text(), "// Real frontend code")
                                self.assertIn(label, page.locator("body").inner_text())
                            finally:
                                page.close()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
