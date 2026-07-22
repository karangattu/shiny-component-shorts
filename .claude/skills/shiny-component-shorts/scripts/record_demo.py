#!/usr/bin/env python3
"""Record a Shiny component demo from a declarative action file."""

from __future__ import annotations

import argparse
import atexit
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

_active_processes = set()

def _cleanup_processes():
    for proc in list(_active_processes):
        try:
            terminate_process(proc)
        except Exception:
            pass

atexit.register(_cleanup_processes)


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
DEFAULT_ACCENT = "#007BC2"

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

CODE_OVERLAY_JS = r"""async (cfg) => {
    document.getElementById('__code_overlay__')?.remove();
    document.getElementById('__code_overlay_style__')?.remove();
    document.documentElement.classList.remove('__demo_code_side__');
    const sideBySide = cfg.layout === 'side';
    const uiFont = getComputedStyle(document.body).fontFamily;
    const escapeHtml = value => value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    const highlightCode = (source, language) => {
        const keywords = new Set(language === 'r'
            ? ['function', 'if', 'else', 'for', 'while', 'in', 'return', 'TRUE', 'FALSE', 'NULL']
            : ['and', 'as', 'async', 'await', 'break', 'class', 'continue', 'def', 'elif',
                'else', 'False', 'finally', 'for', 'from', 'if', 'import', 'in', 'is',
                'lambda', 'None', 'not', 'or', 'pass', 'raise', 'return', 'True',
                'try', 'while', 'with', 'yield']);
        const builtins = new Set(language === 'r'
            ? ['c', 'list', 'min', 'max', 'length', 'paste', 'paste0']
            : ['dict', 'enumerate', 'float', 'int', 'len', 'list', 'max', 'min',
                'range', 'set', 'str', 'tuple', 'zip']);
        const pattern = /(#[^\n]*)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(@[A-Za-z_][A-Za-z0-9_.]*)|([A-Za-z_][A-Za-z0-9_]*)|([0-9]+(?:\.[0-9]+)?)/g;
        let html = '';
        let cursor = 0;
        for (const match of source.matchAll(pattern)) {
            html += escapeHtml(source.slice(cursor, match.index));
            const token = match[0];
            let kind = '';
            if (match[1]) kind = 'comment';
            else if (match[2]) kind = 'string';
            else if (match[3]) kind = 'decorator';
            else if (match[5]) kind = 'number';
            else if (keywords.has(token)) kind = 'keyword';
            else if (builtins.has(token)) kind = 'builtin';
            else if (source.slice(match.index + token.length).trimStart().startsWith('(')) {
                kind = 'function';
            }
            html += kind
                ? `<span class="tok-${kind}">${escapeHtml(token)}</span>`
                : escapeHtml(token);
            cursor = match.index + token.length;
        }
        return html + escapeHtml(source.slice(cursor));
    };
    const style = document.createElement('style');
    style.id = '__code_overlay_style__';
    style.textContent = '@keyframes __blink {0%,55%{opacity:1}56%,100%{opacity:0}}'
        + '#__code_overlay__ .cursor{animation:__blink 1s step-end infinite;}'
        + '#__code_overlay__ *{box-sizing:border-box;}'
        + '#__code_overlay__ .tok-keyword{color:#BF007F;font-weight:600;}'
        + '#__code_overlay__ .tok-string{color:#00BF7F;}'
        + '#__code_overlay__ .tok-comment{color:#CDD4DA;font-style:italic;opacity:.72;}'
        + '#__code_overlay__ .tok-number{color:#F9B928;}'
        + '#__code_overlay__ .tok-decorator{color:#03C7E8;}'
        + '#__code_overlay__ .tok-builtin{color:#03C7E8;}'
        + '#__code_overlay__ .tok-function{color:#F9B928;}'
        + '#__code_overlay__ .__code_context_line__{opacity:.58;}'
        + '#__code_overlay__ .__code_focus_line__{background:rgba(0,123,194,.16);'
        + 'box-shadow:inset 2px 0 #007BC2;}'
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
        : 'position:fixed;left:4%;right:4%;bottom:4%;max-height:46%;z-index:99999;'
            + 'display:flex;flex-direction:column;background:#1D1F21;'
            + 'border:1px solid #48505F;border-radius:10px;'
            + 'box-shadow:0 18px 60px rgba(29,31,33,.55);overflow:hidden;';
    if (sideBySide) document.documentElement.classList.add('__demo_code_side__');
    const titlebar = document.createElement('div');
    titlebar.style.cssText = 'height:30px;display:grid;grid-template-columns:64px 1fr 64px;'
        + 'align-items:center;background:#202020;border-bottom:1px solid rgba(205,212,218,.18);'
        + 'color:#CDD4DA;font-size:10px;font-family:' + uiFont + ';';
    const traffic = document.createElement('div');
    traffic.innerHTML = '<i></i><i></i><i></i>';
    traffic.style.cssText = 'display:flex;gap:6px;padding-left:11px;';
    Array.from(traffic.children).forEach((dot, index) => {
        dot.style.cssText = 'display:block;width:9px;height:9px;border-radius:50%;background:'
            + ['#C10000', '#F9B928', '#00891A'][index] + ';';
    });
    const windowTitle = document.createElement('div');
    windowTitle.textContent = cfg.title + ' — Shiny component short — Visual Studio Code';
    windowTitle.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center;';
    titlebar.append(traffic, windowTitle, document.createElement('span'));
    const workbench = document.createElement('div');
    workbench.style.cssText = 'display:flex;min-height:176px;flex:1;';
    const activity = document.createElement('div');
    activity.id = '__code_activity_bar__';
    activity.innerHTML = '<div>▱</div><div>⌕</div><div>⑂</div>';
    activity.style.cssText = 'width:38px;flex:0 0 38px;background:#202020;color:#CDD4DA;'
        + 'border-right:1px solid rgba(205,212,218,.18);text-align:center;'
        + 'font:20px/38px sans-serif;opacity:.82;box-shadow:inset 2px 0 #FFFFFF;';
    const editor = document.createElement('div');
    editor.style.cssText = 'min-width:0;display:flex;flex-direction:column;flex:1;background:#1D1F21;';
    const tabs = document.createElement('div');
    tabs.style.cssText = 'height:34px;display:flex;background:#202020;'
        + 'border-bottom:1px solid rgba(205,212,218,.18);';
    const tab = document.createElement('div');
    tab.id = '__code_tab__';
    tab.innerHTML = '<span></span><span></span><span>×</span>';
    tab.children[0].textContent = cfg.language === 'r' ? 'R' : 'PY';
    tab.children[0].style.cssText = 'color:#03C7E8;font-weight:800;';
    tab.children[1].textContent = cfg.title;
    tab.style.cssText = 'display:flex;align-items:center;gap:8px;padding:0 12px;background:#1D1F21;'
        + 'border-top:2px solid #007BC2;color:#CDD4DA;'
        + 'font-size:12px;font-family:' + uiFont + ';';
    tabs.appendChild(tab);
    const breadcrumb = document.createElement('div');
    breadcrumb.textContent = 'src  ›  ' + cfg.title;
    breadcrumb.style.cssText = 'height:25px;padding:5px 12px;color:#CDD4DA;opacity:.68;'
        + 'font-size:11px;font-family:' + uiFont + ';';
    const codeViewport = document.createElement('div');
    codeViewport.id = '__code_gutter__';
    codeViewport.style.cssText = 'flex:1;overflow:hidden;padding:8px 0 12px;'
        + "font-family:'Source Code Pro','SF Mono',ui-monospace,Menlo,monospace;"
        + 'font-size:14px;line-height:1.65;color:#FFFFFF;';
    const beforeBlock = document.createElement('div');
    const focusBlock = document.createElement('div');
    focusBlock.id = '__code_focus_block__';
    const afterBlock = document.createElement('div');
    const renderLines = (target, source, firstLine, focus) => {
        target.replaceChildren();
        if (!source && !focus) return 0;
        const lines = (source || '').split('\n');
        lines.forEach((line, index) => {
            const row = document.createElement('div');
            row.className = focus ? '__code_focus_line__' : '__code_context_line__';
            row.style.cssText = 'display:grid;grid-template-columns:42px minmax(0,1fr);min-height:23px;';
            const number = document.createElement('span');
            number.textContent = String(firstLine + index);
            number.style.cssText = 'padding-right:12px;text-align:right;color:#CDD4DA;'
                + 'opacity:.62;user-select:none;';
            const code = document.createElement('span');
            code.style.cssText = 'min-width:0;padding-right:12px;white-space:pre-wrap;overflow-wrap:anywhere;';
            code.innerHTML = highlightCode(line, cfg.language);
            if (focus && index === lines.length - 1) {
                const typingCursor = document.createElement('span');
                typingCursor.className = 'cursor';
                typingCursor.textContent = '\u258B';
                typingCursor.style.color = '#007BC2';
                code.appendChild(typingCursor);
            }
            row.append(number, code);
            target.appendChild(row);
        });
        return lines.length;
    };
    const beforeCount = cfg.before ? cfg.before.split('\n').length : 0;
    const focusStart = cfg.startLine + beforeCount;
    const focusCount = cfg.text.split('\n').length;
    renderLines(beforeBlock, cfg.before, cfg.startLine, false);
    renderLines(focusBlock, '', focusStart, true);
    renderLines(afterBlock, cfg.after, focusStart + focusCount, false);
    codeViewport.append(beforeBlock, focusBlock, afterBlock);
    const status = document.createElement('div');
    status.id = '__code_status_bar__';
    status.style.cssText = 'height:20px;display:flex;align-items:center;justify-content:flex-end;gap:12px;'
        + 'padding:0 10px;background:#007BC2;color:#FFFFFF;font:10px/1 ' + uiFont + ';';
    const updateStatus = typed => {
        const column = (typed.split('\n').at(-1) || '').length + 1;
        status.textContent = `Ln ${focusStart}, Col ${column}   Spaces: 4   UTF-8   ${cfg.language === 'r' ? 'R' : 'Python'}`;
    };
    updateStatus('');
    editor.append(tabs, breadcrumb, codeViewport, status);
    workbench.append(activity, editor);
    el.append(titlebar, workbench);
    document.body.appendChild(el);
    for (let i = 1; i <= cfg.text.length; i++) {
        const typed = cfg.text.slice(0, i);
        renderLines(focusBlock, typed, focusStart, true);
        updateStatus(typed);
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
            + 'pointer-events:none;background:rgba(29,31,33,.92);color:#FFFFFF;'
            + 'border-radius:16px;padding:14px 18px;text-align:center;'
            + `font:800 32px/1.25 ${font};letter-spacing:-.01em;`
            + 'box-shadow:0 10px 34px rgba(29,31,33,.45);';
        document.documentElement.appendChild(hook);

        const label = document.createElement('div');
        label.id = '__demo_state_label__';
        label.style.cssText = 'position:fixed;top:15%;left:6%;z-index:2147483645;'
            + 'pointer-events:none;display:none;background:' + cfg.accent + ';color:#FFFFFF;'
            + 'border-radius:8px;padding:5px 12px;text-transform:uppercase;'
            + `font:700 15px/1.3 ${font};letter-spacing:.08em;`
            + 'box-shadow:0 4px 16px rgba(29,31,33,.35);';
        document.documentElement.appendChild(label);

        const caption = document.createElement('div');
        caption.id = '__demo_caption__';
        caption.style.cssText = 'position:fixed;bottom:15%;left:8%;right:8%;z-index:2147483645;'
            + 'pointer-events:none;opacity:0;transition:opacity 150ms ease;'
            + 'color:#FFFFFF;text-align:center;'
            + `font:700 27px/1.3 ${font};`
            + 'text-shadow:0 2px 10px rgba(29,31,33,.85),0 0 2px rgba(29,31,33,.9);';
        document.documentElement.appendChild(caption);

        const rail = document.createElement('div');
        rail.id = '__demo_beat_rail__';
        rail.style.cssText = 'position:fixed;bottom:4%;left:0;right:0;z-index:2147483645;'
            + 'pointer-events:none;display:flex;justify-content:center;gap:8px;';
        const pills = cfg.beats.map(name => {
            const pill = document.createElement('span');
            pill.textContent = name;
            pill.style.cssText = 'background:rgba(29,31,33,.85);color:rgba(205,212,218,.55);'
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
                    pill.style.background = i === index ? cfg.accent : 'rgba(29,31,33,.85)';
                    pill.style.color = i === index ? '#FFFFFF' : 'rgba(205,212,218,.55)';
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


def code_overlay_config(orientation: str, action: dict) -> dict:
    if orientation not in {"vertical", "horizontal"}:
        raise ValueError(f"Unsupported orientation: {orientation}")
    title = action.get("title", "app.py")
    language = str(
        action.get("language")
        or ("r" if str(title).lower().endswith(".r") else "python")
    )
    return {
        "title": title,
        "before": str(action.get("before", "")).strip("\n"),
        "text": str(action["text"]).rstrip("\n"),
        "after": str(action.get("after", "")).strip("\n"),
        "startLine": int(action.get("start_line", 1)),
        "language": language.lower(),
        "typeMs": action.get("type_ms", 22),
        "layout": "side" if orientation == "horizontal" else "overlay",
    }


def code_hold_ms(text: str, override: int | None = None, context: str = "") -> int:
    return override or max(
        5500, min(11000, 3200 + 55 * len(text) + 14 * len(context))
    )


def port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(host: str, start_port: int, max_attempts: int = 100) -> int:
    for port in range(start_port, start_port + max_attempts):
        if port_is_available(host, port):
            return port
    raise RuntimeError(f"Could not find an available port on {host} in range {start_port} to {start_port + max_attempts}")


def url_with_port(url: str, port: int) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    updated = f"{parsed.scheme or 'http'}://{host}:{port}{parsed.path}"
    if parsed.query:
        updated += f"?{parsed.query}"
    if parsed.fragment:
        updated += f"#{parsed.fragment}"
    return updated


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
    proc = subprocess.Popen(cmd, cwd=project_dir)
    _active_processes.add(proc)
    return proc


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


def _ease_in_out(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def _glide(page, x0: float, y0: float, x1: float, y1: float, steps: int) -> None:
    """Move the cursor with ease-in-out pacing and a subtle overshoot-and-settle."""
    distance = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if distance < 2:
        page.mouse.move(x1, y1)
        return
    overshoot = min(8.0, distance * 0.05)
    ox = x1 + (x1 - x0) / distance * overshoot
    oy = y1 + (y1 - y0) / distance * overshoot
    for i in range(1, steps + 1):
        e = _ease_in_out(i / steps)
        page.mouse.move(x0 + (ox - x0) * e, y0 + (oy - y0) * e)
    for i in range(1, 4):
        page.mouse.move(ox + (x1 - ox) * i / 3, oy + (y1 - oy) * i / 3)


def move_cursor_to(page, selector: str) -> tuple[float, float]:
    locator = page.locator(selector).first
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError(f"Cursor target is not visible: {selector}")
    x = box["x"] + box["width"] * random.uniform(0.42, 0.58)
    y = box["y"] + box["height"] * random.uniform(0.42, 0.58)
    origin = getattr(page, "_demo_cursor_pos", None) or (x - 240, y - 160)
    _glide(page, origin[0], origin[1], x, y, random.randint(16, 24))
    page._demo_cursor_pos = (x, y)
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
    tx = x + float(config.get("delta_x", 0))
    ty = y + float(config.get("delta_y", 0))
    steps = int(config.get("steps", 24))
    # Ease the payload drag without overshoot so slider values never wobble.
    for i in range(1, steps + 1):
        e = _ease_in_out(i / steps)
        page.mouse.move(x + (tx - x) * e, y + (ty - y) * e)
    page._demo_cursor_pos = (tx, ty)
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
    page,
    actions: list[dict],
    project_dir: Path,
    overlays: dict | None = None,
    orientation: str = "vertical",
    clock_zero: float | None = None,
) -> list[dict]:
    timeline: list[dict] = []
    zero = clock_zero if clock_zero is not None else time.monotonic()
    for action in actions:
        name = validate_action_shape(action)
        value = action[name]
        started = time.monotonic() - zero
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
            config = code_overlay_config(orientation, value)
            text = config["text"]
            page.evaluate(CODE_OVERLAY_JS, config)
            page.wait_for_timeout(
                code_hold_ms(
                    text,
                    value.get("duration"),
                    config["before"] + config["after"],
                )
            )
            page.evaluate(
                "() => { document.getElementById('__code_overlay__')?.remove();"
                " document.getElementById('__code_overlay_style__')?.remove();"
                " document.documentElement.classList.remove('__demo_code_side__'); }"
            )
        elif name == "screenshot":
            target = project_dir / value["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target))
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
        timeline.append(
            {
                "action": name,
                "start": round(started, 2),
                "end": round(time.monotonic() - zero, 2),
            }
        )
    return timeline


def terminate_process(proc: subprocess.Popen) -> None:
    _active_processes.discard(proc)
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
    app_dir: Path | None = None,
    port_override: int | None = None,
) -> Path:
    from playwright.sync_api import ViewportSize, sync_playwright

    project_dir = project_dir.resolve()
    app_dir = (app_dir or project_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"App directory does not exist: {app_dir}")
    config = yaml.safe_load(actions_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("actions"), list):
        raise ValueError("actions.yaml must contain an `actions` list")

    url = config.get("url", "http://127.0.0.1:8000")
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    port = port_override if port_override is not None else parsed.port or 8000
    if not 1 <= port <= 65436:
        raise ValueError("Port must be between 1 and 65436")
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The shared recorder only starts local Shiny apps")
    bind_host = "127.0.0.1"
    if port_override is not None:
        url = url_with_port(url, port)
    if not port_is_available(bind_host, port):
        try:
            port = find_available_port(bind_host, port)
            url = url_with_port(url, port)
        except RuntimeError as err:
            raise RuntimeError(
                f"Port {parsed.port or 8000} is in use and no other ports were available: {err}"
            )

    orientation = resolve_orientation(orientation_override, config)
    overlays = normalize_overlays(config)
    viewport = ViewportSize(width=720, height=1280)
    if orientation == "horizontal":
        viewport = ViewportSize(width=1280, height=720)
    size = ViewportSize(width=viewport["width"] * 2, height=viewport["height"] * 2)

    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    proc = start_app_with_retry(app_dir, app_type, bind_host, port, url)
    try:
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
            if overlays is not None:
                context.add_init_script(
                    f"({RETENTION_OVERLAY_JS})({json.dumps(overlays)})"
                )
            page = context.new_page()
            video = page.video
            if video is None:
                raise RuntimeError("Playwright did not attach a video recorder")
            recording_started = time.monotonic()
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
            preamble_seconds = time.monotonic() - recording_started
            timeline = run_actions(
                page,
                config["actions"],
                project_dir,
                overlays,
                orientation,
                clock_zero=recording_started,
            )
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
        # Trim the page-load preamble so the first action lands near the start
        # of the deliverable and narration timed from zero stays in sync.
        trim_seconds = max(0.0, preamble_seconds - 0.7)
        # Cut the tail at the final screenshot: capturing it re-rasterizes the
        # page at 1x, which records as a shrunken frame on a gray canvas.
        tail_args: list[str] = []
        screenshot_start = next(
            (
                entry["start"]
                for entry in timeline
                if entry["action"] == "screenshot"
            ),
            None,
        )
        if screenshot_start is not None and screenshot_start - 0.05 > trim_seconds:
            tail_args = ["-t", f"{screenshot_start - 0.05 - trim_seconds:.2f}"]
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(webm_path),
                "-ss",
                f"{trim_seconds:.2f}",
                *tail_args,
                "-c:v",
                "libx264",
                "-crf",
                "17",
                "-preset",
                "slow",
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
                    "action_timeline": [
                        {
                            "action": entry["action"],
                            "start": round(entry["start"] - trim_seconds, 2),
                            "end": round(entry["end"] - trim_seconds, 2),
                        }
                        for entry in timeline
                    ],
                    "orientation": orientation,
                    "overlays": overlays,
                    "scale_factor": 2,
                    "trimmed_preamble_seconds": round(trim_seconds, 2),
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
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--app-type", choices=["python", "r"], default="python")
    parser.add_argument("--actions", type=Path, default=Path("actions.yaml"))
    parser.add_argument("--orientation", choices=["vertical", "horizontal"], default=None)
    parser.add_argument("--port", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = args.project_dir.resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Demo directory does not exist: {project_dir}")
    app_dir = (args.app_dir or project_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"App directory does not exist: {app_dir}")
    actions_path = args.actions if args.actions.is_absolute() else project_dir / args.actions
    if not actions_path.is_file():
        raise FileNotFoundError(f"Action file does not exist: {actions_path}")
    mp4_path = record_project(
        project_dir, args.app_type, actions_path, args.orientation, app_dir, args.port
    )
    print(f"Recorded: {mp4_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
