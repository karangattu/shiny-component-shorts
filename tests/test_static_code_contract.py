"""Code excerpts are readable source, not a simulated editor session."""

import importlib.util
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class StaticCodeTest(unittest.TestCase):
    def test_complete_source_and_original_layout_in_both_variants(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for tree in [".agents", ".claude"]:
                scripts = ROOT / tree / "skills/shiny-component-shorts/scripts"
                sys.path.insert(0, str(scripts))
                spec = importlib.util.spec_from_file_location(
                    "static_recorder", scripts / "record_demo.py"
                )
                assert spec is not None and spec.loader is not None
                recorder = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(recorder)
                for orientation, width, height in [
                    ("vertical", 720, 1280),
                    ("horizontal", 1280, 720),
                ]:
                    with self.subTest(tree=tree, orientation=orientation):
                        page = browser.new_page(
                            viewport={"width": width, "height": height}
                        )
                        page.set_content(
                            '<body style="width:90%;"><main>Live app</main></body>'
                        )
                        config = recorder.code_overlay_config(
                            orientation,
                            {
                                "title": "app.py",
                                "start_line": 48,
                                "before": "@render.text\ndef coordinates():",
                                "text": '    latitude, longitude = reactive_read(marker, "location")',
                                "after": '    return f"{latitude:.4f}, {longitude:.4f}"',
                            },
                        )
                        page.evaluate(recorder.CODE_OVERLAY_JS, config)
                        overlay = page.locator("#__code_overlay__")
                        self.assertNotIn("Visual Studio Code", overlay.inner_text())
                        self.assertEqual(overlay.locator(".cursor").count(), 0)
                        self.assertEqual(
                            overlay.locator(".__code_source__").all_text_contents(),
                            [
                                "@render.text",
                                "def coordinates():",
                                '    latitude, longitude = reactive_read(marker, "location")',
                                '    return f"{latitude:.4f}, {longitude:.4f}"',
                            ],
                        )
                        self.assertGreater(
                            overlay.locator('[class*="hljs-"]').count(), 0
                        )
                        box = overlay.bounding_box()
                        assert box is not None
                        self.assertGreaterEqual(
                            box["height"],
                            height * 0.9 if orientation == "vertical" else height * 0.5,
                        )
                        if orientation == "vertical":
                            self.assertGreaterEqual(box["width"], width * 0.9)
                        else:
                            app_box = page.locator("main").bounding_box()
                            assert app_box is not None
                            self.assertLessEqual(
                                app_box["x"] + app_box["width"], box["x"]
                            )
                        page.evaluate(recorder.CODE_OVERLAY_REMOVE_JS)
                        self.assertEqual(overlay.count(), 0)
                        self.assertEqual(
                            page.locator("body").evaluate("(e)=>e.style.width"), "90%"
                        )
                        page.close()
                sys.path.pop(0)
            browser.close()
