"""Preflight or record a gallery episode's verified actions against measured narration.

Copy this file and assemble.py beside the production's .video-skill directory, and put a
capture.yaml in the episode directory. Run `preflight` after every change to the app layout.
"""
import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
import yaml

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in (HERE, *HERE.parents) if (p / ".video-skill/scripts").is_dir()), HERE)
sys.path.insert(0, str(ROOT / ".video-skill/scripts"))
import align_narration  # noqa: E402
import record_demo  # noqa: E402
from stitch_reel import CUT_LEAD_SECONDS  # noqa: E402

FPS = 30
LONG_HOLD_SECONDS = 5.0  # flag a wait this long with no visible action


def open_app(browser, view, config):
    width, height = record_demo.viewport_size(view)
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_init_script(record_demo.CURSOR_OVERLAY_JS)
    context.add_init_script(record_demo.SHINY_CLIENT_ERROR_GUARD_JS)
    page = context.new_page()
    page.goto(config["urls"][view], wait_until="domcontentloaded")
    record_demo.wait_for_shiny_ready(page)
    page.locator(config["ready"]).first.wait_for(state="visible")
    # Map tiles, a WebGL layer, and a widget's own frame finish after the page does.
    if config.get("ready_when"):
        page.wait_for_function(config["ready_when"], timeout=30000)
    page.wait_for_timeout(config.get("settle", 5) * 1000)
    check_webgpu(page, config)
    check(page)
    return context, page


def check_webgpu(page, config):
    """A WebGPU widget can render its chrome while its canvas stays blank."""
    if not any("webgpu" in arg.lower() for arg in config.get("browser_args", [])):
        return
    result = page.evaluate("""async () => {
      let adapter = false;
      try { adapter = navigator.gpu ? !!(await navigator.gpu.requestAdapter()) : false; } catch (error) {}
      let notice = false;
      const visit = root => {
        if (/WebGPU is unavailable/i.test(root.textContent || '')) notice = true;
        for (const el of root.querySelectorAll('*')) if (el.shadowRoot) visit(el.shadowRoot);
      };
      visit(document);
      return {adapter, notice};
    }""")
    if not result["adapter"] or result["notice"]:
        raise ValueError(
            "WebGPU is unavailable or the widget reports a blank canvas. "
            "Use browser_args: ['--enable-unsafe-webgpu', '--use-angle=metal'] in capture.yaml."
        )


def check(page):
    record_demo.assert_no_shiny_client_errors(page)
    record_demo.assert_one_cursor(page)
    assert not page.locator(".shiny-output-error").count(), page.locator(".shiny-output-error").first.inner_text()
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")


def glide(page, point, seconds=None):
    x0, y0 = getattr(page, "_demo_cursor_pos", None) or (point[0] - 200, point[1] - 140)
    record_demo._glide(page, x0, y0, point[0], point[1], None if seconds is None else seconds * 1000)
    page._demo_cursor_pos = tuple(point)


def press(page):
    page.mouse.down()
    page.wait_for_timeout(90)
    page.mouse.up()


def act(page, step, points, press_at=None, started=False):
    """Run one step. `press_at` is the monotonic time of its decisive press."""
    before_change = None
    if step.get("expect_change"):
        before_change = json.dumps(page.evaluate(f"(() => ({step['expect_change']}))()"))
    if "click" in step:
        pressed = record_demo.human_click(page, step["click"], press_at)
    elif "point" in step:
        if press_at is not None:
            record_demo.wait_until(page, press_at - 1.0)
        glide(page, points[step["point"]], 0.7 if press_at else None)
        record_demo.wait_until(page, press_at)
        pressed = time.monotonic()
        press(page)
    elif "drag" in step:
        # Hold the button along the path and release at the end: a lasso, an orbit, or a pan.
        path = [points[name] for name in step["drag"]]
        seconds = step.get("seconds", 1.2)
        if not started:
            if press_at is not None:
                record_demo.wait_until(page, press_at - seconds - 0.95)
            glide(page, path[0], 0.6 if press_at else None)
            page.wait_for_timeout(120)
            page.mouse.down()
            page.wait_for_timeout(120)
        elif press_at is not None:
            record_demo.wait_until(page, press_at - seconds - 0.1)
        for point in path[1:]:
            glide(page, point, seconds / (len(path) - 1))
        record_demo.wait_until(page, press_at)
        pressed = time.monotonic()
        page.mouse.up()
    else:
        a, b = (points[name] for name in step["box"])
        if not started:
            if press_at is not None:
                record_demo.wait_until(page, press_at - 1.75)
            glide(page, a, 0.6 if press_at else None)
            page.wait_for_timeout(120)
            press(page)
            page.wait_for_timeout(120)
        elif press_at is not None:
            record_demo.wait_until(page, press_at - 0.8)
        glide(page, b, 0.65)
        record_demo.wait_until(page, press_at)
        pressed = time.monotonic()
        press(page)
    if step.get("dismiss_hover"):
        dismiss = step["dismiss_hover"]
        rest_pt = points[dismiss] if isinstance(dismiss, str) else (dismiss if isinstance(dismiss, list) else points.get("rest", [8, 8]))
        glide(page, rest_pt, 0.15)
    record_demo.assert_one_cursor(page)
    shown = None
    if step.get("expect"):
        page.wait_for_function(step["expect"], timeout=15000)
        shown = time.monotonic()
    if before_change is not None:
        page.wait_for_function(
            "([expr, prev]) => JSON.stringify(new Function('return (' + expr + ')')()) !== prev",
            arg=[step["expect_change"], before_change],
            timeout=8000,
        )
        shown = shown or time.monotonic()
    if step.get("scroll_visible"):
        visible = page.evaluate(
            """sel => {
 const nodes = [...document.querySelectorAll(sel)];
 const el = nodes.at(-1);
 if (!el) return false;
 const r = el.getBoundingClientRect();
 if (r.width <= 0 || r.height <= 0 || r.top < 0 || r.bottom > innerHeight) return false;
 let p = el.parentElement;
 while (p && p !== document.body) {
   const s = getComputedStyle(p);
   if (/(auto|scroll)/.test(s.overflowY)) {
     const pr = p.getBoundingClientRect();
     if (r.top < pr.top - 2 || r.bottom > pr.bottom + 2) return false;
   }
   p = p.parentElement;
 }
 return true;
}""",
            step["scroll_visible"],
        )
        if not visible:
            raise RuntimeError(f"Element {step['scroll_visible']!r} is scrolled out of view")
    return pressed, shown


def state(page, config):
    """What the app shows now, from the optional `report` expression in capture.yaml."""
    return page.evaluate(config["report"]) if config.get("report") else None


def long_hold_warnings(config, spoken, duration):
    """Report stretches of footage with no action, so the editor can recut them."""
    warnings = []
    for clip in config["clips"]:
        steps = clip.get("actions") or []
        if not steps:
            continue  # A result hold is deliberate.
        start = spoken.get(clip["cue"])
        if start is None:
            continue
        marks = []
        for step in steps:
            if "at" in step:
                marks.append(start + step["at"])
            elif step.get("phrase") in spoken:
                marks.append(spoken[step["phrase"]] - step.get("lead", 0))
        if not marks:
            continue
        end = spoken.get(clip.get("end", ""), duration)
        marks.sort()
        gaps = [("before the first action", marks[0] - start)]
        gaps += [(f"after action {index}", b - a)
                 for index, (a, b) in enumerate(zip(marks, marks[1:]), start=1)]
        if end is not None and end > marks[-1]:
            gaps.append(("after the last action", end - marks[-1]))
        for label, seconds in gaps:
            if seconds > LONG_HOLD_SECONDS:
                warnings.append(f'{clip["name"]}: {seconds:.1f}s {label} (> {LONG_HOLD_SECONDS:.0f}s)')
    return warnings


def preflight(browser, project, config, view):
    context, page = open_app(browser, view, config)
    points = config["points"][view]
    for step in config["setup"]:
        act(page, step, points)
    for clip in config["clips"]:
        for step in clip["actions"]:
            pressed, shown = act(page, step, points)
            if shown:
                print(view, clip["name"], f"result after {shown - pressed:.2f}s", json.dumps(state(page, config), ensure_ascii=False), flush=True)
        page.wait_for_timeout(1200)
        check(page)
        page.screenshot(path=str(project / "sources" / f"state-{clip['name']}-{view}.png"),
                        style="#__demo_cursor__ {visibility:hidden !important}")
    context.close()


def record(browser, project, config, view, only=None):
    timing = align_narration.load_timing(project)
    assert timing and timing["transcript_check"]["passed"]
    width, height = record_demo.viewport_size(view)
    points = config["points"][view]

    def spoken(phrase):
        return align_narration.find_timed_phrase(timing, phrase)["start"] + align_narration.NARRATION_OFFSET_SECONDS

    def cut(phrase):
        return math.ceil((spoken(phrase) - CUT_LEAD_SECONDS) * FPS) / FPS

    by_name = {clip["name"]: clip for clip in config["clips"]}
    spoken_times = {}
    for clip in config["clips"]:
        phrases = [clip["cue"], clip.get("end")]
        phrases += [step.get("phrase") for step in clip["actions"]]
        for phrase in phrases:
            if phrase and phrase not in spoken_times:
                spoken_times[phrase] = spoken(phrase)
    for warning in long_hold_warnings(
        config, spoken_times,
        timing["duration_seconds"] + align_narration.NARRATION_OFFSET_SECONDS + 1.5,
    ):
        print(f"WARNING: long hold: {warning}", file=sys.stderr)
    for clip in config["clips"]:
        if only and clip["name"] != only:
            continue
        context, page = open_app(browser, view, config)
        record_demo.rest_cursor(page, width, height)
        for step in config["setup"]:
            act(page, step, points)
        for name in clip.get("resume", []):
            for step in by_name[name]["actions"]:
                act(page, step, points)
        page.wait_for_timeout(1500)
        first = clip["actions"][0] if clip["actions"] else None
        # A box or a drag needs about two seconds of pointer travel. For a clip that opens on one,
        # press its first point off camera, so the recording starts with the shape about to grow.
        started = bool(first and ("box" in first or "drag" in first) and "at" in first)
        if started:
            glide(page, points[(first.get("box") or first["drag"])[0]])
            page.wait_for_timeout(120)
            press(page) if "box" in first else page.mouse.down()
            page.wait_for_timeout(200)
        start = max(0.0, cut(clip["cue"]))
        end = cut(clip["end"]) if "end" in clip else math.ceil(
            (timing["duration_seconds"] + align_narration.NARRATION_OFFSET_SECONDS + 1.5) * FPS) / FPS
        output = project / "sources" / f'{clip["name"]}-{view}.mp4'
        with tempfile.TemporaryDirectory(dir=project / "artifacts", prefix=".frames-") as tmp:
            capture = record_demo.ScreencastCapture(context, page, Path(tmp), width * 2, height * 2)
            capture.start()
            page.wait_for_timeout(140)
            clock, wall = time.monotonic(), time.time()
            trace = []
            try:
                for step in clip["actions"]:
                    when = step["at"] if "at" in step else spoken(step["phrase"]) - start - step.get("lead", 0)
                    pressed, shown = act(page, step, points, clock + when, started and step is first)
                    trace.append({"step": step.get("click") or step.get("point") or step.get("box") or step.get("drag"),
                                  "planned": round(when, 2), "pressed": round(pressed - clock, 2),
                                  "shown": round(shown - clock, 2) if shown else None})
                record_demo.wait_until(page, clock + end - start + 0.4)
                wall_end = time.time()
            finally:
                capture.stop()
            check(page)
            context.close()
            record_demo.encode_screencast(capture.frames, wall, wall_end, output, width * 2, height * 2)
        output.with_suffix(".json").write_text(json.dumps({"start": start, "end": end, "actions": trace}, indent=2) + "\n")
        print(output.name, json.dumps(trace), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("mode", choices=("preflight", "record"))
    parser.add_argument("--view", choices=("vertical", "horizontal"), required=True)
    parser.add_argument("--clip")
    args = parser.parse_args()
    raw_project = Path(args.project)
    project = raw_project if raw_project.is_absolute() or (raw_project / "capture.yaml").is_file() else ROOT / args.project
    config = yaml.safe_load((project / "capture.yaml").read_text())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=[
            "--force-device-scale-factor=2", "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
            # Opt in per episode in capture.yaml, e.g. WebGPU flags for a canvas widget.
            *config.get("browser_args", [])])
        if args.mode == "preflight":
            preflight(browser, project, config, args.view)
        else:
            record(browser, project, config, args.view, args.clip)
        browser.close()


if __name__ == "__main__":
    main()
