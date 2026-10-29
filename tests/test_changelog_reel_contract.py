import importlib.util
import json
import sys
import tempfile
import unittest
import wave
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
            self.assertIn("### Changelog or blog video series", skill)
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


def explainer_segment(base: Path, config: str, seconds: float = 12.0, starts=(0.0, 3.0, 6.0, 9.0)) -> Path:
    """An explainer directory with a quiet narration track and sentence timing."""
    (base / "artifacts").mkdir(parents=True)
    (base / "explainer.yaml").write_text(config)
    with wave.open(str(base / "artifacts" / "narration.wav"), "wb") as track:
        track.setnchannels(1)
        track.setsampwidth(2)
        track.setframerate(16000)
        track.writeframes(b"\x00\x00" * int(16000 * seconds))
    sentences = [{"start": start, "end": start + 2.5} for start in starts]
    (base / "artifacts" / "narration-timing.json").write_text(json.dumps({"sentences": sentences}))
    return base


SCENES_YAML = """title: Reconnect
scenes:
  - type: flow
    nodes:
      - {label: Browser, sentence: 1}
      - {label: "`allow_reconnect()`", caption: Same session, sentence: 2}
  - type: code
    sentence: 3
    caption: One line.
    code: |
      def server(input, output, session):
      -     pass
      +     session.allow_reconnect(True)
    highlight: [3]
  - type: compare
    sentence: 4
    before: {lines: [Every edit re-sends the table]}
    after: {label: Now, code: "render.data_frame(df)"}
"""


class ExplainerSceneTest(unittest.TestCase):
    def setUp(self):
        self.stitch = load("stitch_reel")
        self.feature = {"title": "Feature", "accent": "#007BC2"}

    def spec(self, config: str, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            segment = explainer_segment(Path(temp) / "seg", config, **kwargs)
            return self.stitch.explainer_spec(segment, self.feature, "New in 1.8.0", "vertical")[0]

    def test_legacy_points_become_one_bullets_scene(self):
        spec = self.spec("points:\n  - One\n  - {text: Two, sentence: 3}\ncode: x()\n")
        (scene,) = spec["scenes"]
        self.assertEqual(scene["type"], "bullets")
        self.assertEqual([p["text"] for p in scene["points"]], ["One", "Two"])
        self.assertAlmostEqual(scene["points"][1]["at"], 6.15)
        self.assertEqual(scene["code"], [{"text": "x()", "kind": "", "hl": False}])
        self.assertIsNone(scene["out"])

    def test_code_language_reaches_the_browser_renderer(self):
        spec = self.spec("language: r\npoints: [Example]\ncode: 'function(x) x + 1'\n")
        self.assertEqual(spec.get("language"), "r")

    def test_scenes_start_on_their_sentences(self):
        spec = self.spec(SCENES_YAML)
        flow, code, compare = spec["scenes"]
        self.assertEqual([s["at"] for s in spec["scenes"]], [0.7, 6.15, 9.15])
        self.assertEqual([flow["out"], code["out"], compare["out"]], [6.15, 9.15, None])
        # sentence 1 starts before the header has drawn, so its beat waits for the scene
        self.assertEqual([n["at"] for n in flow["nodes"]], [1.1, 3.15])
        self.assertEqual([line["kind"] for line in code["lines"]], ["", "del", "add"])
        self.assertEqual(code["lines"][2], {"text": "    session.allow_reconnect(True)", "kind": "add", "hl": True})
        self.assertTrue(code["at"] < code["changeAt"] < code["out"])
        self.assertEqual(compare["before"]["label"], "Before")
        self.assertEqual(compare["after"]["code"][0]["text"], "render.data_frame(df)")
        self.assertEqual(spec["sentenceStarts"], [0.15, 3.15, 6.15, 9.15])

    def test_bad_explainers_fail_with_the_file_name(self):
        bad = {
            "unknown type": "scenes:\n  - {type: video}\n",
            "too many": "scenes:\n" + "  - {type: bullets, points: [a]}\n" * 5,
            "cue in the next scene": (
                "scenes:\n  - {type: flow, nodes: [a, {label: b, sentence: 4}]}\n"
                "  - {type: bullets, sentence: 3, points: [c]}\n"
            ),
            "scenes out of order": (
                "scenes:\n  - {type: bullets, sentence: 3, points: [a]}\n"
                "  - {type: bullets, sentence: 2, points: [b]}\n"
            ),
            "bars without values": "scenes:\n  - {type: bars, items: [{label: a}, {label: b}]}\n",
            "missing html file": "scenes:\n  - {type: html, file: nope.html}\n",
            "code line too wide": "scenes:\n  - {type: code, code: '" + "x" * 65 + "'}\n",
        }
        for name, config in bad.items():
            with self.subTest(name), self.assertRaises(SystemExit) as raised:
                self.spec(config)
            self.assertIn("explainer.yaml", str(raised.exception))

    def test_accent_text_stays_readable(self):
        self.assertEqual(self.stitch.on_accent("#007BC2"), "#FFFFFF")
        self.assertEqual(self.stitch.on_accent("#F9B928"), "#1D1F21")

    def test_every_scene_fits_the_band_in_both_orientations(self):
        from playwright.sync_api import sync_playwright

        config = """scenes:
  - type: flow
    nodes: [Browser, Connection drops, "`session.allow_reconnect()`", Inputs restored]
  - type: code
    sentence: 2
    code: |
      def server(input, output, session):
      -     pass
      +     session.allow_reconnect(True)  # keep inputs on a reconnect
  - type: compare
    sentence: 3
    before: {lines: [Every edit re-sends the table, "`render.data_frame` redraws all rows"]}
    after: {code: "render.data_frame(df)"}
  - type: bars
    sentence: 4
    caption: Editing one cell.
    items: [{label: Before, value: 840, text: 840 ms}, {label: Now, value: 60, text: 60 ms}]
"""
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            segment = explainer_segment(Path(temp) / "seg", config, seconds=16, starts=(0.0, 3.0, 7.0, 11.0))
            browser = playwright.chromium.launch()
            try:
                for orientation in ("vertical", "horizontal"):
                    spec = self.stitch.explainer_spec(segment, self.feature, "New", orientation)[0]
                    width, height = self.stitch.SIZES[orientation]
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.set_content(f"<style>{self.stitch.PAGE_CSS}</style>")
                    page.evaluate(self.stitch.PAGE_JS, {**spec, "logo": "", "logoWidth": 0, "logoFade": 0.4})
                    fits = page.evaluate("""() => {
                      const stage = document.querySelector('.stage').getBoundingClientRect();
                      return [...document.querySelectorAll('.fit')].map((fit) => {
                        const box = fit.getBoundingClientRect();
                        const rows = [...fit.querySelectorAll('.ln, .flow, .node, .panel')];
                        return box.height <= stage.height + 1 && box.width <= stage.width + 1
                          && rows.every((row) => row.scrollWidth <= row.clientWidth + 1);
                      });
                    }""")
                    self.assertEqual(len(fits), 4, orientation)
                    self.assertTrue(all(fits), f"{orientation}: {fits}")
                    page.close()
            finally:
                browser.close()

    def test_html_scene_runs_its_script_and_reads_sentence_times(self):
        from playwright.sync_api import sync_playwright

        html = '<div id="mark" style="animation: rise .5s var(--s2) both">x</div><script>window.ranScene = 1</script>'
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            segment = explainer_segment(Path(temp) / "seg", "scenes:\n  - {type: html, file: scene.html}\n")
            (segment / "scene.html").write_text(html)
            spec = self.stitch.explainer_spec(segment, self.feature, "New", "vertical")[0]
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 720, "height": 1280})
                page.set_content(f"<style>{self.stitch.PAGE_CSS}</style>")
                page.evaluate(self.stitch.PAGE_JS, {**spec, "logo": "", "logoWidth": 0, "logoFade": 0.4})
                self.assertEqual(page.evaluate("window.ranScene"), 1)
                opacity = "() => getComputedStyle(document.getElementById('mark')).opacity"
                page.evaluate(self.stitch.SEEK_JS, 2000)
                self.assertEqual(page.evaluate(opacity), "0")
                page.evaluate(self.stitch.SEEK_JS, 4000)
                self.assertEqual(page.evaluate(opacity), "1")
            finally:
                browser.close()


class LogoTimingTest(unittest.TestCase):
    def test_logo_seconds_default_and_validation(self):
        for copy in COPIES:
            recorder = load("record_demo", copy)
            self.assertEqual(recorder.resolve_logo_seconds({}), 0.0)
            self.assertEqual(recorder.resolve_logo_seconds({"logo_seconds": 0}), 0.0)
            for bad in (-1, "5", True):
                with self.assertRaises(ValueError):
                    recorder.resolve_logo_seconds({"logo_seconds": bad})
            logo = recorder.logo_overlay_config("vertical", recorder.resolve_logo_path(), 0)
            self.assertTrue(logo["hidden"])

    def test_reel_logo_is_opt_in(self):
        for copy in COPIES:
            stitch = load("stitch_reel", copy)
            self.assertEqual(stitch.reel_logo_seconds({}), 0.0)
            self.assertEqual(stitch.reel_logo_seconds({"logo_seconds": 5}), 5.0)
            for bad in (-1, "5", True):
                with self.assertRaises(ValueError):
                    stitch.reel_logo_seconds({"logo_seconds": bad})

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
        self.assertIn('"logoSeconds": logo_seconds', (COPIES[0] / "scripts/stitch_reel.py").read_text())


if __name__ == "__main__":
    unittest.main()
