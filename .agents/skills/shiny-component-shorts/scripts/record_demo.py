#!/usr/bin/env python3
"""Record a Shiny component demo from a declarative action file."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import yaml


SUPPORTED_ACTIONS = frozenset(
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
    }
)

CURSOR_OVERLAY_JS = r"""(() => {
    const install = () => {
        if (document.getElementById('__demo_cursor__')) return;
        const style = document.createElement('style');
        style.textContent = `
            @keyframes __demo_cursor_ripple__ {
                from { opacity: .45; transform: translate(-50%, -50%) scale(.35); }
                to { opacity: 0; transform: translate(-50%, -50%) scale(1.35); }
            }
            .__demo_cursor_ripple__ {
                position: fixed; z-index: 2147483646; width: 28px; height: 28px;
                border: 2px solid rgba(0, 123, 194, .75); border-radius: 50%;
                pointer-events: none; animation: __demo_cursor_ripple__ 420ms ease-out forwards;
            }
        `;
        document.head.appendChild(style);

        const ns = 'http://www.w3.org/2000/svg';
        const cursor = document.createElementNS(ns, 'svg');
        cursor.id = '__demo_cursor__';
        cursor.setAttribute('viewBox', '0 0 24 30');
        cursor.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:28px;'
            + 'z-index:2147483647;pointer-events:none;opacity:0;'
            + 'filter:drop-shadow(0 1px 1px rgba(29,31,33,.55));transform-origin:2px 2px;';
        const arrow = document.createElementNS(ns, 'path');
        arrow.setAttribute('d', 'M2 2 L2 23 L7.5 17.5 L12.5 28 L16.5 26 L11.5 16 L21 16 Z');
        arrow.setAttribute('fill', '#FFFFFF');
        arrow.setAttribute('stroke', '#1D1F21');
        arrow.setAttribute('stroke-width', '1.4');
        arrow.setAttribute('stroke-linejoin', 'round');
        cursor.appendChild(arrow);
        document.documentElement.appendChild(cursor);

        let x = -30, y = -30, pressed = false;
        const render = () => {
            cursor.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${pressed ? .88 : 1})`;
        };
        window.addEventListener('mousemove', event => {
            x = event.clientX; y = event.clientY;
            cursor.style.opacity = '1';
            render();
        }, true);
        window.addEventListener('mousedown', () => {
            pressed = true;
            render();
            const ripple = document.createElement('span');
            ripple.className = '__demo_cursor_ripple__';
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            document.documentElement.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove(), {once: true});
        }, true);
        window.addEventListener('mouseup', () => {
            pressed = false;
            render();
        }, true);
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', install, {once: true});
    } else {
        install();
    }
})();"""

CODE_OVERLAY_JS = """async (cfg) => {
    document.getElementById('__code_overlay__')?.remove();
    document.getElementById('__code_overlay_style__')?.remove();
    document.documentElement.classList.remove('__demo_code_side__');
    const sideBySide = cfg.layout === 'side';
    const style = document.createElement('style');
    style.id = '__code_overlay_style__';
    style.textContent = '@keyframes __blink {0%,55%{opacity:1}56%,100%{opacity:0}}'
        + '#__code_overlay__ .cursor{animation:__blink 1s step-end infinite;}'
        + '#__code_overlay__ *{box-sizing:border-box;}'
        + 'html.__demo_code_side__ body{width:54vw!important;max-width:54vw!important;'
        + 'margin-left:2vw!important;margin-right:0!important;overflow-x:hidden!important;}'
        + 'html.__demo_code_side__ body>*:not(#__code_overlay__){max-width:100%!important;}';
    document.head.appendChild(style);
    const el = document.createElement('div');
    el.id = '__code_overlay__';
    el.style.cssText = sideBySide
        ? 'position:fixed;top:20%;bottom:20%;right:3%;width:41%;z-index:99999;'
            + 'display:flex;flex-direction:column;background:#1D1F21;'
            + 'border:1px solid #48505F;border-radius:10px;'
            + 'box-shadow:0 18px 60px rgba(29,31,33,.55);overflow:hidden;'
        : 'position:fixed;left:4%;right:4%;top:28%;max-height:52%;z-index:99999;'
            + 'background:#1D1F21;border:1px solid #48505F;border-radius:10px;'
            + 'box-shadow:0 18px 60px rgba(29,31,33,.55);overflow:hidden;';
    if (sideBySide) document.documentElement.classList.add('__demo_code_side__');
    const titlebar = document.createElement('div');
    titlebar.textContent = 'Shiny app code';
    titlebar.style.cssText = 'height:28px;display:grid;place-items:center;background:#202020;'
        + 'border-bottom:1px solid #343A46;color:#CDD4DA;'
        + "font:11px 'Mona Sans',system-ui,sans-serif;";
    const workbench = document.createElement('div');
    workbench.style.cssText = 'display:flex;min-height:146px;flex:1;';
    const activity = document.createElement('div');
    activity.id = '__code_activity_bar__';
    activity.innerHTML = '<div>▱</div><div>⌕</div><div>⑂</div>';
    activity.style.cssText = 'width:38px;flex:0 0 38px;background:#202020;color:#8D959E;'
        + 'border-right:1px solid #343A46;text-align:center;font:20px/38px sans-serif;';
    const editor = document.createElement('div');
    editor.style.cssText = 'min-width:0;flex:1;background:#1D1F21;';
    const tabs = document.createElement('div');
    tabs.style.cssText = 'height:34px;display:flex;background:#202020;border-bottom:1px solid #343A46;';
    const tab = document.createElement('div');
    tab.id = '__code_tab__';
    tab.innerHTML = '<span style="color:#007BC2;font-weight:800">PY</span><span></span><span>×</span>';
    tab.children[1].textContent = cfg.title;
    tab.style.cssText = 'display:flex;align-items:center;gap:8px;padding:0 12px;background:#1D1F21;'
        + 'border-top:2px solid #007BC2;color:#CDD4DA;'
        + "font:12px 'Mona Sans',system-ui,sans-serif;";
    tabs.appendChild(tab);
    const breadcrumb = document.createElement('div');
    breadcrumb.textContent = 'src  ›  ' + cfg.title;
    breadcrumb.style.cssText = 'height:25px;padding:5px 12px;color:#8D959E;'
        + "font:11px 'Mona Sans',system-ui,sans-serif;";
    const codeRow = document.createElement('div');
    codeRow.style.cssText = 'display:flex;padding:10px 14px 15px 0;';
    const gutter = document.createElement('div');
    gutter.id = '__code_gutter__';
    gutter.textContent = '1';
    gutter.style.cssText = 'width:42px;flex:0 0 42px;padding-right:12px;text-align:right;'
        + "white-space:pre;color:#8D959E;font:15px/1.65 'Source Code Pro',ui-monospace,monospace;"
        + 'user-select:none;';
    const body = document.createElement('div');
    body.style.cssText = 'min-width:0;white-space:pre-wrap;color:#FFFFFF;'
        + "font-family:'Source Code Pro','SF Mono',ui-monospace,Menlo,monospace;"
        + 'font-size:15px;line-height:1.65;';
    const text = document.createElement('span');
    const cursor = document.createElement('span');
    cursor.className = 'cursor';
    cursor.textContent = '\\u258B';
    cursor.style.color = '#007BC2';
    body.append(text, cursor);
    codeRow.append(gutter, body);
    editor.append(tabs, breadcrumb, codeRow);
    workbench.append(activity, editor);
    el.append(titlebar, workbench);
    document.body.appendChild(el);
    for (let i = 1; i <= cfg.text.length; i++) {
        text.textContent = cfg.text.slice(0, i);
        gutter.textContent = Array.from(
            {length: text.textContent.split('\\n').length}, (_, index) => index + 1
        ).join('\\n');
        await new Promise(resolve => setTimeout(resolve, cfg.typeMs));
    }
}"""


def resolve_orientation(cli_value: str | None, config: dict) -> str:
    orientation = cli_value or config.get("orientation", "vertical")
    if orientation not in {"vertical", "horizontal"}:
        raise ValueError(f"Unsupported orientation: {orientation}")
    return orientation


def code_overlay_config(orientation: str, action: dict) -> dict:
    if orientation not in {"vertical", "horizontal"}:
        raise ValueError(f"Unsupported orientation: {orientation}")
    return {
        "title": action.get("title", "app.py"),
        "text": str(action["text"]).rstrip("\n"),
        "typeMs": action.get("type_ms", 22),
        "layout": "side" if orientation == "horizontal" else "overlay",
    }


def code_hold_ms(text: str, override: int | None = None) -> int:
    return override or max(5500, min(10000, 3200 + 55 * len(text)))


def port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def wait_for_server(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"Shiny server never became reachable at {url}")


def start_app(project_dir: Path, app_type: str, host: str, port: int) -> subprocess.Popen:
    if app_type == "python":
        cmd = [
            sys.executable,
            "-m",
            "shiny",
            "run",
            "--host",
            host,
            "--port",
            str(port),
            "app.py",
        ]
    else:
        cmd = [
            "Rscript",
            "-e",
            f'shiny::runApp(".", host="{host}", port={port}, launch.browser=FALSE)',
        ]
    return subprocess.Popen(cmd, cwd=project_dir)


def move_cursor_to(page, selector: str) -> tuple[float, float]:
    locator = page.locator(selector).first
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError(f"Cursor target is not visible: {selector}")
    x = box["x"] + box["width"] * random.uniform(0.42, 0.58)
    y = box["y"] + box["height"] * random.uniform(0.42, 0.58)
    page.mouse.move(x, y, steps=random.randint(14, 22))
    page.wait_for_timeout(random.randint(90, 180))
    return x, y


def human_click(page, selector: str) -> None:
    move_cursor_to(page, selector)
    page.mouse.down()
    page.wait_for_timeout(random.randint(70, 135))
    page.mouse.up()


def human_drag(page, config: dict) -> None:
    x, y = move_cursor_to(page, config["selector"])
    page.mouse.down()
    page.wait_for_timeout(random.randint(90, 150))
    page.mouse.move(
        x + float(config.get("delta_x", 0)),
        y + float(config.get("delta_y", 0)),
        steps=int(config.get("steps", 24)),
    )
    page.wait_for_timeout(random.randint(90, 150))
    page.mouse.up()


def validate_action_shape(action: object) -> str:
    if not isinstance(action, dict) or len(action) != 1:
        raise ValueError(f"Each action must contain exactly one key: {action!r}")
    name = next(iter(action))
    if name not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unknown action {name!r}; supported: {sorted(SUPPORTED_ACTIONS)}")
    return name


def run_actions(
    page, actions: list[dict], project_dir: Path, orientation: str = "vertical"
) -> None:
    for action in actions:
        name = validate_action_shape(action)
        value = action[name]
        if name == "wait_for":
            page.wait_for_selector(value, state="attached", timeout=15000)
        elif name == "wait":
            page.wait_for_timeout(value)
        elif name == "click":
            human_click(page, value)
        elif name == "drag":
            human_drag(page, value)
        elif name == "select_option":
            move_cursor_to(page, value["selector"])
            page.locator(value["selector"]).select_option(value["value"])
        elif name == "hover":
            move_cursor_to(page, value)
        elif name == "fill":
            human_click(page, value["selector"])
            page.locator(value["selector"]).fill(value["value"])
        elif name == "type":
            human_click(page, value["selector"])
            page.eval_on_selector(
                value["selector"],
                "el => { el.focus(); if (el.setSelectionRange) "
                "el.setSelectionRange(el.value.length, el.value.length); }",
            )
            page.locator(value["selector"]).press_sequentially(
                value["value"], delay=value.get("delay", 45)
            )
        elif name == "press":
            page.locator(value["selector"]).press(value["key"])
        elif name == "code":
            config = code_overlay_config(orientation, value)
            text = config["text"]
            page.evaluate(CODE_OVERLAY_JS, config)
            page.wait_for_timeout(code_hold_ms(text, value.get("duration")))
            page.evaluate(
                "() => { document.getElementById('__code_overlay__')?.remove();"
                " document.getElementById('__code_overlay_style__')?.remove();"
                " document.documentElement.classList.remove('__demo_code_side__'); }"
            )
        elif name == "screenshot":
            target = project_dir / value["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target), full_page=True)


def terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def record_project(
    project_dir: Path,
    app_type: str,
    actions_path: Path,
    orientation_override: str | None,
) -> Path:
    from playwright.sync_api import sync_playwright

    project_dir = project_dir.resolve()
    config = yaml.safe_load(actions_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("actions"), list):
        raise ValueError("actions.yaml must contain an `actions` list")

    url = config.get("url", "http://127.0.0.1:8000")
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The shared recorder only starts local Shiny apps")
    bind_host = "127.0.0.1"
    if not port_is_available(bind_host, port):
        raise RuntimeError(
            f"Port {port} is already in use. Stop the known listener and rerun; "
            "the recorder will not kill an unknown process."
        )

    orientation = resolve_orientation(orientation_override, config)
    viewport = {"width": 720, "height": 1280}
    if orientation == "horizontal":
        viewport = {"width": 1280, "height": 720}
    size = {dimension: pixels * 2 for dimension, pixels in viewport.items()}

    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    proc = start_app(project_dir, app_type, bind_host, port)
    try:
        wait_for_server(url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                args=["--force-device-scale-factor=2", "--high-dpi-support=1"]
            )
            context = browser.new_context(
                viewport=viewport,
                record_video_dir=str(artifacts),
                record_video_size=size,
            )
            context.add_init_script(CURSOR_OVERLAY_JS)
            page = context.new_page()
            video = page.video
            page.goto(url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            run_actions(page, config["actions"], project_dir, orientation)
            context.close()
            video_source = Path(video.path())
            browser.close()

        video_name = config.get("video_name", "demo.webm")
        webm_path = artifacts / video_name
        if webm_path.exists() and webm_path != video_source:
            webm_path.unlink()
        if video_source != webm_path:
            shutil.move(str(video_source), webm_path)
        if not webm_path.is_file() or webm_path.stat().st_size == 0:
            raise RuntimeError("Playwright did not produce a non-empty WebM recording")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required to create artifacts/demo.mp4")
        mp4_path = artifacts / Path(video_name).with_suffix(".mp4").name
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(webm_path),
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4_path),
            ],
            check=True,
        )
        if not mp4_path.is_file() or mp4_path.stat().st_size == 0:
            raise RuntimeError("ffmpeg did not produce a non-empty MP4 recording")
        (artifacts / "recording.json").write_text(
            json.dumps(
                {
                    "orientation": orientation,
                    "scale_factor": 2,
                    "width": size["width"],
                    "height": size["height"],
                    "video": mp4_path.name,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return mp4_path
    finally:
        terminate_process(proc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--app-type", choices=["python", "r"], default="python")
    parser.add_argument("--actions", type=Path, default=Path("actions.yaml"))
    parser.add_argument("--orientation", choices=["vertical", "horizontal"], default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = args.project_dir.resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Demo directory does not exist: {project_dir}")
    actions_path = args.actions if args.actions.is_absolute() else project_dir / args.actions
    if not actions_path.is_file():
        raise FileNotFoundError(f"Action file does not exist: {actions_path}")
    mp4_path = record_project(project_dir, args.app_type, actions_path, args.orientation)
    print(f"Recorded: {mp4_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
