import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = [ROOT / ".claude/skills/shiny-component-shorts", ROOT / ".agents/skills/shiny-component-shorts"]


def load(name: str, copy: Path = COPIES[0]):
    sys.path.insert(0, str(copy / "scripts"))
    spec = importlib.util.spec_from_file_location(f"{name}_{copy.parent.parent.name}", copy / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KEEP_A_CHANGELOG = """# Change Log

Intro text.

## [Unreleased]

### New features

* `ui.sidebar()` gains a `role` parameter
  for ARIA landmarks (rstudio/bslib#1359). (#2530)

### Bug fixes

* Fixed a crash. (#2518)

## [1.8.0] - 2026-09-12

### New features

* Added `session.allow_reconnect()`. (#2480)
* Added `ui.page_html()`. (#2490)

### Improvements

* Faster [data frames](https://example.com). (#2491)
"""

NEWS_MD = """# shiny (development version)

* Fixed #4281: dates work.

* Added an agent skill. (#4427)

# shiny 1.14.0

## New features

* New `startApp()` runs an app in non-blocking mode. (#4300)

## Bug fixes

* Fixed a bug.
"""


class ChangelogFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.cl = load("changelog_features")

    def test_unreleased_is_default_and_continuations_join(self):
        release = self.cl.pick_release(self.cl.parse_releases(KEEP_A_CHANGELOG), None)
        features = self.cl.feature_entries(release, False, None, "posit-dev/py-shiny")
        self.assertEqual(len(features), 1)
        self.assertIn("for ARIA landmarks", features[0]["text"])
        self.assertEqual(
            features[0]["references"],
            ["https://github.com/rstudio/bslib/pull/1359", "https://github.com/posit-dev/py-shiny/pull/2530"],
        )
        self.assertEqual(features[0]["symbols"][0], "ui.sidebar()")

    def test_named_version_and_improvements(self):
        releases = self.cl.parse_releases(KEEP_A_CHANGELOG)
        release = self.cl.pick_release(releases, "v1.8.0")
        self.assertEqual(release["date"], "2026-09-12")
        self.assertEqual(len(self.cl.feature_entries(release, False, None, None)), 2)
        with_improvements = self.cl.feature_entries(release, True, None, None)
        self.assertEqual(with_improvements[-1]["text"], "Faster data frames. (#2491)")
        with self.assertRaises(SystemExit):
            self.cl.pick_release(releases, "9.9.9")

    def test_r_news_without_subsections_skips_fixes(self):
        releases = self.cl.parse_releases(NEWS_MD)
        dev = self.cl.pick_release(releases, None)
        features = self.cl.feature_entries(dev, False, None, None)
        self.assertEqual([f["text"] for f in features], ["Added an agent skill. (#4427)"])
        named = self.cl.feature_entries(self.cl.pick_release(releases, "1.14.0"), False, None, None)
        self.assertEqual(len(named), 1)
        self.assertEqual(named[0]["section"], "New features")

    def test_missing_unreleased_section_names_latest(self):
        text = KEEP_A_CHANGELOG.split("## [1.8.0]")[1]
        with self.assertRaises(SystemExit) as raised:
            self.cl.pick_release(self.cl.parse_releases("## [1.8.0]" + text), None)
        self.assertIn("1.8.0", str(raised.exception))


class ReelContractTest(unittest.TestCase):
    def test_scripts_and_reference_are_mirrored(self):
        for name in ("scripts/changelog_features.py", "scripts/stitch_reel.py"):
            self.assertEqual((COPIES[0] / name).read_text(), (COPIES[1] / name).read_text(), name)
        for copy in COPIES:
            skill = (copy / "SKILL.md").read_text()
            self.assertIn("### Changelog reel", skill)
            self.assertIn("references/changelog-reel.md", skill)
            reference = (copy / "references/changelog-reel.md").read_text()
            self.assertIn(f"python {copy.relative_to(ROOT)}/scripts/stitch_reel.py", reference)

    def test_batch_finds_explainers_only_outside_finish(self):
        for copy in COPIES:
            batch = load("batch_process", copy)
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                (base / "explainer").mkdir()
                (base / "explainer" / "explainer.yaml").write_text("points: [One]\n")
                (base / "demo").mkdir()
                (base / "demo" / "actions.yaml").write_text("actions: []\n")
                (base / "demo" / "app.py").write_text("")
                self.assertEqual([p.name for p in batch.discover_projects(base)], ["demo"])
                self.assertEqual(
                    [p.name for p in batch.discover_projects(base, explainers=True)],
                    ["demo", "explainer"],
                )
                self.assertEqual(
                    [p.name for p in batch.discover_projects(base, ["*"], explainers=True)],
                    ["demo", "explainer"],
                )

    def test_reel_config_limits(self):
        stitch = load("stitch_reel")
        with tempfile.TemporaryDirectory() as temp:
            reel = Path(temp)
            (reel / "reel.yaml").write_text("features: []\n")
            with self.assertRaises(SystemExit):
                stitch.load_reel(reel)
            many = "".join(f"  - {{title: F{i}, dir: s{i}}}\n" for i in range(stitch.MAX_FEATURES + 1))
            (reel / "reel.yaml").write_text("features:\n" + many)
            with self.assertRaises(SystemExit):
                stitch.load_reel(reel)
            (reel / "reel.yaml").write_text("features:\n  - {title: A, dir: s1}\n  - {title: B, dir: s2}\n")
            config = stitch.load_reel(reel)
            self.assertEqual(config["orientation"], "vertical")
            self.assertEqual(config["features"][1]["path"], (reel / "s2").resolve())
            self.assertNotEqual(config["features"][0]["accent"], config["features"][1]["accent"])


class LogoTimingTest(unittest.TestCase):
    def test_logo_seconds_default_and_validation(self):
        for copy in COPIES:
            recorder = load("record_demo", copy)
            self.assertEqual(recorder.resolve_logo_seconds({}), 5.0)
            self.assertEqual(recorder.resolve_logo_seconds({"logo_seconds": 0}), 0.0)
            for bad in (-1, "5", True):
                with self.assertRaises(ValueError):
                    recorder.resolve_logo_seconds({"logo_seconds": bad})
            logo = recorder.logo_overlay_config("vertical", recorder.resolve_logo_path(), 0)
            self.assertTrue(logo["hidden"])

    def test_overlay_fades_out_and_branding_check_allows_it(self):
        from playwright.sync_api import sync_playwright

        recorder = load("record_demo")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for hidden in (False, True):
                    seconds = 0 if hidden else 5.0
                    page = browser.new_page()
                    logo = recorder.logo_overlay_config("vertical", recorder.resolve_logo_path(), seconds)
                    page.add_init_script(f"({recorder.LOGO_OVERLAY_JS})({json.dumps(logo)})")
                    page.goto("data:text/html,<main>app</main>")
                    page.wait_for_selector("#__demo_logo__", state="attached", timeout=5000)
                    opacity = "el => getComputedStyle(el).opacity"
                    if not hidden:
                        page.wait_for_timeout(500)
                        self.assertEqual(page.eval_on_selector("#__demo_logo__", opacity), "1")
                        recorder.hide_logo_after(page, 0.1)
                    page.wait_for_timeout(1000)
                    self.assertEqual(page.eval_on_selector("#__demo_logo__", opacity), "0")
                    recorder.assert_branding_visible(page)
                    page.close()
            finally:
                browser.close()

    def test_reel_logo_lives_on_the_intro_only(self):
        stitch = load("stitch_reel")
        self.assertGreaterEqual(stitch.INTRO_SECONDS, stitch.LOGO_SECONDS)
        self.assertIn('"logoSeconds": LOGO_SECONDS', (COPIES[0] / "scripts/stitch_reel.py").read_text())


if __name__ == "__main__":
    unittest.main()
