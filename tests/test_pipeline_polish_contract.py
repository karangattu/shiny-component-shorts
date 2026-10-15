import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = [ROOT / ".claude/skills/shiny-component-shorts", ROOT / ".agents/skills/shiny-component-shorts"]


def load(name: str, copy: Path = COPIES[0]):
    sys.path.insert(0, str(copy / "scripts"))
    spec = importlib.util.spec_from_file_location(
        f"{name}_{copy.parent.parent.name}_polish", copy / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ParallelOrientationTest(unittest.TestCase):
    def test_run_jobs_shares_one_concurrency_budget(self):
        batch = load("batch_process")
        lock, active, peak = threading.Lock(), [0], [0]

        def worker(_name: str) -> dict:
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
            return {}

        batch.run_jobs([(worker, (f"job{i}",)) for i in range(6)], 2)
        self.assertEqual(peak[0], 2)

    def test_finish_schedules_companions_with_primaries(self):
        for copy in COPIES:
            source = (copy / "scripts/batch_process.py").read_text()
            self.assertIn("jobs.append((companion_project, (project, companion_port", source)
            self.assertIn("run_jobs(jobs, args.record_concurrency)", source)
            self.assertIn("thumbnails=False", source)


class ReelCacheTest(unittest.TestCase):
    def test_from_cache_builds_once_and_keys_change_with_inputs(self):
        stitch = load("stitch_reel")
        builds = []

        def build(target: Path) -> None:
            builds.append(target)
            target.write_bytes(b"clip")

        with tempfile.TemporaryDirectory() as temp:
            cache, out = Path(temp) / "cache", Path(temp) / "out.mp4"
            key = stitch.cache_key({"kind": "intro"})
            stitch.from_cache(cache, key, out, build)
            stitch.from_cache(cache, key, out, build)
            self.assertEqual(len(builds), 1)
            self.assertEqual(out.read_bytes(), b"clip")
            self.assertNotEqual(key, stitch.cache_key({"kind": "outro"}))

    def test_cards_load_the_bundled_fonts(self):
        stitch = load("stitch_reel")
        css = stitch.font_css()
        self.assertIn("font-family: 'Open Sans'", css)
        self.assertIn("font-family: 'Source Code Pro'", css)
        for copy in COPIES:
            fonts = copy / "assets/fonts"
            for name in ("OpenSans-Latin.woff2", "SourceCodePro-Latin.woff2"):
                self.assertTrue((fonts / name).stat().st_size > 10_000, name)
            self.assertIn("SIL OPEN FONT LICENSE Version 1.1", (fonts / "OFL.txt").read_text())


class LogoReloadTest(unittest.TestCase):
    def test_logo_stays_hidden_after_a_reload(self):
        import http.server
        import socketserver

        from playwright.sync_api import sync_playwright

        recorder = load("record_demo")
        handler = http.server.SimpleHTTPRequestHandler
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "index.html").write_text("<main>app</main>")

            class Handler(handler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=temp, **kwargs)

                def log_message(self, format: str, *args: object) -> None:
                    pass

            with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
                threading.Thread(target=server.serve_forever, daemon=True).start()
                url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
                logo = recorder.logo_overlay_config("vertical", recorder.resolve_logo_path())
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    try:
                        context = browser.new_context()
                        context.add_init_script(f"({recorder.LOGO_OVERLAY_JS})({json.dumps(logo)})")
                        page = context.new_page()
                        page.goto(url)
                        page.wait_for_selector("#__demo_logo__", state="attached")
                        recorder.hide_logo_after(page, 0.1)
                        page.wait_for_timeout(700)
                        page.reload()
                        page.wait_for_selector("#__demo_logo__", state="attached")
                        page.wait_for_timeout(500)
                        opacity = page.eval_on_selector(
                            "#__demo_logo__", "el => getComputedStyle(el).opacity"
                        )
                        self.assertEqual(opacity, "0")
                    finally:
                        browser.close()
                server.shutdown()


class ReelSegmentWarningTest(unittest.TestCase):
    def test_long_segment_narration_warns_only_inside_a_reel(self):
        batch = load("batch_process")
        with tempfile.TemporaryDirectory() as temp:
            segment = Path(temp) / "reel" / "01-feature"
            (segment / "artifacts").mkdir(parents=True)
            timing = segment / "artifacts" / "narration-timing.json"
            timing.write_text(json.dumps({"duration_seconds": 31.0}))
            self.assertEqual(batch.reel_segment_warnings(segment, timing), [])
            (segment.parent / "reel.yaml").write_text("features: []\n")
            self.assertIn("31.0s", batch.reel_segment_warnings(segment, timing)[0])
            timing.write_text(json.dumps({"duration_seconds": 20.0}))
            self.assertEqual(batch.reel_segment_warnings(segment, timing), [])


class ThumbnailTest(unittest.TestCase):
    def test_thumbnails_for_both_orientations(self):
        thumbnail = load("thumbnail")
        with tempfile.TemporaryDirectory() as temp:
            demo = Path(temp)
            artifacts = demo / "artifacts"
            artifacts.mkdir()
            (demo / "actions.yaml").write_text("title: Show every check at once\nactions: []\n")
            for name, size in (("final_with_audio.mp4", "144x256"), ("final_with_audio-horizontal.mp4", "256x144")):
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                     f"color=c=white:s={size}:d=2", "-pix_fmt", "yuv420p", str(artifacts / name)],
                    check=True,
                )
            made = thumbnail.make_thumbnails(demo)
            self.assertEqual([path.name for path in made], ["thumbnail.jpg", "thumbnail-horizontal.jpg"])
            for path, expected in zip(made, ("1080x1920", "1280x720")):
                size = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of",
                     "csv=s=x:p=0", str(path)],
                    capture_output=True, text=True, check=True,
                ).stdout.strip()
                self.assertEqual(size, expected)
                self.assertLess(path.stat().st_size, thumbnail.MAX_BYTES)
            self.assertEqual(thumbnail.project_title(demo), "Show every check at once")

    def test_scripts_are_mirrored(self):
        for name in ("thumbnail.py", "stitch_reel.py", "companion.py", "batch_process.py"):
            self.assertEqual(
                (COPIES[0] / "scripts" / name).read_text(), (COPIES[1] / "scripts" / name).read_text(), name
            )


if __name__ == "__main__":
    unittest.main()
