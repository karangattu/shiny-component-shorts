"""Source-derived stills must preserve code and refuse unreadable layouts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/skills/shiny-component-shorts/scripts"))


class EditorialAssetsTest(unittest.TestCase):
    def test_exact_code_and_provenance_in_both_orientations(self):
        import prepare_editorial

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "app.py").write_text('def answer():\n    return "<value>"\n')
            (project / "source-shots.yaml").write_text(
                """target_seconds: 50
shots:
- cue: Here is the result
  source: Actual app source
  chapter: Source
  panels:
  - file: app.py
    kind: code
    lines: [1, 2]
    highlight: 2
"""
            )
            result = prepare_editorial.prepare(project)
            self.assertEqual(result["target_seconds"], 50)
            self.assertEqual(result["shots"][0]["chapter"], "Source")
            manifest = json.loads(
                (project / "artifacts/editorial-sources/provenance.json").read_text()
            )
            self.assertEqual(manifest["sources"][0]["file"], str((project / "app.py").resolve()))
            self.assertIn(
                str((project / "source-shots.yaml").resolve()),
                {item["file"] for item in manifest["sources"]},
            )
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for orientation in ["vertical", "horizontal"]:
                    view = result["shots"][0]["views"][orientation]
                    self.assertTrue((project / view["file"]).is_file())
                    self.assertEqual(len(view["highlight"]), 4)
                    page = browser.new_page()
                    page.goto((project / view["file"]).with_suffix(".html").as_uri())
                    self.assertEqual(
                        page.locator(".text").all_text_contents(),
                        ["def answer():", '    return "<value>"'],
                    )
                    self.assertGreater(page.locator(".hljs-keyword").count(), 0)
                    page.close()
                browser.close()

    def test_invalid_slice_and_overflow_fail_before_export(self):
        import prepare_editorial

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "app.py").write_text("one\ntwo\n")
            config = project / "source-shots.yaml"
            config.write_text(
                "shots:\n- cue: Source\n  panels:\n  - {kind: code, file: app.py, lines: [1, 9]}\n"
            )
            with self.assertRaisesRegex(ValueError, "lines"):
                prepare_editorial.prepare(project)
            (project / "app.py").write_text(("    a = 1\n") * 60)
            config.write_text("shots:\n- cue: Source\n  panels:\n  - {kind: code, file: app.py}\n")
            with self.assertRaisesRegex(ValueError, "fit|overflow"):
                prepare_editorial.prepare(project)

    def test_corrupt_capture_is_rejected_instead_of_rendering_a_broken_icon(self):
        import prepare_editorial

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "capture.png").write_bytes(b"not an image")
            (project / "source-shots.yaml").write_text(
                "shots:\n- cue: The real capture\n  panels:\n  - {kind: image, file: capture.png}\n"
            )
            with self.assertRaisesRegex(ValueError, "image"):
                prepare_editorial.prepare(project)
