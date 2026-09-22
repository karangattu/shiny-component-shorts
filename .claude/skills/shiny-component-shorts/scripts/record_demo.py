#!/usr/bin/env python3
"""Record a Shiny component demo from a declarative action file."""

from __future__ import annotations

import argparse
import atexit
import base64
import json
import mimetypes
import random
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import IO
from urllib.parse import urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import align_narration  # noqa: E402
import validate_demo  # noqa: E402

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
        "cue",
        "screenshot",
        "caption",
        "beat",
        "label",
    }
)
VISIBLE_ACTIONS = validate_demo.VISIBLE_ACTIONS
# Video time zero sits this long before the first action, so the opening frame
# already shows the settled app with the cursor at rest.
LEAD_SECONDS = 0.7
# An anchored pointer arrives this early, then presses exactly on the phrase.
ARRIVE_EARLY_SECONDS = 0.3
# The overshoot-and-settle after a glide, and the quickest a hurried glide runs.
SETTLE_SECONDS = 0.07
MIN_GLIDE_MS = 260.0
OUTPUT_FPS = 30
SCREENCAST_QUALITY = 92

SHINY_CLIENT_ERROR_GUARD_JS = r"""(() => {
    const marker = 'Shiny Client Errors';
    const record = (text) => {
        if (window.__demo_shiny_client_error__) return;
        const start = text.indexOf(marker);
        if (start !== -1) {
            window.__demo_shiny_client_error__ = text.slice(start, start + 2000);
        }
    };
    const inspect = (node) => record(
        node.nodeType === Node.TEXT_NODE
            ? node.data
            : (node.innerText || node.textContent || '')
    );
    const capture = (mutations = []) => {
        for (const mutation of mutations) {
            if (mutation.type === 'characterData') inspect(mutation.target);
            for (const node of mutation.addedNodes) inspect(node);
        }
        record(document.body?.innerText || '');
    };
    window.__demo_shiny_client_error__ = null;
    new MutationObserver(capture).observe(document, {
        childList: true,
        characterData: true,
        subtree: true,
    });
    document.addEventListener('DOMContentLoaded', capture, {once: true});
})();"""

SHINY_CLIENT_ERROR_SCAN_JS = r"""() => {
    if (window.__demo_shiny_client_error__) {
        return window.__demo_shiny_client_error__;
    }
    const marker = 'Shiny Client Errors';
    const text = document.body?.innerText || '';
    const start = text.indexOf(marker);
    return start === -1 ? null : text.slice(start, start + 2000);
}"""

DEFAULT_BEATS = ("Reveal", "Proof", "Code", "Payoff")
DEFAULT_ACCENT = "#007BC2"

# Every recording carries the Shiny wordmark in the reserved top band.
DEFAULT_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "shiny-logo.png"
LOGO_WIDTHS = {"vertical": 144, "horizontal": 180}
LOGO_INSET = {"top": "4%", "left": "4%"}
LOGO_DARK_THRESHOLD = 0.5

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

LOGO_OVERLAY_JS = r"""(cfg) => {
    const install = () => {
        if (document.getElementById('__demo_logo__')) return;
        const logo = document.createElement('img');
        logo.id = '__demo_logo__';
        logo.src = cfg.src;
        logo.alt = 'Shiny';
        logo.style.cssText = `position:fixed;top:${cfg.top};left:${cfg.left};`
            + `width:${cfg.width}px;height:auto;z-index:2147483644;`
            + 'pointer-events:none;user-select:none;transition:opacity 180ms ease;';
        document.documentElement.appendChild(logo);

        const channel = value => {
            const scaled = value / 255;
            return scaled <= .03928
                ? scaled / 12.92
                : Math.pow((scaled + .055) / 1.055, 2.4);
        };
        const luminance = ([r, g, b]) =>
            .2126 * channel(r) + .7152 * channel(g) + .0722 * channel(b);

        const hasCollision = () => {
            const box = logo.getBoundingClientRect();
            if (!box.width || !box.height) return false;
            const samples = [
                [box.left + box.width * 0.15, box.top + box.height * 0.2],
                [box.left + box.width * 0.5, box.top + box.height * 0.5],
                [box.left + box.width * 0.85, box.top + box.height * 0.8],
                [box.left + box.width * 0.15, box.top + box.height * 0.8],
                [box.left + box.width * 0.85, box.top + box.height * 0.2],
            ];
            for (const [sx, sy] of samples) {
                if (sx < 0 || sy < 0 || sx > window.innerWidth || sy > window.innerHeight) continue;
                const behind = document.elementsFromPoint(sx, sy);
                for (const node of behind) {
                    if (!node || node === logo || node === document.body || node === document.documentElement) continue;
                    if (node.id === '__demo_cursor__' || node.classList?.contains('__demo_cursor_ripple__')) continue;
                    const tag = node.tagName?.toUpperCase() || '';
                    if (['H1','H2','H3','H4','H5','H6','P','SPAN','LABEL','BUTTON','INPUT','SELECT','TEXTAREA','CANVAS','SVG','IMG','A','TABLE','TH','TD','UL','OL','LI','PRE','CODE','I','B','STRONG','EM'].includes(tag)) {
                        return true;
                    }
                    if (node.classList?.contains('card') || node.classList?.contains('card-body') || node.classList?.contains('card-header') || node.classList?.contains('navbar') || node.classList?.contains('modal') || node.classList?.contains('alert')) {
                        return true;
                    }
                    const cs = getComputedStyle(node);
                    const bg = cs.backgroundColor;
                    const hasBg = bg && !['rgba(0, 0, 0, 0)', 'transparent'].includes(bg);
                    const hasBorder = (parseFloat(cs.borderTopWidth) || 0) > 0 || (parseFloat(cs.borderBottomWidth) || 0) > 0 || (parseFloat(cs.borderLeftWidth) || 0) > 0 || (parseFloat(cs.borderRightWidth) || 0) > 0;
                    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
                    if ((hasBg || hasBorder || hasShadow) && node.offsetWidth > 0 && node.offsetHeight > 0) {
                        if (node.offsetWidth >= window.innerWidth * 0.95 && node.offsetHeight >= window.innerHeight * 0.95 && !hasBorder && !hasShadow) {
                            continue;
                        }
                        return true;
                    }
                }
            }
            return false;
        };

        const backdropLuminance = () => {
            const box = logo.getBoundingClientRect();
            const behind = document.elementsFromPoint(
                box.left + box.width / 2, box.top + box.height / 2
            );
            for (const node of [...behind, document.body, document.documentElement]) {
                if (!node) continue;
                const rgba = getComputedStyle(node).backgroundColor.match(/[\d.]+/g);
                if (!rgba || (rgba[3] !== undefined && parseFloat(rgba[3]) < .35)) continue;
                return luminance(rgba.slice(0, 3).map(Number));
            }
            return 1;
        };
        const paint = () => {
            // Keep branding visible; let preflight/recording reject overlap.
            if (hasCollision()) window.__demo_logo_collision__ = true;
            logo.style.opacity = '1';
            logo.style.filter =
                backdropLuminance() < cfg.darkThreshold ? 'invert(1)' : 'none';
        };
        paint();
        setInterval(paint, 400);
    };
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', install, {once: true});
    } else {
        install();
    }
}"""


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
        + 'html.__demo_code_side__ body>*:not(#__code_overlay__){max-width:100%!important;}'
        // Enter and leave like an edit, not a glitch: fade and slide the card,
        // and ease the side-by-side reflow instead of snapping the app over.
        + '#__code_overlay__{transition:opacity 260ms ease,transform 300ms cubic-bezier(.2,.7,.2,1);}'
        + '#__code_overlay__.__code_hidden__{opacity:0;transform:'
        + (sideBySide ? 'translateX(28px)' : 'translateY(22px)') + ';}'
        + 'html.__demo_code_anim__ body{transition:width 260ms ease,max-width 260ms ease,'
        + 'margin 260ms ease;}';
    document.head.appendChild(style);
    const el = document.createElement('div');
    el.id = '__code_overlay__';
    el.className = '__code_hidden__';
    el.style.cssText = sideBySide
        ? 'position:fixed;top:20%;bottom:20%;right:3%;width:41%;z-index:99999;'
            + 'display:flex;flex-direction:column;background:#1D1F21;'
            + 'border:1px solid #48505F;border-radius:10px;'
            + 'box-shadow:0 18px 60px rgba(29,31,33,.55);overflow:hidden;'
        : 'position:fixed;left:4%;right:4%;bottom:4%;max-height:46%;z-index:99999;'
            + 'display:flex;flex-direction:column;background:#1D1F21;'
            + 'border:1px solid #48505F;border-radius:10px;'
            + 'box-shadow:0 18px 60px rgba(29,31,33,.55);overflow:hidden;';
    if (sideBySide) {
        // Pin the current width so the reflow animates from a length, not auto.
        document.body.style.width = document.body.getBoundingClientRect().width + 'px';
        document.documentElement.classList.add('__demo_code_anim__');
        document.body.getBoundingClientRect();
        document.documentElement.classList.add('__demo_code_side__');
    }
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
    windowTitle.textContent = cfg.title + ' — Visual Studio Code';
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
        + 'font-size:' + (sideBySide ? '18px' : '20px') + ';line-height:1.65;color:#FFFFFF;';
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
    el.getBoundingClientRect();
    el.classList.remove('__code_hidden__');
    for (let i = 1; i <= cfg.text.length; i++) {
        const typed = cfg.text.slice(0, i);
        renderLines(focusBlock, typed, focusStart, true);
        updateStatus(typed);
        await new Promise(resolve => setTimeout(resolve, cfg.typeMs));
    }
}"""


CODE_OVERLAY_REMOVE_JS = r"""async () => {
    const root = document.documentElement;
    const el = document.getElementById('__code_overlay__');
    el?.classList.add('__code_hidden__');
    root.classList.remove('__demo_code_side__');
    await new Promise(resolve => setTimeout(resolve, 320));
    el?.remove();
    document.getElementById('__code_overlay_style__')?.remove();
    root.classList.remove('__demo_code_anim__');
    document.body.style.removeProperty('width');
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


def resolve_logo_path(override: Path | None = None) -> Path:
    path = (override or DEFAULT_LOGO_PATH).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Brand logo is missing or empty: {path}. Every recording carries the "
            "Shiny wordmark; restore the skill's assets/shiny-logo.png or pass --logo."
        )
    return path


def logo_overlay_config(orientation: str, logo_path: Path) -> dict:
    if orientation not in LOGO_WIDTHS:
        raise ValueError(f"Unsupported orientation: {orientation}")
    mime = mimetypes.guess_type(logo_path.name)[0] or "image/png"
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return {
        "src": f"data:{mime};base64,{encoded}",
        "width": LOGO_WIDTHS[orientation],
        "darkThreshold": LOGO_DARK_THRESHOLD,
        **LOGO_INSET,
    }


def code_hold_ms(text: str, override: int | None = None, context: str = "") -> int:
    return override or max(
        7500, min(16000, 4800 + 70 * len(text) + 18 * len(context))
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


def start_app(
    project_dir: Path,
    app_type: str,
    host: str,
    port: int,
    output: IO[str] | None = None,
) -> subprocess.Popen:
    """Start the app; `output` redirects its server log to a file instead of here."""
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
    if output is None:
        proc = subprocess.Popen(cmd, cwd=project_dir)
    else:
        proc = subprocess.Popen(
            cmd, cwd=project_dir, stdout=output, stderr=subprocess.STDOUT
        )
    _active_processes.add(proc)
    return proc


def start_app_with_retry(
    project_dir: Path,
    app_type: str,
    host: str,
    port: int,
    url: str,
    attempts: int = 3,
    output: IO[str] | None = None,
) -> subprocess.Popen:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        proc = start_app(project_dir, app_type, host, port, output)
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


def glide_duration_ms(distance: float) -> float:
    """Fitts-style travel time: short hops are quick, long reaches take longer."""
    return min(950.0, 240.0 + 1.1 * distance)


def wait_until(page, deadline: float | None) -> None:
    """Block on the page clock until a monotonic deadline; late is a no-op."""
    if deadline is None:
        return
    remaining = deadline - time.monotonic()
    if remaining > 0.005:
        page.wait_for_timeout(remaining * 1000)


def _glide(
    page, x0: float, y0: float, x1: float, y1: float, duration_ms: float | None = None
) -> None:
    """Travel a gentle arc on a wall-clock schedule, overshoot slightly, settle."""
    dx, dy = x1 - x0, y1 - y0
    distance = (dx**2 + dy**2) ** 0.5
    if distance < 2:
        page.mouse.move(x1, y1)
        return
    duration = (duration_ms if duration_ms is not None else glide_duration_ms(distance)) / 1000
    # Hands arc rather than rule straight lines; bend a little to either side.
    bend = distance * random.uniform(0.05, 0.12) * random.choice((-1.0, 1.0))
    cx = (x0 + x1) / 2 - dy / distance * bend
    cy = (y0 + y1) / 2 + dx / distance * bend
    overshoot = min(6.0, distance * 0.03)
    ox, oy = x1 + dx / distance * overshoot, y1 + dy / distance * overshoot
    started = time.monotonic()
    while True:
        step_started = time.monotonic()
        t = (step_started - started) / duration
        if t >= 1:
            break
        e = _ease_in_out(t)
        u = 1 - e
        page.mouse.move(
            u * u * x0 + 2 * u * e * cx + e * e * ox,
            u * u * y0 + 2 * u * e * cy + e * e * oy,
        )
        # Keep sampling near 60 Hz even when a move returns instantly.
        spent = (time.monotonic() - step_started) * 1000
        if spent < 14:
            page.wait_for_timeout(14 - spent)
    page.mouse.move(ox, oy)
    for i in range(1, 4):
        page.wait_for_timeout(16)
        page.mouse.move(ox + (x1 - ox) * i / 3, oy + (y1 - oy) * i / 3)


def rest_cursor(page, width: int, height: int) -> None:
    """Park the visible cursor in the empty bottom band before the first frame."""
    x, y = width * 0.64, height * 0.86
    page.mouse.move(x, y)
    page._demo_cursor_pos = (x, y)


def move_cursor_to(page, selector: str, arrive_by: float | None = None) -> tuple[float, float]:
    """Glide to `selector`; with `arrive_by`, leave just late enough to land then."""
    locator = page.locator(selector).first
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box is None:
        raise RuntimeError(f"Cursor target is not visible: {selector}")
    x = box["x"] + box["width"] * random.uniform(0.42, 0.58)
    y = box["y"] + box["height"] * random.uniform(0.42, 0.58)
    origin = getattr(page, "_demo_cursor_pos", None) or (x - 240, y - 160)
    duration = glide_duration_ms(((x - origin[0]) ** 2 + (y - origin[1]) ** 2) ** 0.5)
    if arrive_by is not None:
        # A pointer running behind hurries, as a person would, but never jumps.
        available = (arrive_by - time.monotonic() - SETTLE_SECONDS) * 1000
        duration = max(MIN_GLIDE_MS, min(duration, available))
        wait_until(page, arrive_by - SETTLE_SECONDS - duration / 1000)
    _glide(page, origin[0], origin[1], x, y, duration)
    page._demo_cursor_pos = (x, y)
    page._demo_arrived_at = time.monotonic()
    page.wait_for_timeout(random.randint(90, 180))
    return x, y


def human_click(page, selector: str, anchor: float | None = None) -> float:
    """Click like a person; with `anchor`, the press lands on that moment."""
    move_cursor_to(page, selector, None if anchor is None else anchor - ARRIVE_EARLY_SECONDS)
    wait_until(page, anchor)
    reaction = time.monotonic()
    page.mouse.down()
    page.wait_for_timeout(random.randint(70, 135))
    page.mouse.up()
    return reaction


def human_drag(page, config: dict, anchor: float | None = None) -> float:
    x, y = move_cursor_to(
        page, config["selector"], None if anchor is None else anchor - ARRIVE_EARLY_SECONDS
    )
    wait_until(page, anchor)
    reaction = time.monotonic()
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
    return reaction


def typing_pause_ms(char: str, delay: float) -> float:
    """A person's uneven rhythm around `delay`: quicker runs, beats at breaks."""
    pause = delay * random.uniform(0.6, 1.3)
    if char == " ":
        pause *= 1.35
    elif char in ".,;:!?\n":
        pause *= 2.2
    return pause


def human_type(page, selector: str, text: str, delay: float) -> None:
    """Type one key at a time on a schedule, so the average pace stays `delay`."""
    locator = page.locator(selector)
    deadline = time.monotonic()
    for char in text:
        locator.press_sequentially(char, delay=0)
        deadline += typing_pause_ms(char, delay) / 1000
        wait_until(page, deadline)


def validate_action_shape(action: object) -> str:
    if not isinstance(action, dict) or len(action) != 1:
        raise ValueError(f"Each action must contain exactly one key: {action!r}")
    name = next(iter(action))
    if name not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unknown action {name!r}; supported: {sorted(SUPPORTED_ACTIONS)}")
    return name


def assert_no_shiny_client_errors(page) -> None:
    panel_text = page.evaluate(SHINY_CLIENT_ERROR_SCAN_JS)
    if panel_text:
        summary = " ".join(str(panel_text).split())
        raise RuntimeError(
            "Shiny client error panel detected; refusing to record. "
            f"Fix the app and restart the recording. Panel text: {summary}"
        )


def assert_branding_visible(page) -> None:
    problem = page.evaluate("""() => {
        const logo = document.getElementById('__demo_logo__');
        if (!logo || !logo.complete || !logo.naturalWidth) return 'missing logo';
        const box = logo.getBoundingClientRect();
        if (window.__demo_logo_collision__) return 'content overlaps the logo';
        if (box.left < 0 || box.top < 0 || box.right > innerWidth || box.bottom > innerHeight * .2)
            return 'logo lies outside the reserved top band';
        return null;
    }""")
    if problem:
        raise RuntimeError(f"Branding check failed: {problem}; fix the app layout before recording")


def run_actions(
    page,
    actions: list[dict],
    project_dir: Path,
    overlays: dict | None = None,
    orientation: str = "vertical",
    clock_zero: float | None = None,
    cues: dict[int, dict] | None = None,
    video_zero: float | None = None,
) -> list[dict]:
    """Run the action list; each entry records start, end, and reaction times.

    `cues` maps a cue action's index to its target video time; the next visible
    action then reacts on `video_zero + target` instead of after fixed waits.
    """
    timeline: list[dict] = []
    zero = clock_zero if clock_zero is not None else time.monotonic()
    origin = video_zero if video_zero is not None else zero
    pending: dict | None = None
    for index, action in enumerate(actions):
        name = validate_action_shape(action)
        value = action[name]
        started = time.monotonic() - zero
        if name in {"caption", "beat", "label"} and overlays is None:
            raise ValueError(
                f"The {name!r} action requires an `overlays` block in actions.yaml"
            )
        if name == "cue":
            if cues is None or index not in cues:
                raise ValueError(
                    f"Action {index + 1}: cue was not resolved against narration timing"
                )
            pending = cues[index]
            timeline.append(
                {
                    "action": "cue",
                    "start": round(started, 2),
                    "end": round(started, 2),
                    "phrase": pending["phrase"],
                    "target": pending["target"],
                }
            )
            continue
        anchor = origin + pending["target"] if pending and name in VISIBLE_ACTIONS else None
        reaction: float | None = None
        if name == "wait_for":
            page.wait_for_selector(value, state="attached", timeout=15000)
        elif name == "wait":
            page.wait_for_timeout(value)
        elif name == "click":
            reaction = human_click(page, value, anchor)
        elif name == "drag":
            reaction = human_drag(page, value, anchor)
        elif name == "select_option":
            move_cursor_to(
                page, value["selector"], None if anchor is None else anchor - ARRIVE_EARLY_SECONDS
            )
            wait_until(page, anchor)
            reaction = time.monotonic()
            page.locator(value["selector"]).select_option(value["value"])
        elif name == "hover":
            move_cursor_to(page, value, anchor)
            # A hover reacts when the pointer lands, not after it settles.
            reaction = getattr(page, "_demo_arrived_at", None) or time.monotonic()
        elif name == "fill":
            human_click(page, value["selector"], None if anchor is None else anchor - 0.2)
            wait_until(page, anchor)
            reaction = time.monotonic()
            page.locator(value["selector"]).fill(value["value"])
        elif name == "type":
            human_click(page, value["selector"], None if anchor is None else anchor - 0.2)
            page.eval_on_selector(
                value["selector"],
                "el => { el.focus(); if (el.setSelectionRange) "
                "el.setSelectionRange(el.value.length, el.value.length); }",
            )
            wait_until(page, anchor)
            reaction = time.monotonic()
            human_type(page, value["selector"], value["value"], value.get("delay", 45))
        elif name == "press":
            wait_until(page, anchor)
            reaction = time.monotonic()
            page.locator(value["selector"]).press(value["key"])
        elif name == "code":
            config = code_overlay_config(orientation, value)
            text = config["text"]
            wait_until(page, anchor)
            reaction = time.monotonic()
            page.evaluate(CODE_OVERLAY_JS, config)
            page.wait_for_timeout(
                code_hold_ms(
                    text,
                    value.get("duration"),
                    config["before"] + config["after"],
                )
            )
            page.evaluate(CODE_OVERLAY_REMOVE_JS)
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
            index_value = resolve_beat_index(value, overlays["beats"])
            page.evaluate("index => window.__demo_overlays__?.setBeat(index)", index_value)
            page.wait_for_timeout(300)
        elif name == "label":
            page.evaluate(
                "text => window.__demo_overlays__?.setLabel(text)", str(value or "")
            )
            page.wait_for_timeout(300)
        assert_branding_visible(page)
        entry: dict = {
            "action": name,
            "start": round(started, 2),
            "end": round(time.monotonic() - zero, 2),
        }
        if reaction is not None:
            entry["reaction"] = round(reaction - zero, 2)
        if anchor is not None and pending is not None:
            entry["cue"] = {"phrase": pending["phrase"], "target": pending["target"]}
            pending = None
        timeline.append(entry)
    return timeline


class ScreencastCapture:
    """Full-resolution compositor frames stamped on the same wall clock as the actions.

    Chromium sends a JPEG each time the page repaints and holds the newest
    frame until it is acknowledged, so a slow consumer lowers the frame rate
    without ever dropping the final state of a change.
    """

    def __init__(self, context, page, frames_dir: Path, width: int, height: int) -> None:
        self.frames: list[tuple[float, Path]] = []
        self.dir = frames_dir
        self.width, self.height = width, height
        self.dir.mkdir(parents=True, exist_ok=True)
        self.session = context.new_cdp_session(page)
        self.session.on("Page.screencastFrame", self._on_frame)

    def _on_frame(self, event: dict) -> None:
        # Acknowledge first so Chromium can compose the next frame while this
        # one is written; a late ack is what stretches gaps between frames.
        self.session.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        path = self.dir / f"{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((float(event["metadata"]["timestamp"]), path))

    def start(self) -> None:
        self.session.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": SCREENCAST_QUALITY,
                "maxWidth": self.width,
                "maxHeight": self.height,
                "everyNthFrame": 1,
            },
        )

    def stop(self) -> None:
        self.session.send("Page.stopScreencast")


def screencast_manifest(frames: list[tuple[float, Path]], start: float, end: float) -> str:
    """An ffconcat script showing each frame from its timestamp until the next one.

    `start` and `end` are wall-clock seconds; the frame already on screen at
    `start` opens the video so a static opening is never blank.
    """
    ordered = sorted(frames, key=lambda frame: frame[0])
    kept = [frame for frame in ordered if frame[0] < end]
    opening = max((i for i, frame in enumerate(kept) if frame[0] <= start), default=0)
    kept = kept[opening:]
    if not kept:
        raise RuntimeError("The screencast captured no frames inside the recording window")

    def quoted(path: Path) -> str:
        return "'" + str(path).replace("'", "'\\''") + "'"

    lines = ["ffconcat version 1.0"]
    for index, (stamp, path) in enumerate(kept):
        begin = max(stamp, start)
        finish = kept[index + 1][0] if index + 1 < len(kept) else end
        lines.append(f"file {quoted(path)}")
        lines.append(f"duration {max(finish - begin, 0.001):.6f}")
    # The concat demuxer ignores the last duration unless the file repeats.
    lines.append(f"file {quoted(kept[-1][1])}")
    return "\n".join(lines) + "\n"


def encode_screencast(
    frames: list[tuple[float, Path]],
    start: float,
    end: float,
    output: Path,
    width: int,
    height: int,
) -> None:
    manifest = output.with_suffix(".ffconcat")
    manifest.write_text(screencast_manifest(frames, start, end), encoding="utf-8")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest),
                "-vf",
                f"fps={OUTPUT_FPS},scale={width}:{height}:flags=lanczos,format=yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-preset",
                "medium",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )
    finally:
        manifest.unlink(missing_ok=True)


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


def viewport_size(orientation: str) -> tuple[int, int]:
    return (1280, 720) if orientation == "horizontal" else (720, 1280)


def prepare_run(
    actions_path: Path,
    orientation_override: str | None,
    port_override: int | None,
    logo_override: Path | None,
) -> dict:
    """Resolve everything a recording or a preflight needs from actions.yaml."""
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
    logo_path = resolve_logo_path(logo_override)
    return {
        "config": config,
        "url": url,
        "bind_host": bind_host,
        "port": port,
        "orientation": orientation,
        "overlays": normalize_overlays(config),
        "logo": logo_overlay_config(orientation, logo_path),
        "logo_path": logo_path,
    }


def deferred_selectors(actions: list[dict]) -> list[str]:
    """Targets declared as asynchronous through a `wait_for` action."""
    return sorted(
        {
            action["wait_for"]
            for action in actions
            # Runs before shape validation, so ignore anything not a selector.
            if isinstance(action, dict) and isinstance(action.get("wait_for"), str)
        }
    )


def action_shape_problems(actions: list[dict], run: dict) -> list[str]:
    """Everything wrong with the action list that no browser is needed to see."""
    problems: list[str] = []
    for index, action in enumerate(actions, start=1):
        try:
            name = validate_action_shape(action)
            if name == "code":
                code_overlay_config(run["orientation"], action[name])
            elif name in {"caption", "beat", "label"} and run["overlays"] is None:
                raise ValueError(
                    f"the {name!r} action requires an `overlays` block in actions.yaml"
                )
            elif name in {"drag", "select_option", "fill", "type", "press"}:
                if not isinstance(action[name], dict) or "selector" not in action[name]:
                    raise ValueError(f"the {name!r} action needs a `selector`")
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"Action {index}: {exc}")
    problems.extend(validate_demo.cue_problems(actions))
    return problems


def resolve_cues(actions: list[dict], project_dir: Path) -> dict[int, dict]:
    """Target video time for every cue, from the current narration's word timing."""
    if not any(isinstance(action, dict) and "cue" in action for action in actions):
        return {}
    return validate_demo.resolve_cue_times(actions, align_narration.load_timing(project_dir))


def phone_preview(screenshot_path: Path) -> Path | None:
    """Best-effort phone-size copy of the frame, cheap for a reviewer to open."""
    script = Path(__file__).resolve().parent / "review_frames.py"
    if not script.is_file():
        return None
    output = screenshot_path.with_name("preflight-phone.png")
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-dir",
            str(screenshot_path.parent.parent),
            "--images",
            str(screenshot_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    return output if completed.returncode == 0 and output.is_file() else None


def preflight_project(
    project_dir: Path,
    app_type: str,
    actions_path: Path,
    orientation_override: str | None,
    app_dir: Path | None = None,
    port_override: int | None = None,
    logo_override: Path | None = None,
) -> dict:
    """Start the app, resolve every selector, and screenshot — without recording.

    A full take costs a browser run, an encode, a validation, and a frame
    review; catching a missing selector or a client-error panel here costs one
    page load. `problems` is empty when the actions file is ready to record.
    """
    from playwright.sync_api import ViewportSize, sync_playwright

    project_dir = project_dir.resolve()
    app_dir = (app_dir or project_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"App directory does not exist: {app_dir}")

    run = prepare_run(actions_path, orientation_override, port_override, logo_override)
    actions = run["config"]["actions"]
    report: dict = {
        "app_dir": str(app_dir),
        "app_type": app_type,
        "url": run["url"],
        "orientation": run["orientation"],
        "selectors": [],
        "deferred": deferred_selectors(actions),
        "screenshot": None,
        "phone_screenshot": None,
        "app_log": None,
        "problems": action_shape_problems(actions, run),
        "cues": [],
    }
    if not report["problems"]:
        try:
            report["cues"] = [
                {"action": index + 1, **cue}
                for index, cue in sorted(resolve_cues(actions, project_dir).items())
            ]
        except ValueError as exc:
            report["problems"].append(str(exc))
    if report["problems"]:
        # A malformed action list cannot be checked against a live page.
        return report

    checked = collect_selectors(actions)
    width, height = viewport_size(run["orientation"])
    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    screenshot_path = artifacts / "preflight.png"
    log_path = artifacts / "preflight-app.log"
    report["app_log"] = str(log_path)

    # The app's server log belongs in a file, not in the preflight report.
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = start_app_with_retry(
                app_dir, app_type, run["bind_host"], run["port"], run["url"], output=log
            )
        except RuntimeError as exc:
            report["problems"].append(f"{exc}; app output in {log_path}")
            return report
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    args=["--force-device-scale-factor=2", "--high-dpi-support=1"]
                )
                context = browser.new_context(
                    viewport=ViewportSize(width=width, height=height)
                )
                context.add_init_script(CURSOR_OVERLAY_JS)
                context.add_init_script(SHINY_CLIENT_ERROR_GUARD_JS)
                context.add_init_script(
                    f"({LOGO_OVERLAY_JS})({json.dumps(run['logo'])})"
                )
                if run["overlays"] is not None:
                    context.add_init_script(
                        f"({RETENTION_OVERLAY_JS})({json.dumps(run['overlays'])})"
                    )
                page = context.new_page()
                page.goto(run["url"])
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)
                try:
                    assert_no_shiny_client_errors(page)
                    assert_branding_visible(page)
                except RuntimeError as exc:
                    report["problems"].append(str(exc))
                missing = [
                    selector
                    for selector in checked
                    if page.locator(selector).count() == 0
                ]
                report["selectors"] = [
                    selector for selector in checked if selector not in missing
                ]
                if missing:
                    report["problems"].append(
                        "Selectors not found on the initial page: " + ", ".join(missing)
                    )
                page.screenshot(path=str(screenshot_path))
                context.close()
                browser.close()
        finally:
            terminate_process(proc)

    report["screenshot"] = str(screenshot_path)
    preview = phone_preview(screenshot_path)
    report["phone_screenshot"] = str(preview) if preview is not None else None
    return report


def record_project(
    project_dir: Path,
    app_type: str,
    actions_path: Path,
    orientation_override: str | None,
    app_dir: Path | None = None,
    port_override: int | None = None,
    logo_override: Path | None = None,
    capture: str = "screencast",
) -> Path:
    from playwright.sync_api import ViewportSize, sync_playwright

    project_dir = project_dir.resolve()
    app_dir = (app_dir or project_dir).resolve()
    if not app_dir.is_dir():
        raise FileNotFoundError(f"App directory does not exist: {app_dir}")
    if capture not in {"screencast", "playwright"}:
        raise ValueError(f"Unsupported capture mode: {capture}")

    run = prepare_run(actions_path, orientation_override, port_override, logo_override)
    config = run["config"]
    url = run["url"]
    bind_host = run["bind_host"]
    port = run["port"]
    orientation = run["orientation"]
    overlays = run["overlays"]
    logo_path = run["logo_path"]
    logo = run["logo"]
    problems = action_shape_problems(config["actions"], run)
    if problems:
        raise ValueError("; ".join(problems))
    cues = resolve_cues(config["actions"], project_dir)
    width, height = viewport_size(orientation)
    viewport = ViewportSize(width=width, height=height)
    size = ViewportSize(width=width * 2, height=height * 2)

    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    video_name = config.get("video_name", "demo.webm")
    mp4_path = artifacts / Path(video_name).with_suffix(".mp4").name
    frames_dir = artifacts / ".screencast-frames"
    shutil.rmtree(frames_dir, ignore_errors=True)
    proc = start_app_with_retry(app_dir, app_type, bind_host, port, url)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                args=["--force-device-scale-factor=2", "--high-dpi-support=1"]
            )
            context = (
                browser.new_context(
                    viewport=viewport,
                    record_video_dir=str(artifacts),
                    record_video_size=size,
                )
                if capture == "playwright"
                else browser.new_context(viewport=viewport)
            )
            context.add_init_script(CURSOR_OVERLAY_JS)
            context.add_init_script(SHINY_CLIENT_ERROR_GUARD_JS)
            context.add_init_script(f"({LOGO_OVERLAY_JS})({json.dumps(logo)})")
            if overlays is not None:
                context.add_init_script(
                    f"({RETENTION_OVERLAY_JS})({json.dumps(overlays)})"
                )
            page = context.new_page()
            video = page.video
            if capture == "playwright" and video is None:
                raise RuntimeError("Playwright did not attach a video recorder")
            screencast = (
                ScreencastCapture(context, page, frames_dir, size["width"], size["height"])
                if capture == "screencast"
                else None
            )
            recording_started = time.monotonic()
            wall_started = time.time()
            if screencast is not None:
                screencast.start()
            page.goto(url)
            page.wait_for_load_state("networkidle")
            rest_cursor(page, width, height)
            page.wait_for_timeout(3000)
            assert_no_shiny_client_errors(page)
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
            # Trim the page-load preamble so the first action lands near the
            # start of the deliverable and narration timed from zero stays in sync.
            trim_seconds = max(0.0, preamble_seconds - LEAD_SECONDS)
            timeline = run_actions(
                page,
                config["actions"],
                project_dir,
                overlays,
                orientation,
                clock_zero=recording_started,
                cues=cues,
                video_zero=recording_started + trim_seconds,
            )
            assert_no_shiny_client_errors(page)
            assert_branding_visible(page)
            if screencast is not None:
                screencast.stop()
            context.close()
            # The video file is final once its context closes; read its path
            # while Playwright is still running.
            video_source = Path(video.path()) if capture == "playwright" and video else None
            browser.close()

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required to create artifacts/demo.mp4")
        # Cut the tail at the final screenshot: capturing it re-rasterizes the
        # page at 1x, which records as a shrunken frame on a gray canvas.
        screenshot_start = next(
            (entry["start"] for entry in timeline if entry["action"] == "screenshot"),
            None,
        )
        tail = (
            screenshot_start - 0.05
            if screenshot_start is not None and screenshot_start - 0.05 > trim_seconds
            else timeline[-1]["end"] if timeline else trim_seconds + 1.0
        )
        if screencast is not None:
            # Frames and actions share one clock, so the cut is exact.
            encode_screencast(
                screencast.frames,
                wall_started + trim_seconds,
                wall_started + tail,
                mp4_path,
                size["width"],
                size["height"],
            )
            frame_count = len(screencast.frames)
            shutil.rmtree(frames_dir, ignore_errors=True)
        else:
            assert video_source is not None
            webm_path = artifacts / video_name
            if webm_path.exists() and webm_path != video_source:
                webm_path.unlink()
            if video_source != webm_path:
                shutil.move(str(video_source), webm_path)
            if not webm_path.is_file() or webm_path.stat().st_size == 0:
                raise RuntimeError("Playwright did not produce a non-empty WebM recording")
            frame_count = None
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
                    "-t",
                    f"{tail - trim_seconds:.2f}",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "17",
                    "-preset",
                    "fast",
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

        def shifted(value: float) -> float:
            return round(value - trim_seconds, 2)

        (artifacts / "recording.json").write_text(
            json.dumps(
                {
                    "action_timeline": [
                        {
                            **entry,
                            "start": shifted(entry["start"]),
                            "end": shifted(entry["end"]),
                            **(
                                {"reaction": shifted(entry["reaction"])}
                                if "reaction" in entry
                                else {}
                            ),
                        }
                        for entry in timeline
                    ],
                    "capture": {
                        "mode": capture,
                        "fps": OUTPUT_FPS if capture == "screencast" else 25,
                        "source_frames": frame_count,
                        "clock": (
                            "screencast frame timestamps (exact)"
                            if capture == "screencast"
                            else "Playwright video start (approximate)"
                        ),
                    },
                    "logo": {
                        "source": logo_path.name,
                        "width": logo["width"],
                        "top": logo["top"],
                        "left": logo["left"],
                    },
                    "narration_offset_seconds": align_narration.NARRATION_OFFSET_SECONDS,
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
        shutil.rmtree(frames_dir, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--app-type", choices=["python", "r"], default="python")
    parser.add_argument("--actions", type=Path, default=Path("actions.yaml"))
    parser.add_argument("--orientation", choices=["vertical", "horizontal"], default=None)
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--logo",
        type=Path,
        help="Override the top-left brand logo; defaults to the skill's shiny-logo.png",
    )
    parser.add_argument(
        "--capture",
        choices=["screencast", "playwright"],
        default="screencast",
        help="screencast: full-quality 30 fps frames on the action clock (default); "
        "playwright: the legacy 25 fps WebM recorder",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Start the app, resolve every selector, and screenshot without recording",
    )
    return parser.parse_args()


def print_preflight(project_dir: Path, report: dict) -> None:
    verdict = "FAILED" if report["problems"] else "OK"
    print(f"Preflight {verdict} — {project_dir}")
    print(
        f"  app: {report['app_type']} at {report['url']} "
        f"({report['orientation']}, {report['app_dir']})"
    )
    if report["selectors"]:
        print(
            f"  selectors resolved: {len(report['selectors'])} "
            f"({', '.join(report['selectors'])})"
        )
    if report["deferred"]:
        print(f"  deferred to wait_for: {', '.join(report['deferred'])}")
    for cue in report.get("cues", []):
        print(f"  cue {cue['action']}: {cue['phrase'] or 'fixed time'!r} at {cue['target']:.2f}s video time")
    if report["screenshot"]:
        print(f"  frame: {report['screenshot']}")
    if report["phone_screenshot"]:
        print(f"  phone size: {report['phone_screenshot']}")
    if report["problems"] and report["app_log"]:
        print(f"  app log: {report['app_log']}")
    for problem in report["problems"]:
        print(f"  - {problem}")
    print(
        "Fix these before recording."
        if report["problems"]
        else "No client-error panel, every selector resolves. Ready to record."
    )


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
    if args.dry_run:
        try:
            report = preflight_project(
                project_dir,
                args.app_type,
                actions_path,
                args.orientation,
                app_dir,
                args.port,
                args.logo,
            )
        except (RuntimeError, ValueError, FileNotFoundError) as exc:
            print(f"Preflight FAILED — {project_dir}\n  - {exc}")
            return 1
        print_preflight(project_dir, report)
        return 1 if report["problems"] else 0
    mp4_path = record_project(
        project_dir,
        args.app_type,
        actions_path,
        args.orientation,
        app_dir,
        args.port,
        args.logo,
        args.capture,
    )
    print(f"Recorded: {mp4_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
