"""Source, timing, completion and review behavior that saves recording retries."""

import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def load(tree, name):
    scripts = ROOT / tree / "skills/shiny-component-shorts/scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        name + tree.replace(".", ""), scripts / (name + ".py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.path.pop(0)
    return module


class ProductionWorkflowTest(unittest.TestCase):
    def test_source_ranges_and_narration_holds(self):
        for tree in [".agents", ".claude"]:
            helper = load(tree, "production_actions")
            with tempfile.TemporaryDirectory() as temp:
                app = Path(temp)
                (app / "app.R").write_text(
                    "library(shiny)\nf <- function() {\n  x <- 1\n  x\n}\n"
                )
                timing = {
                    "words": [
                        {"word": "show", "sentence": 0, "start": 1, "end": 1.3},
                        {"word": "done", "sentence": 0, "start": 4, "end": 5},
                        {"word": "next", "sentence": 0, "start": 9, "end": 9.5},
                    ]
                }
                actions: list[dict] = [
                    {"cue": "show"},
                    {
                        "code": {
                            "source_lines": [2, 5],
                            "highlight_lines": [3, 3],
                            "hold_until": "done",
                            "reading_pause": 2,
                        }
                    },
                    {"cue": "next"},
                    {"click": "#run"},
                ]
                result = helper.prepare_actions(actions, app, timing)
                code = result[1]["code"]
                self.assertEqual(code["source_file"], "app.R")
                self.assertEqual(code["start_line"], 2)
                self.assertEqual(code["before"], "f <- function() {")
                self.assertEqual(code["text"], "  x <- 1")
                self.assertEqual(code["after"], "  x\n}")
                self.assertEqual(code["duration"], 6000)
                self.assertNotIn(
                    "text",
                    actions[1]["code"],
                    "Do not mutate the original configuration",
                )
                actions[1]["code"]["reading_pause"] = 5
                with self.assertRaisesRegex(ValueError, "overlap"):
                    helper.prepare_actions(actions, app, timing)
                for bad in [
                    {"source_file": "../private.py", "source_lines": [1, 2]},
                    {"source_lines": [1, 99]},
                    {"source_lines": [2, 5], "highlight_lines": [1, 1]},
                ]:
                    with self.assertRaises(ValueError):
                        helper.prepare_actions([{"code": bad}], app)

    def test_source_ranges_keep_blank_line_numbers_in_the_renderer(self):
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as p:
            root = Path(temp)
            (root / "app.py").write_text("\ndef f():\n\n    return 1\n")
            browser = p.chromium.launch()
            for tree in [".agents", ".claude"]:
                helper = load(tree, "production_actions")
                recorder = load(tree, "record_demo")
                code = helper.prepare_actions(
                    [{"code": {"source_lines": [1, 4], "highlight_lines": [4, 4]}}],
                    root,
                )[0]["code"]
                page = browser.new_page(viewport={"width": 720, "height": 1280})
                page.set_content("<body></body>")
                page.evaluate(
                    recorder.CODE_OVERLAY_JS,
                    recorder.code_overlay_config("vertical", code),
                )
                self.assertEqual(
                    page.locator(".__code_source__").all_text_contents(),
                    ["", "def f():", "", "    return 1"],
                )
                self.assertIn(
                    "lines 1–4", page.locator("#__code_source_label__").inner_text()
                )
                page.close()
            browser.close()

    def test_every_code_review_uses_actual_reveal_time(self):
        for tree in [".agents", ".claude"]:
            review = load(tree, "review_frames")
            marks = dict(
                review.review_marks(
                    [
                        {"action": "code", "start": 1, "reaction": 10, "end": 20},
                        {"action": "code", "start": 21, "reaction": 30, "end": 40},
                    ],
                    45,
                )
            )
            self.assertEqual(marks["code"], 16)
            self.assertEqual(marks["code-2"], 36)

    def test_equivalent_transcripts_do_not_hide_wrong_numbers(self):
        for tree in [".agents", ".claude"]:
            alignment = load(tree, "align_narration")
            normalize = alignment.normalize_tokens
            self.assertEqual(
                normalize("$250,000"), normalize("two hundred fifty thousand dollars")
            )
            self.assertEqual(normalize("filename"), normalize("file name"))
            self.assertNotEqual(normalize("$250,000"), normalize("$350,000"))
            self.assertNotEqual(normalize("-5"), normalize("5"))
            self.assertEqual(normalize("$1"), normalize("one dollar"))
            legacy = [{"word": "filename", "sentence": 0, "start": 1, "end": 2}]
            self.assertEqual(alignment.find_phrase(legacy, "file name")["end"], 2)
            self.assertEqual(legacy[0]["word"], "filename")
            heard = [
                {"word": "$250,", "start": 0, "end": 0.5},
                {"word": "000", "start": 0.5, "end": 1},
            ]
            report = alignment.align("two hundred fifty thousand dollars", heard, 1)
            self.assertEqual(report["word_error_rate"], 0)

    def test_rhythm_is_advisory_but_empty_and_vocalization_are_errors(self):
        for tree in [".agents", ".claude"]:
            voice = load(tree, "check_narration_voice")
            plain = (
                "Transcript:\nThe table updates. The rows change. The labels remain."
            )
            self.assertTrue(voice.voice_warnings(plain))
            self.assertEqual(voice.voice_errors(plain), [])
            self.assertTrue(voice.voice_errors("Transcript:\n[laugh]"))
            self.assertTrue(voice.voice_errors("Transcript:\n"))

    def test_native_panel_completion_and_state_previews_without_narration(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for tree in [".agents", ".claude"]:
                recorder = load(tree, "record_demo")
                with self.subTest(tree=tree), tempfile.TemporaryDirectory() as temp:
                    project = Path(temp)
                    (project / "app.py").write_text("x = 1\ny = 2\n")
                    page = browser.new_page(viewport={"width": 720, "height": 1280})
                    page.set_content(
                        """<button id="run" onclick="document.body.insertAdjacentHTML('beforeend', '<div id=work>Working</div>');setTimeout(()=>{document.querySelector('#work').remove();document.querySelector('#result').textContent='Done'},900)">Run</button><div id="result">Idle</div>"""
                    )
                    page.evaluate(
                        recorder.LOGO_OVERLAY_JS,
                        recorder.logo_overlay_config(
                            "vertical", recorder.resolve_logo_path(), 0
                        ),
                    )
                    actions: list[dict] = [
                        {"cue": "unavailable without audio"},
                        {"click": "#run"},
                        {
                            "wait_stream": {
                                "completion": {
                                    "selector": "#work",
                                    "state": "detached",
                                },
                                "timeout": 2000,
                            }
                        },
                        {"code": {"source_lines": [1, 2]}},
                        {"code": {"text": "x = 1"}},
                    ]
                    frames = recorder.preview_actions(
                        page,
                        actions,
                        project,
                        "vertical",
                        project / "previews",
                        project,
                    )
                    self.assertEqual(page.locator("#result").inner_text(), "Done")
                    self.assertEqual(len([f for f in frames if f["kind"] == "code"]), 2)
                    self.assertTrue(any(f["kind"] == "completed" for f in frames))
                    self.assertTrue(all(Path(f["path"]).is_file() for f in frames))
                    self.assertFalse((project / "artifacts/narration.wav").exists())
                    self.assertFalse((project / "artifacts/recording.json").exists())
                    page.set_content(
                        '<div id="result">Waiting</div><script>setTimeout(()=>document.querySelector("#result").textContent="Ready",150)</script>'
                    )
                    recorder.wait_for_stream(
                        page,
                        {
                            "completion": {"selector": "#result", "text": "Ready"},
                            "timeout": 1500,
                        },
                    )
                    page.set_content(
                        '<script>setTimeout(()=>document.body.insertAdjacentHTML("beforeend", "<div id=work>Busy</div>"),300);setTimeout(()=>document.querySelector("#work").remove(),900)</script>'
                    )
                    started = time.monotonic()
                    recorder.wait_for_stream(
                        page,
                        {
                            "completion": {"selector": "#work", "state": "hidden"},
                            "timeout": 1500,
                        },
                    )
                    self.assertGreater(time.monotonic() - started, 0.2)
                    page.set_content('<div id="result">Waiting</div>')
                    with self.assertRaisesRegex(RuntimeError, "completion"):
                        recorder.wait_for_stream(
                            page,
                            {
                                "completion": {"selector": "#result", "text": "Ready"},
                                "timeout": 150,
                            },
                        )
                    page.close()
            browser.close()
