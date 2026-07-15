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
        "caption",
        "beat",
        "label",
    }
)

DEFAULT_BEATS = ("Reveal", "Proof", "Code", "Payoff")
DEFAULT_ACCENT = "#4285f4"

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
                border: 2px solid rgba(66, 133, 244, .75); border-radius: 50%;
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
            + 'filter:drop-shadow(0 1px 1px rgba(0,0,0,.55));transform-origin:2px 2px;';
        const arrow = document.createElementNS(ns, 'path');
        arrow.setAttribute('d', 'M2 2 L2 23 L7.5 17.5 L12.5 28 L16.5 26 L11.5 16 L21 16 Z');
        arrow.setAttribute('fill', '#fff');
        arrow.setAttribute('stroke', '#171717');
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
    const style = document.createElement('style');
    style.id = '__code_overlay_style__';
    style.textContent = '@keyframes __blink {0%,55%{opacity:1}56%,100%{opacity:0}}'
        + '#__code_overlay__ .cursor{animation:__blink 1s step-end infinite;}';
    document.head.appendChild(style);
    const el = document.createElement('div');
    el.id = '__code_overlay__';
    el.style.cssText = 'position:fixed;left:5%;right:5%;top:34%;z-index:99999;'
        + 'background:#0b1020;border:1px solid rgba(255,255,255,.08);'
        + 'border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.55);overflow:hidden;';
    const bar = document.createElement('div');
    bar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px 14px;'
        + 'background:rgba(255,255,255,.05);border-bottom:1px solid rgba(255,255,255,.06);';
    for (const color of ['#ff5f57', '#febc2e', '#28c840']) {
        const dot = document.createElement('span');
        dot.style.cssText = 'width:11px;height:11px;border-radius:50%;background:' + color + ';';
        bar.appendChild(dot);
    }
    const title = document.createElement('span');
    title.textContent = cfg.title;
    title.style.cssText = 'margin-left:8px;color:#8b93a7;font-size:12.5px;'
        + "font-family:ui-monospace,'SF Mono',Menlo,monospace;";
    bar.appendChild(title);
    const body = document.createElement('div');
    body.style.cssText = 'padding:16px 18px;white-space:pre-wrap;color:#e8ecf4;'
        + "font-family:'JetBrains Mono','Fira Code','SF Mono',ui-monospace,Menlo,monospace;"
        + 'font-size:16px;line-height:1.65;';
    const text = document.createElement('span');
    const cursor = document.createElement('span');
    cursor.className = 'cursor';
    cursor.textContent = '\\u258B';
    cursor.style.color = '#7aa2ff';
    body.append(text, cursor);
    el.append(bar, body);
    document.body.appendChild(el);
    for (let i = 1; i <= cfg.text.length; i++) {
        text.textContent = cfg.text.slice(0, i);
        await new Promise(resolve => setTimeout(resolve, cfg.typeMs));
    }
}"""


RETENTION_OVERLAY_JS = r"""(cfg) => {
    const install = () => {
        if (document.getElementById('__demo_hook__')) return;
        const font = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif";

        const hook = document.createElement('div');
        hook.id = '__demo_hook__';
        hook.textContent = cfg.hook;
        hook.style.cssText = 'position:fixed;top:4%;left:6%;right:6%;z-index:2147483645;'
            + 'pointer-events:none;background:rgba(11,16,32,.92);color:#f4f7ff;'
            + 'border-radius:16px;padding:14px 18px;text-align:center;'
            + `font:800 32px/1.25 ${font};letter-spacing:-.01em;`
            + 'box-shadow:0 10px 34px rgba(0,0,0,.45);';
        document.documentElement.appendChild(hook);

        const label = document.createElement('div');
        label.id = '__demo_state_label__';
        label.style.cssText = 'position:fixed;top:15%;left:6%;z-index:2147483645;'
            + 'pointer-events:none;display:none;background:' + cfg.accent + ';color:#fff;'
            + 'border-radius:8px;padding:5px 12px;text-transform:uppercase;'
            + `font:700 15px/1.3 ${font};letter-spacing:.08em;`
            + 'box-shadow:0 4px 16px rgba(0,0,0,.35);';
        document.documentElement.appendChild(label);

        const caption = document.createElement('div');
        caption.id = '__demo_caption__';
        caption.style.cssText = 'position:fixed;bottom:15%;left:8%;right:8%;z-index:2147483645;'
            + 'pointer-events:none;opacity:0;transition:opacity 150ms ease;'
            + 'color:#fff;text-align:center;'
            + `font:700 27px/1.3 ${font};`
            + 'text-shadow:0 2px 10px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9);';
        document.documentElement.appendChild(caption);

        const rail = document.createElement('div');
        rail.id = '__demo_beat_rail__';
        rail.style.cssText = 'position:fixed;bottom:4%;left:0;right:0;z-index:2147483645;'
            + 'pointer-events:none;display:flex;justify-content:center;gap:8px;';
        const pills = cfg.beats.map(name => {
            const pill = document.createElement('span');
            pill.textContent = name;
            pill.style.cssText = 'background:rgba(11,16,32,.85);color:rgba(255,255,255,.35);'
                + 'border-radius:999px;padding:5px 13px;'
                + `font:700 13px/1.3 ${font};letter-spacing:.04em;`
                + 'transition:background 150ms ease,color 150ms ease;';
            rail.appendChild(pill);
            return pill;
        });
        document.documentElement.appendChild(rail);

        window.__demo_overlays__ = {
            setCaption(text) {
                caption.textContent = text;
                caption.style.opacity = text ? '1' : '0';
            },
            setBeat(index) {
                pills.forEach((pill, i) => {
                    pill.style.background = i === index ? cfg.accent : 'rgba(11,16,32,.85)';
                    pill.style.color = i === index ? '#fff' : 'rgba(255,255,255,.35)';
                });
                this.setLabel('#' + (index + 1) + ' ' + cfg.beats[index].toUpperCase());
            },
            setLabel(text) {
                label.textContent = text;
                label.style.display = text ? 'block' : 'none';
            },
        };
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', install, {once: true});
    } else {
        install();
    }
}"""


def normalize_overlays(config: dict) -> dict | None:
    overlays = config.get("overlays")
    if overlays is None:
        return None
    if not isinstance(overlays, dict) or not str(overlays.get("hook", "")).strip():
        raise ValueError("The overlays block must define a non-empty `hook`")
    beats = overlays.get("beats", list(DEFAULT_BEATS))
    if not isinstance(beats, list) or not beats:
        raise ValueError("overlays.beats must be a non-empty list of beat names")
    return {
        "hook": str(overlays["hook"]).strip(),
        "beats": [str(beat) for beat in beats],
        "accent": str(overlays.get("accent", DEFAULT_ACCENT)),
    }


def resolve_beat_index(value: object, beats: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"beat must be a 1-based index or a beat name: {value!r}")
    if isinstance(value, int):
        index = value - 1
    else:
        lowered = [beat.lower() for beat in beats]
        if value.lower() not in lowered:
            raise ValueError(f"Unknown beat {value!r}; overlays.beats = {beats}")
        index = lowered.index(value.lower())
    if not 0 <= index < len(beats):
        raise ValueError(f"beat {value!r} is out of range for {len(beats)} beats")
    return index


def resolve_orientation(cli_value: str | None, config: dict) -> str:
    orientation = cli_value or config.get("orientation", "vertical")
    if orientation not in {"vertical", "horizontal"}:
        raise ValueError(f"Unsupported orientation: {orientation}")
    return orientation


def code_hold_ms(text: str, override: int | None = None) -> int:
    return override or max(3500, min(8000, 1200 + 55 * len(text)))


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


def start_app_with_retry(
    project_dir: Path,
    app_type: str,
    host: str,
    port: int,
    url: str,
    attempts: int = 3,
) -> subprocess.Popen:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        proc = start_app(project_dir, app_type, host, port)
        try:
            wait_for_server(url, timeout=20.0)
            return proc
        except RuntimeError as exc:
            last_error = exc
            terminate_process(proc)
            if attempt < attempts:
                time.sleep(2 * attempt)
                if not port_is_available(host, port):
                    raise RuntimeError(
                        f"Port {port} became occupied between startup attempts; "
                        "the recorder will not kill an unknown process."
                    ) from exc
    raise RuntimeError(
        f"Shiny app failed to start after {attempts} attempts: {last_error}"
    ) from last_error


def collect_selectors(actions: list[dict]) -> list[str]:
    """Selectors to pre-check on the loaded page.

    Targets of any `wait_for` action are exempt: naming them there declares
    they appear asynchronously after an interaction.
    """
    exempt: set[str] = set()
    ordered: list[str] = []
    for action in actions:
        name = validate_action_shape(action)
        value = action[name]
        if name == "wait_for":
            exempt.add(value)
            continue
        if name in {"click", "hover"}:
            selector = value
        elif name in {"drag", "select_option", "fill", "type", "press"}:
            selector = value["selector"]
        else:
            continue
        if selector not in ordered:
            ordered.append(selector)
    return [selector for selector in ordered if selector not in exempt]


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
    page, actions: list[dict], project_dir: Path, overlays: dict | None = None
) -> None:
    for action in actions:
        name = validate_action_shape(action)
        value = action[name]
        if name in {"caption", "beat", "label"} and overlays is None:
            raise ValueError(
                f"The {name!r} action requires an `overlays` block in actions.yaml"
            )
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
            text = value["text"].rstrip("\n")
            page.evaluate(
                CODE_OVERLAY_JS,
                {
                    "title": value.get("title", "app.py"),
                    "text": text,
                    "typeMs": value.get("type_ms", 22),
                },
            )
            page.wait_for_timeout(code_hold_ms(text, value.get("duration")))
            page.evaluate(
                "() => { document.getElementById('__code_overlay__')?.remove();"
                " document.getElementById('__code_overlay_style__')?.remove(); }"
            )
        elif name == "screenshot":
            target = project_dir / value["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target), full_page=True)
        elif name == "caption":
            page.evaluate(
                "text => window.__demo_overlays__?.setCaption(text)", str(value or "")
            )
            page.wait_for_timeout(300)
        elif name == "beat":
            assert overlays is not None
            index = resolve_beat_index(value, overlays["beats"])
            page.evaluate("index => window.__demo_overlays__?.setBeat(index)", index)
            page.wait_for_timeout(300)
        elif name == "label":
            page.evaluate(
                "text => window.__demo_overlays__?.setLabel(text)", str(value or "")
            )
            page.wait_for_timeout(300)


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
    overlays = normalize_overlays(config)
    size = {"width": 720, "height": 1280}
    if orientation == "horizontal":
        size = {"width": 1280, "height": 720}

    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    proc = start_app_with_retry(project_dir, app_type, bind_host, port, url)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport=size,
                record_video_dir=str(artifacts),
                record_video_size=size,
            )
            context.add_init_script(CURSOR_OVERLAY_JS)
            if overlays is not None:
                context.add_init_script(
                    f"({RETENTION_OVERLAY_JS})({json.dumps(overlays)})"
                )
            page = context.new_page()
            video = page.video
            page.goto(url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            missing = [
                selector
                for selector in collect_selectors(config["actions"])
                if page.locator(selector).count() == 0
            ]
            if missing:
                raise RuntimeError(
                    "Selectors not found on initial page: " + ", ".join(missing)
                )
            run_actions(page, config["actions"], project_dir, overlays)
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
                    "overlays": overlays,
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
