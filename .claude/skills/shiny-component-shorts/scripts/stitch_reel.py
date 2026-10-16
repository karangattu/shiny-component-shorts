#!/usr/bin/env python3
"""Stitch per-feature clips into one changelog reel with animated feature cards.

Reads `reel.yaml` in the reel directory:

    title: What's new in Shiny for Python
    release: "1.8.0"              # or "Unreleased"
    eyebrow: From the Shiny blog  # optional; replaces the "New in 1.8.0" label
    orientation: vertical         # vertical (default) or horizontal
    outro:                        # optional closing card
      title: Try it today
      command: pip install -U shiny
    features:
      - title: Reconnect without losing state
        why: Users keep their inputs after a network blip.
        dir: ../reel-allow-reconnect     # a recorded demo or an explainer segment

Each feature `dir` is either a recorded demo project (its
`artifacts/final_with_audio.mp4`, else `artifacts/demo.mp4`) or an explainer
segment: a directory with `explainer.yaml` and `artifacts/narration.wav`. An
explainer plays 1-4 animated scenes (bullets, flow, compare, code, bars, or a
hand-written html fragment), each starting on a narration sentence. The
script renders explainer segments, then builds an intro card, one animated
card per feature ("2 of 4" plus title and why it helps), and an optional
outro card. It joins everything with crossfades and writes
`artifacts/reel.mp4`, `artifacts/reel.json` (chapter times), and
`artifacts/reel-review.png`, then the same reel in the other orientation as
`reel-<orientation>.mp4` (with matching `.json` and review sheet). Recorded
segments supply that orientation through `companion.py`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, NoReturn

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_narration import NARRATION_OFFSET_SECONDS  # noqa: E402
from merge_audio import merge, probe_duration  # noqa: E402

FPS = 30
SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
SCALE = 2  # 720x1280 CSS pixels render to the 1440x2560 recording size
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "shiny-logo.png"
# Bundled OFL fonts (see assets/fonts/OFL.txt), so cards render the same on every machine.
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONTS = {"Open Sans": "OpenSans-Latin.woff2", "Source Code Pro": "SourceCodePro-Latin.woff2"}
LOGO_WIDTHS = {"vertical": 144, "horizontal": 180}
# Shiny preset palette accents, rotated per feature so each card looks new.
ACCENTS = ["#007BC2", "#00BF7F", "#F9B928", "#BF007F", "#03C7E8", "#F45100", "#74149C"]
# The wordmark shows only at the start of the reel: it fades out on the intro card.
LOGO_SECONDS = 5.0
LOGO_FADE_SECONDS = 0.4
INTRO_SECONDS = 5.4
CARD_SECONDS = 2.6
OUTRO_SECONDS = 3.2
TRANSITION_SECONDS = 0.5
TRANSITION_IN = "smoothleft"  # previous clip -> card
TRANSITION_OUT = "circleopen"  # card -> feature clip
EXPLAINER_TAIL_SECONDS = 0.9
# Explainer scenes: the header draws in first, then each scene replaces the last.
SCENE_TYPES = ("bullets", "flow", "compare", "code", "bars", "html")
MAX_SCENES = 4
FIRST_SCENE_SECONDS = 0.7
MIN_SCENE_SECONDS = 2.0
MAX_CODE_LINES = 12
MAX_CODE_COLUMNS = 64  # wider lines drop below a readable size in the vertical reel
MAX_FEATURES = 6
MAX_SEGMENT_SECONDS = 30.0

PAGE_CSS = """
* { box-sizing: border-box; margin: 0; }
html, body { width: 100%; height: 100%; overflow: hidden; }
body { background: #1D1F21; color: #FFFFFF;
  font-family: 'Open Sans', system-ui, -apple-system, 'Segoe UI', sans-serif; }
.logo { position: absolute; top: 4%; left: 4%; filter: brightness(0) invert(1);
  animation: fadeout var(--logo-fade) ease both; }
@keyframes fadeout { from { opacity: 1; } to { opacity: 0; } }
.band { position: absolute; top: 20%; bottom: 20%; left: 6%; right: 6%;
  display: flex; flex-direction: column; justify-content: center; }
.horizontal .band { left: 8%; right: 8%; }
.glow { position: absolute; width: 140vmax; height: 140vmax; border-radius: 50%;
  left: -20vmax; top: -30vmax; opacity: .16;
  background: radial-gradient(circle, var(--accent) 0%, transparent 60%);
  animation: drift var(--total) linear both; }
@keyframes drift { from { transform: translate(-6%, -4%) scale(1); }
  to { transform: translate(6%, 4%) scale(1.08); } }
.eyebrow { font-size: 22px; font-weight: 700; letter-spacing: .14em;
  text-transform: uppercase; color: #CDD4DA; }
.rise { animation: rise .55s cubic-bezier(.2,.8,.2,1) both; }
@keyframes rise { from { opacity: 0; transform: translateY(28px); }
  to { opacity: 1; transform: none; } }
.wipe { animation: wipe .7s cubic-bezier(.6,0,.2,1) both; }
@keyframes wipe { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
.bar { height: 8px; width: 120px; border-radius: 4px; background: var(--accent);
  transform-origin: left; animation: grow .6s cubic-bezier(.2,.8,.2,1) both; }
@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.count { display: flex; align-items: baseline; gap: 14px; }
.count .num { font-size: 132px; font-weight: 800; line-height: 1; color: var(--accent); }
.count .of { font-size: 34px; font-weight: 600; color: #CDD4DA; }
.title { font-size: 56px; font-weight: 800; line-height: 1.08; }
.why { font-size: 32px; line-height: 1.35; color: #E8ECEF; }
.dots { display: flex; gap: 12px; }
.dot { height: 10px; flex: 1; border-radius: 5px; background: rgba(255,255,255,.18);
  overflow: hidden; }
.dot i { display: block; height: 100%; background: #FFFFFF; transform-origin: left; }
.dot.current i { background: var(--accent); animation: grow .9s .5s ease-out both; }
.dot.future i { transform: scaleX(0); }
.list { display: flex; flex-direction: column; gap: 18px; }
.list li { list-style: none; display: flex; gap: 16px; align-items: baseline;
  font-size: 30px; line-height: 1.3; }
.list li b { color: var(--accent); font-size: 26px; min-width: 42px; }
.code { font-family: 'Source Code Pro', 'SF Mono', ui-monospace, Menlo, monospace;
  font-size: 26px; background: #2A2D30; border-left: 6px solid var(--accent);
  padding: 18px 22px; border-radius: 10px; color: #FFFFFF; white-space: pre-wrap; }
.cmd { font-family: 'Source Code Pro', 'SF Mono', ui-monospace, Menlo, monospace;
  font-size: 30px; background: #FFFFFF; color: #1D1F21; padding: 18px 26px;
  border-radius: 12px; align-self: flex-start; }
.horizontal .title { font-size: 64px; }
.horizontal .count .num { font-size: 120px; }
/* Explainer: a fixed header plus a stage where scenes replace each other. */
.band.split { justify-content: flex-start; }
.horizontal .band.split { flex-direction: row; align-items: stretch; gap: 48px !important; }
.split .head { display: flex; flex-direction: column; gap: 14px; flex: none; }
.horizontal .split .head { width: 30%; justify-content: center; }
.split .head .title { font-size: 46px; }
.stage { position: relative; flex: 1; min-height: 0; min-width: 0; }
.scene { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center;
  animation: enter .6s cubic-bezier(.2,.8,.2,1) both, leave .45s ease-in forwards; }
.fit { display: flex; flex-direction: column; gap: 20px; }
.is-html .fit { flex: 1; }
.fit .list { padding: 0; }
@keyframes enter { from { opacity: 0; transform: translateY(36px); } to { opacity: 1; transform: none; } }
@keyframes leave { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateY(-28px); } }
.still, .still * { animation: none !important; }
.mono, .codebox { font-family: 'Source Code Pro', 'SF Mono', ui-monospace, Menlo, monospace; }
.mono { font-size: .88em; background: rgba(255,255,255,.12); padding: 0 .25em; border-radius: 6px; }
.caption { font-size: 24px; line-height: 1.4; color: #CDD4DA; }
.codebox { font-size: 22px; line-height: 1.55; background: #2A2D30; border-radius: 14px;
  border-left: 6px solid var(--accent); padding: 16px 0; overflow: hidden; white-space: pre; }
.horizontal .codebox { font-size: 20px; }
.ln { display: flex; padding-right: 20px; overflow: hidden; }
.codebox:not(.diff) .ln { padding-left: 22px; }
.codebox:not(.diff) .gut { display: none; }
.gut { flex: none; width: 2em; text-align: center; font-weight: 700; color: #CDD4DA; }
.ln.del { background: rgba(193,0,0,.36); }
.ln.del .txt { text-decoration: line-through; text-decoration-color: rgba(255,255,255,.6); }
.ln.add { background: rgba(0,191,127,.22); }
.ln.add .gut { color: #00BF7F; }
.tc { color: #ADB5BD; } .ts { color: #00BF7F; } .tn, .tf { color: #F9B928; } .tk, .td { color: #03C7E8; }
@keyframes collapse { from { max-height: 1.55em; opacity: 1; } to { max-height: 0; opacity: 0; } }
@keyframes expand { from { max-height: 0; opacity: 0; } to { max-height: 1.55em; opacity: 1; } }
@keyframes mark { to { background: rgba(255,255,255,.12); box-shadow: inset 6px 0 0 var(--accent); } }
@keyframes light { to { border-color: var(--accent); background: #34383C;
  box-shadow: 0 0 0 6px rgba(255,255,255,.05), 0 0 44px -8px var(--accent); } }
@keyframes dim { to { opacity: .45; } }
@keyframes fill-x { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes fill-y { from { transform: scaleY(0); } to { transform: scaleY(1); } }
.flow { display: flex; flex-direction: column; }
.horizontal .flow { flex-direction: row; align-items: stretch; }
.node { background: #2A2D30; border: 3px solid rgba(255,255,255,.16); border-radius: 18px;
  padding: 18px 24px; display: flex; flex-direction: column; justify-content: center; gap: 6px; }
.horizontal .node { flex: 1 1 0; }
.node .label { font-size: 30px; font-weight: 700; line-height: 1.2; }
.node .cap { font-size: 22px; line-height: 1.35; color: #CDD4DA; }
.link { align-self: center; flex: none; width: 6px; height: 40px; border-radius: 3px;
  background: rgba(255,255,255,.16); overflow: hidden; }
.horizontal .link { width: 40px; height: 6px; }
.link i { display: block; width: 100%; height: 100%; background: var(--accent); transform-origin: top; }
.horizontal .link i { transform-origin: left; }
.compare { display: flex; flex-direction: column; gap: 22px; }
.horizontal .compare { flex-direction: row; align-items: stretch; }
.panel { flex: 1 1 0; min-width: 0; background: #2A2D30; border: 3px solid rgba(255,255,255,.12);
  border-radius: 18px; padding: 20px 22px; display: flex; flex-direction: column; gap: 14px; }
.panel .codebox { background: #1D1F21; border-left: none; padding: 12px 0; font-size: 20px; }
.tag { align-self: flex-start; font-size: 18px; font-weight: 800; letter-spacing: .12em;
  text-transform: uppercase; padding: 6px 14px; border-radius: 999px; background: rgba(255,255,255,.16); }
.panel.after .tag { background: var(--accent); color: var(--on-accent); }
.plist { display: flex; flex-direction: column; gap: 10px; padding: 0; }
.plist li { list-style: none; display: flex; gap: 12px; font-size: 26px; line-height: 1.3; }
.plist li b { flex: none; width: 1em; color: #CDD4DA; }
.panel.after .plist li b { color: var(--accent); }
.bars { display: flex; flex-direction: column; gap: 26px; }
.barrow { display: flex; flex-direction: column; gap: 10px; }
.bartop { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; font-size: 26px; }
.bartop b { font-size: 34px; font-weight: 800; }
.track { height: 26px; border-radius: 13px; background: rgba(255,255,255,.1); overflow: hidden; }
.track i { display: block; height: 100%; border-radius: 13px; background: #6C757D; transform-origin: left; }
.barrow.lead .track i { background: var(--accent); }
.custom { position: relative; flex: 1; }
"""

# Builds the card from JSON with textContent, so changelog text never becomes HTML.
# The one exception is an explainer's `html` scene, which the segment author wrote.
PAGE_JS = r"""
async (spec) => {
  await Promise.all([...document.fonts].map((face) => face.load()));
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const at = (node, delay) => { node.style.animationDelay = delay + 's'; return node; };
  const anim = (node, ...parts) => { node.style.animation = parts.join(', '); return node; };
  const EASE = 'cubic-bezier(.2,.8,.2,1)';
  const H = spec.orientation === 'horizontal';
  // `backticks` in any explainer text render as inline code.
  const rich = (tag, cls, text) => {
    const node = el(tag, cls);
    String(text).split('`').forEach((part, i) =>
      node.append(i % 2 ? el('span', 'mono', part) : document.createTextNode(part)));
    return node;
  };
  const TOKENS = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)|(\b(?:def|return|import|from|with|as|if|else|elif|for|in|and|or|not|None|True|False|TRUE|FALSE|NULL|function|class|lambda|async|await|library)\b)|([A-Za-z_][\w.$]*)(?=\()|(@[\w.]+)/g;
  const paint = (line) => {
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of line.matchAll(TOKENS)) {
      frag.append(line.slice(last, m.index));
      const cls = ['tc', 'ts', 'tn', 'tk', 'tf', 'td'][m.slice(1).findIndex((g) => g !== undefined)];
      frag.append(el('span', cls, m[0]));
      last = m.index + m[0].length;
    }
    frag.append(line.slice(last) || (last ? '' : ' '));
    return frag;
  };
  // Lines wipe in one by one; `-` lines collapse and `+` lines open at changeAt.
  const codeBox = (lines, revealAt, changeAt, markAt) => {
    const box = el('div', 'codebox' + (lines.some((l) => l.kind) ? ' diff' : ''));
    const step = Math.min(0.12, 1.2 / lines.length);
    let shown = 0;
    for (const line of lines) {
      const row = el('div', 'ln ' + line.kind);
      const indent = line.text.match(/^\s*/)[0];  // kept out of the strike-through
      const text = el('span', 'txt');
      text.append(paint(line.text.slice(indent.length)));
      row.append(el('b', 'gut', line.kind === 'add' ? '+' : line.kind === 'del' ? '−' : ''), el('span', '', indent), text);
      const parts = line.kind === 'add'
        ? [`expand .5s ${EASE} ${changeAt + 0.25}s both`]
        : [`wipe .45s cubic-bezier(.6,0,.2,1) ${revealAt + step * shown++}s both`];
      if (line.kind === 'del') parts.push(`collapse .45s ease ${changeAt}s forwards`);
      if (line.hl) parts.push(`mark .4s ease ${line.kind === 'add' ? changeAt + 0.8 : markAt}s forwards`);
      box.append(anim(row, ...parts));
    }
    return box;
  };
  const rise = (delay) => `rise .55s ${EASE} ${delay}s both`;
  const SCENES = {
    bullets(fit, s) {
      const list = el('ul', 'list');
      for (const point of s.points) {
        const li = at(el('li', 'rise'), point.at);
        li.append(el('b', '', '→'), rich('span', '', point.text));
        list.append(li);
      }
      fit.append(list);
      if (s.code) fit.append(anim(codeBox(s.code, s.codeAt + 0.1, 0, 0), rise(s.codeAt)));
    },
    flow(fit, s) {
      const flow = el('div', 'flow');
      s.nodes.forEach((item, i) => {
        const appear = s.at + 0.1 + i * 0.12;
        if (i) {
          const link = anim(el('div', 'link'), rise(appear));
          link.append(anim(el('i'), `${H ? 'fill-x' : 'fill-y'} .4s ease-out ${item.at - 0.4}s both`));
          flow.append(link);
        }
        const box = anim(el('div', 'node'), rise(appear), `light .45s ease ${item.at}s forwards`);
        box.append(rich('div', 'label', item.label));
        if (item.caption) box.append(rich('div', 'cap', item.caption));
        flow.append(box);
      });
      fit.append(flow);
    },
    compare(fit, s) {
      const grid = el('div', 'compare');
      const panel = (side, data, appear) => {
        const p = el('div', 'panel ' + side);
        p.append(el('div', 'tag', data.label));
        if (data.code) p.append(codeBox(data.code, appear + 0.2, 0, 0));
        else {
          const list = el('ul', 'plist');
          data.lines.forEach((line, i) => {
            const li = anim(el('li'), rise(appear + 0.15 + i * 0.15));
            li.append(el('b', '', side === 'after' ? '✓' : '–'), rich('span', '', line));
            list.append(li);
          });
          p.append(list);
        }
        grid.append(p);
        return p;
      };
      const before = s.at + 0.2;
      anim(panel('before', s.before, before), rise(before), `dim .5s ease ${s.afterAt}s forwards`);
      anim(panel('after', s.after, s.afterAt), rise(s.afterAt), `light .5s ease ${s.afterAt + 0.3}s forwards`);
      fit.append(grid);
    },
    code(fit, s) { fit.append(codeBox(s.lines, s.at + 0.3, s.changeAt, s.markAt)); },
    bars(fit, s) {
      const bars = el('div', 'bars');
      const max = Math.max(...s.items.map((item) => item.value));
      s.items.forEach((item, i) => {
        const row = anim(el('div', 'barrow' + (i === s.items.length - 1 ? ' lead' : '')), rise(item.at));
        const top = el('div', 'bartop');
        top.append(rich('span', '', item.label), el('b', '', item.text));
        const fill = anim(el('i'), `grow .9s ${EASE} ${item.at + 0.2}s both`);
        fill.style.width = (100 * item.value / max) + '%';
        const track = el('div', 'track');
        track.append(fill);
        row.append(top, track);
        bars.append(row);
      });
      fit.append(bars);
    },
    html(fit, s) {
      const box = el('div', 'custom');
      fit.append(box);
      const range = document.createRange();
      range.selectNodeContents(box);
      box.append(range.createContextualFragment(s.html));  // runs its <script> tags
    },
  };
  // Shrink code that is too wide, then any scene that is too tall, before animating.
  const fitScenes = (stage) => {
    document.body.classList.add('still');
    const room = stage.getBoundingClientRect().height;
    for (const fit of stage.querySelectorAll('.fit')) {
      for (const box of fit.querySelectorAll('.codebox')) {
        let size = parseFloat(getComputedStyle(box).fontSize);
        const wide = () => [...box.children].some((row) => row.scrollWidth > row.clientWidth + 1);
        while (wide() && size > 12) box.style.fontSize = --size + 'px';
      }
      const boxes = [...fit.querySelectorAll('.flow, .node, .panel')];
      const tooBig = () => fit.getBoundingClientRect().height > room + 1
        || boxes.some((box) => box.scrollWidth > box.clientWidth + 1);
      let zoom = 1;
      while (tooBig() && zoom > 0.55) {
        zoom -= 0.05;
        fit.style.zoom = zoom.toFixed(2);
      }
    }
    document.body.classList.remove('still');
  };
  document.body.className = spec.orientation;
  document.body.style.setProperty('--accent', spec.accent);
  document.body.style.setProperty('--on-accent', spec.onAccent || '#FFFFFF');
  document.body.style.setProperty('--total', spec.duration + 's');
  document.body.append(el('div', 'glow'));
  if (spec.logoSeconds > 0) {
    const logo = el('img', 'logo');
    logo.src = spec.logo; logo.style.width = spec.logoWidth + 'px';
    logo.style.setProperty('--logo-fade', spec.logoFade + 's');
    logo.style.animationDelay = (spec.logoSeconds - spec.logoFade) + 's';
    document.body.append(logo);
  }
  const band = el('div', 'band');
  band.style.gap = spec.orientation === 'vertical' ? '30px' : '22px';
  document.body.append(band);
  if (spec.kind === 'intro') {
    band.append(at(el('div', 'eyebrow rise', spec.eyebrow), 0.1));
    band.append(at(el('div', 'title wipe', spec.title), 0.3));
    band.append(at(el('div', 'bar'), 0.8));
    const list = el('ul', 'list');
    spec.items.forEach((item, i) => {
      const li = at(el('li', 'rise'), 1.0 + i * 0.22);
      li.append(el('b', '', String(i + 1).padStart(2, '0')), el('span', '', item));
      list.append(li);
    });
    band.append(list);
  } else if (spec.kind === 'feature') {
    band.append(at(el('div', 'eyebrow rise', spec.eyebrow), 0.05));
    const count = at(el('div', 'count rise'), 0.15);
    count.append(el('span', 'num', String(spec.index).padStart(2, '0')),
                 el('span', 'of', 'of ' + String(spec.total).padStart(2, '0')));
    band.append(count);
    band.append(at(el('div', 'title wipe', spec.title), 0.35));
    if (spec.why) band.append(at(el('div', 'why rise', spec.why), 0.9));
    const dots = at(el('div', 'dots rise'), 0.2);
    for (let i = 1; i <= spec.total; i++) {
      const dot = el('div', 'dot ' + (i < spec.index ? 'past' : i === spec.index ? 'current' : 'future'));
      dot.append(el('i'));
      dots.append(dot);
    }
    band.append(dots);
  } else if (spec.kind === 'explainer') {
    band.classList.add('split');
    const head = el('div', 'head');
    head.append(at(el('div', 'eyebrow rise', spec.eyebrow), 0.05),
                at(el('div', 'title wipe', spec.title), 0.2), at(el('div', 'bar'), 0.6));
    const stage = el('div', 'stage');
    band.append(head, stage);
    // html scenes time their own animations with var(--s1), var(--s2), ...
    spec.sentenceStarts.forEach((start, i) => document.body.style.setProperty('--s' + (i + 1), start + 's'));
    for (const scene of spec.scenes) {
      const node = el('div', 'scene is-' + scene.type);
      node.style.animationDelay = scene.at + 's, ' + (scene.out ?? 9999) + 's';
      node.style.setProperty('--in', scene.at + 's');
      const fit = el('div', 'fit');
      node.append(fit);
      stage.append(node);
      SCENES[scene.type](fit, scene);
      if (scene.caption) fit.append(anim(rich('div', 'caption', scene.caption), rise(scene.captionAt)));
    }
    fitScenes(stage);
  } else {
    band.append(at(el('div', 'title wipe', spec.title), 0.15));
    band.append(at(el('div', 'bar'), 0.6));
    if (spec.why) band.append(at(el('div', 'why rise', spec.why), 0.8));
    if (spec.command) band.append(at(el('div', 'cmd rise', spec.command), 1.1));
  }
  for (const animation of document.getAnimations()) animation.pause();
}
"""

# Seeks every animation; returns a progress signature so unchanged frames are reused.
SEEK_JS = """(ms) => document.getAnimations().map((a) => {
  a.currentTime = ms;
  const p = a.effect.getComputedTiming().progress;
  return p === null ? -1 : Math.round(p * 1000);
}).join(',')"""


def font_css() -> str:
    faces = []
    for family, name in FONTS.items():
        data = base64.b64encode((FONT_DIR / name).read_bytes()).decode("ascii")
        faces.append(
            f"@font-face {{ font-family: '{family}'; font-weight: 300 800; font-style: normal; "
            f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}"
        )
    return "\n".join(faces)


def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")


SCRIPT_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_key(*parts: object) -> str:
    """Key a rendered piece by everything that shapes it, this script included."""
    payload = json.dumps([SCRIPT_DIGEST, *parts], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def from_cache(cache: Path | None, key: str, output: Path, build) -> Path:
    """Reuse `cache/<key>.mp4` when present; otherwise build it there first."""
    if cache is None:
        build(output)
        return output
    cache.mkdir(parents=True, exist_ok=True)
    stored = cache / f"{key}.mp4"
    if not stored.is_file() or stored.stat().st_size == 0:
        partial = stored.with_suffix(".partial.mp4")
        build(partial)
        partial.replace(stored)
    if output != stored:
        shutil.copy2(stored, output)
    return output


def render_card(browser, spec: dict, output: Path, cache: Path | None = None) -> Path:
    """Render a card frame by frame at FPS, so the animation is deterministic."""
    key = "card-" + cache_key(
        spec, file_digest(LOGO_PATH), *(file_digest(FONT_DIR / name) for name in FONTS.values())
    )
    return from_cache(cache, key, output, lambda target: _render_card(browser(), spec, target))


def _render_card(browser, spec: dict, output: Path) -> Path:
    width, height = SIZES[spec["orientation"]]
    spec = {
        "logoSeconds": 0, **spec, "logo": logo_data_uri(),
        "logoWidth": LOGO_WIDTHS[spec["orientation"]], "logoFade": LOGO_FADE_SECONDS,
    }
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=SCALE)
    page.set_content(f"<!doctype html><html><head><style>{font_css()}{PAGE_CSS}</style></head><body></body></html>")
    page.evaluate(PAGE_JS, spec)
    page.evaluate("document.fonts.ready")
    encoder = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
            "-c:v", "png", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
            "-pix_fmt", "yuv420p", "-r", str(FPS), str(output),
        ],
        stdin=subprocess.PIPE,
    )
    assert encoder.stdin is not None
    previous_signature, frame = None, b""
    for index in range(round(spec["duration"] * FPS)):
        signature = page.evaluate(SEEK_JS, index * 1000 / FPS)
        if signature != previous_signature:
            frame = page.screenshot(type="png")
            previous_signature = signature
        encoder.stdin.write(frame)
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError(f"ffmpeg failed to encode {output}")
    page.close()
    return output


def on_accent(color: str) -> str:
    """The text color with more contrast on an accent fill: white or the dark text color."""
    channels = [int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    red, green, blue = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#FFFFFF" if 1.05 / (luminance + 0.05) >= (luminance + 0.05) / 0.0637 else "#1D1F21"


def code_lines(text: object, highlight: object = None) -> list[dict]:
    """Split a code block into lines; a leading `+ ` or `- ` marks an added or removed line."""
    marked = set(highlight) if isinstance(highlight, list) else set()
    lines = []
    for number, line in enumerate(str(text).rstrip("\n").split("\n"), start=1):
        kind = ""
        if line[:2] in ("+ ", "- ") or line in ("+", "-"):
            kind, line = ("add" if line[0] == "+" else "del"), line[2:]
        lines.append({"text": line, "kind": kind, "hl": number in marked})
    return lines


def scene_spec(
    scene: dict, number: int, start: float, end: float,
    start_of: Callable[[object, float | None], float | None], fail: Callable[[str], NoReturn], segment: Path,
) -> dict:
    """Resolve one scene's content and the clip time of every beat inside it."""
    where = f"scene {number}"

    def beat(sentence: object, fallback: float, label: str) -> float:
        moment = start_of(sentence, None)
        if moment is None:  # untimed beats are kept inside their own scene
            return round(min(max(fallback, start), end - 0.4), 2)
        if start - 1.0 <= moment < start + 0.4:  # e.g. sentence 1, which starts before the header draws
            moment = start + 0.4
        if not start <= moment < end - 0.3:
            fail(f"{where}: {label} lands at {moment:.1f}s, outside its scene ({start:.1f}-{end:.1f}s)")
        return round(moment, 2)

    def spread(items: list, lead: float = 0.4) -> list[float]:
        step = max(0.0, end - start - lead - 0.8) / len(items)
        return [start + lead + index * step for index in range(len(items))]

    def listed(key: str, low: int, high: int) -> list:
        items = scene.get(key)
        if not isinstance(items, list) or not low <= len(items) <= high:
            fail(f"{where} ({scene['type']}) needs {low}-{high} {key}")
        return items

    def code(text: object, highlight: object = None) -> list[dict]:
        lines = code_lines(text, highlight)
        if len(lines) > MAX_CODE_LINES:
            fail(f"{where} has {len(lines)} code lines; keep it to {MAX_CODE_LINES}")
        for line in lines:
            if len(line["text"]) > MAX_CODE_COLUMNS:
                fail(f"{where}: shorten or wrap this code line to {MAX_CODE_COLUMNS} characters: {line['text'].strip()}")
        return lines

    kind = scene["type"]
    out: dict[str, Any] = {}
    if kind == "bullets":
        points = [p if isinstance(p, dict) else {"text": p} for p in listed("points", 1, 4)]
        out["points"] = [
            {"text": str(p["text"]), "at": beat(p.get("sentence"), even, f"point {i}")}
            for i, (p, even) in enumerate(zip(points, spread(points)), start=1)
        ]
        if scene.get("code"):
            out["code"] = code(scene["code"])
            fallback = max(out["points"][-1]["at"] + 1.0, start + (end - start) * 0.6)
            out["codeAt"] = beat(scene.get("code_sentence"), fallback, "code")
    elif kind == "flow":
        nodes = [n if isinstance(n, dict) else {"label": n} for n in listed("nodes", 2, 4)]
        out["nodes"] = [
            {"label": str(n["label"]), "caption": str(n.get("caption") or ""),
             "at": beat(n.get("sentence"), even, f"node {i}")}
            for i, (n, even) in enumerate(zip(nodes, spread(nodes)), start=1)
        ]
    elif kind == "compare":
        for side, label in (("before", "Before"), ("after", "Now")):
            data = scene.get(side)
            if not isinstance(data, dict) or not (data.get("code") or data.get("lines")):
                fail(f"{where} (compare) needs `{side}:` with `code:` or `lines:`")
            lines = data.get("lines") or []
            if not data.get("code") and not 1 <= len(lines) <= 4:
                fail(f"{where} (compare) {side} needs 1-4 lines")
            out[side] = {
                "label": str(data.get("label") or label),
                "code": code(data["code"]) if data.get("code") else None,
                "lines": [str(line) for line in lines],
            }
        out["afterAt"] = beat(scene.get("after_sentence"), start + (end - start) * 0.45, "after")
    elif kind == "code":
        if not scene.get("code"):
            fail(f"{where} (code) needs `code:`")
        out["lines"] = code(scene["code"], scene.get("highlight"))
        changes = any(line["kind"] for line in out["lines"])
        out["changeAt"] = (
            beat(scene.get("change_sentence"), start + max(1.8, (end - start) * 0.45), "change")
            if changes else 0
        )
        mark = out["changeAt"] + 0.8 if changes else start + 1.6
        out["markAt"] = beat(scene.get("highlight_sentence"), mark, "highlight")
    elif kind == "bars":
        items = listed("items", 2, 4)
        if not all(isinstance(i, dict) and isinstance(i.get("value"), (int, float)) and i["value"] > 0 for i in items):
            fail(f"{where} (bars) items need a `label` and a positive `value`")
        out["items"] = [
            {"label": str(i.get("label") or ""), "value": float(i["value"]),
             "text": str(i.get("text") or i["value"]), "at": beat(i.get("sentence"), even, f"bar {n}")}
            for n, (i, even) in enumerate(zip(items, spread(items)), start=1)
        ]
    else:  # html: a scene the author animates with CSS, timed with var(--in) and var(--sN)
        path = segment / str(scene.get("file") or "")
        if not scene.get("file") or not path.is_file():
            fail(f"{where} (html) needs `file:` naming an HTML fragment in {segment}")
        out["html"] = path.read_text(encoding="utf-8")
    caption = scene.get("caption")
    out.update(
        type=kind,
        caption=str(caption) if caption else "",
        captionAt=beat(scene.get("caption_sentence"), start + 0.9, "caption") if caption else 0,
    )
    return out


def explainer_spec(segment: Path, feature: dict, release: str, orientation: str) -> tuple[dict, Path]:
    """An explainer segment plays 1-4 animated scenes, each on cue with its narration."""
    config = yaml.safe_load((segment / "explainer.yaml").read_text(encoding="utf-8")) or {}
    audio = segment / "artifacts" / "narration.wav"
    if not audio.is_file():
        raise SystemExit(
            f"{segment}: explainer segments need artifacts/narration.wav; run the batch "
            "narration phase on this directory first"
        )
    duration = NARRATION_OFFSET_SECONDS + probe_duration(audio) + EXPLAINER_TAIL_SECONDS
    sentences: list[dict] = []
    timing = segment / "artifacts" / "narration-timing.json"
    if timing.is_file():
        sentences = json.loads(timing.read_text(encoding="utf-8")).get("sentences") or []
    sentence_starts = [round(NARRATION_OFFSET_SECONDS + float(s["start"]), 2) for s in sentences]

    def fail(message: str) -> NoReturn:
        raise SystemExit(f"{segment}/explainer.yaml: {message}")

    def start_of(sentence: object, fallback: float | None) -> float | None:
        if isinstance(sentence, int) and 1 <= sentence <= len(sentence_starts):
            return sentence_starts[sentence - 1]
        return fallback

    raw = config.get("scenes")
    if raw is None:  # the original format: one scene of benefit points
        raw = [{"type": "bullets", **{k: config[k] for k in ("points", "code", "code_sentence") if k in config}}]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SCENES:
        fail(f"needs 1-{MAX_SCENES} scenes")
    starts: list[float] = []
    for number, scene in enumerate(raw):
        if not isinstance(scene, dict) or scene.get("type") not in SCENE_TYPES:
            fail(f"scene {number + 1} needs a `type`: one of {', '.join(SCENE_TYPES)}")
        even = FIRST_SCENE_SECONDS + number * (duration - FIRST_SCENE_SECONDS - EXPLAINER_TAIL_SECONDS) / len(raw)
        starts.append(max(FIRST_SCENE_SECONDS, start_of(scene.get("sentence"), even) or even))
    if any(later - earlier < MIN_SCENE_SECONDS for earlier, later in zip(starts, starts[1:])):
        fail(f"scenes must start in order and at least {MIN_SCENE_SECONDS:g}s apart")
    scenes = []
    for number, scene in enumerate(raw):
        end = starts[number + 1] if number + 1 < len(raw) else duration
        built = scene_spec(scene, number + 1, starts[number], end, start_of, fail, segment)
        built.update(at=round(starts[number], 2), out=round(end, 2) if number + 1 < len(raw) else None)
        scenes.append(built)
    spec = {
        "kind": "explainer",
        "orientation": orientation,
        "accent": feature["accent"],
        "onAccent": on_accent(feature["accent"]),
        "duration": round(duration, 2),
        "eyebrow": config.get("eyebrow") or release,
        "title": config.get("title") or feature["title"],
        "scenes": scenes,
        "sentenceStarts": sentence_starts,
    }
    return spec, audio


def has_audio(path: Path) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())


def video_size(path: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def normalize(
    source: Path, output: Path, orientation: str, lead: float = 0.0, cache: Path | None = None
) -> float:
    """Normalize one piece, reusing a cached encode of the same source."""
    key = "piece-" + cache_key(file_digest(source), orientation, lead)
    from_cache(cache, key, output, lambda target: _normalize(source, target, orientation, lead))
    return probe_duration(source) + lead


def _normalize(source: Path, output: Path, orientation: str, lead: float = 0.0) -> float:
    """Re-encode one piece to the shared size, frame rate, and stereo AAC track.

    `lead` holds the first frame and delays the audio by that many seconds, so
    a transition into the piece covers the hold instead of its first words.
    """
    width, height = (SIZES[orientation][0] * SCALE, SIZES[orientation][1] * SCALE)
    duration = probe_duration(source) + lead
    hold = f"tpad=start_duration={lead:.3f}:start_mode=clone," if lead else ""
    delay = f"adelay={round(lead * 1000)}:all=1," if lead else ""
    video = (
        f"[0:v]{hold}scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#1D1F21,"
        f"fps={FPS},format=yuv420p,setsar=1[v]"
    )
    audio = (
        f"[0:a]{delay}aresample=48000,aformat=channel_layouts=stereo,apad[a]"
        if has_audio(source)
        else "[1:a]aformat=channel_layouts=stereo[a]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]",
            "-t", f"{duration:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", str(output),
        ],
        check=True,
    )
    return duration


def join(pieces: list[tuple[Path, float, str]], output: Path) -> list[float]:
    """Crossfade pieces in order; returns each piece's start time in the reel."""
    inputs: list[str] = []
    for path, _, _ in pieces:
        inputs += ["-i", str(path)]
    filters, starts = [], [0.0]
    video, audio, length = "[0:v]", "[0:a]", pieces[0][1]
    for index, (_, duration, transition) in enumerate(pieces[1:], start=1):
        offset = length - TRANSITION_SECONDS
        filters.append(
            f"{video}[{index}:v]xfade=transition={transition}:duration={TRANSITION_SECONDS}:"
            f"offset={offset:.3f}[v{index}]"
        )
        filters.append(f"{audio}[{index}:a]acrossfade=d={TRANSITION_SECONDS}[a{index}]")
        video, audio = f"[v{index}]", f"[a{index}]"
        starts.append(offset)
        length = offset + duration
    command = ["ffmpeg", "-y", "-loglevel", "error", *inputs]
    if filters:
        command += ["-filter_complex", ";".join(filters), "-map", video, "-map", audio]
    command += [
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    return starts


def review_sheet(reel: Path, chapters: list[dict], output: Path, workdir: Path) -> None:
    """One frame from the middle of every chapter, tiled for a single look."""
    frames = []
    for number, chapter in enumerate(chapters):
        frame = workdir / f"review-{number:02d}.png"
        middle = (chapter["start"] + chapter["end"]) / 2
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{middle:.2f}", "-i", str(reel),
             "-frames:v", "1", "-vf", "scale=360:-2", str(frame)],
            check=True,
        )
        frames.append(frame)
    columns = min(len(frames), 6)
    rows = -(-len(frames) // columns)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1", "-i",
         str(workdir / "review-%02d.png"), "-vf", f"tile={columns}x{rows}:padding=8:color=white",
         "-frames:v", "1", str(output)],
        check=True,
    )


def load_reel(reel_dir: Path) -> dict:
    path = reel_dir / "reel.yaml"
    if not path.is_file():
        raise SystemExit(f"Missing {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    features = config.get("features") or []
    if not features:
        raise SystemExit("reel.yaml lists no features")
    if len(features) > MAX_FEATURES:
        raise SystemExit(
            f"reel.yaml lists {len(features)} features; keep a reel to {MAX_FEATURES} "
            "and split the rest into a second reel"
        )
    orientation = config.get("orientation", "vertical")
    if orientation not in SIZES:
        raise SystemExit(f"Unsupported orientation: {orientation}")
    for number, feature in enumerate(features, start=1):
        for key in ("title", "dir"):
            if not feature.get(key):
                raise SystemExit(f"Feature {number} needs a {key!r}")
        feature["accent"] = feature.get("accent") or ACCENTS[(number - 1) % len(ACCENTS)]
        directory = Path(str(feature["dir"])).expanduser()
        feature["path"] = (directory if directory.is_absolute() else reel_dir / directory).resolve()
    config["orientation"] = orientation
    return config


def segment_clip(feature: dict, orientation: str) -> Path | None:
    """The segment's video in this orientation: its primary file or its companion."""
    artifacts = feature["path"] / "artifacts"
    for suffix in (f"-{orientation}", ""):
        for name in (f"final_with_audio{suffix}.mp4", f"demo{suffix}.mp4"):
            path = artifacts / name
            if path.is_file():
                width, height = video_size(path)
                if (width > height) == (orientation == "horizontal"):
                    return path
    return None


def build(reel_dir: Path, orientation: str | None = None) -> dict:
    """Build the reel in one orientation; the primary one is `reel.mp4`."""
    from playwright.sync_api import sync_playwright

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required")
    config = load_reel(reel_dir)
    orientation = orientation or config["orientation"]
    # The companion orientation gets the same reel under a suffixed name.
    suffix = "" if orientation == config["orientation"] else f"-{orientation}"
    features = config["features"]
    release = str(config.get("release") or "Unreleased")
    # A reel that is not a release (a blog post walkthrough) sets its own eyebrow.
    release_label = str(config.get("eyebrow") or (
        "Coming in the next release" if release.lower() == "unreleased" else f"New in {release}"
    ))
    artifacts = reel_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    # Rendered cards and normalized clips are reused while their inputs match.
    cache = artifacts / ".reel-cache"
    with tempfile.TemporaryDirectory(prefix="reel-") as temp, sync_playwright() as playwright:
        work = Path(temp)
        launched: list = []

        def browser():  # launched only when a card is not cached
            if not launched:
                launched.append(playwright.chromium.launch())
            return launched[0]

        try:
            for feature in features:  # explainer segments become clips first
                if (feature["path"] / "explainer.yaml").is_file():
                    spec, audio = explainer_spec(feature["path"], feature, release_label, orientation)
                    segment_artifacts = feature["path"] / "artifacts"
                    silent = segment_artifacts / f"demo{suffix}.mp4"
                    final = segment_artifacts / f"final_with_audio{suffix}.mp4"
                    stamp = segment_artifacts / f".explainer{suffix}.key"
                    key = cache_key(
                        spec, file_digest(audio), file_digest(LOGO_PATH),
                        *(file_digest(FONT_DIR / name) for name in FONTS.values()),
                    )
                    if final.is_file() and stamp.is_file() and stamp.read_text() == key:
                        print(f"Reused explainer {feature['path'].name}")
                        continue
                    render_card(browser, spec, silent, cache)
                    merge(silent, audio, final)
                    stamp.write_text(key)
                    print(f"Rendered explainer {feature['path'].name} ({spec['duration']:.1f}s)")
            plan: list[tuple[str, Path, str]] = []
            intro_seconds = float(config.get("intro_seconds", INTRO_SECONDS))
            if intro_seconds < LOGO_SECONDS:
                raise SystemExit(
                    f"intro_seconds must be at least {LOGO_SECONDS}: "
                    "the logo stays on the intro card for its first 5 seconds"
                )
            intro = render_card(browser, {
                "kind": "intro", "orientation": orientation, "accent": ACCENTS[0],
                "duration": intro_seconds, "logoSeconds": LOGO_SECONDS,
                "eyebrow": release_label,
                "title": config.get("title") or "What's new in Shiny",
                "items": [feature["title"] for feature in features],
            }, work / "intro.mp4", cache)
            plan.append(("Intro", intro, ""))
            for number, feature in enumerate(features, start=1):
                clip = segment_clip(feature, orientation)
                if clip is None:
                    raise SystemExit(
                        f"{feature['path']}: no {orientation} video yet; record it and run "
                        "companion.py for the other orientation"
                    )
                if clip.name.startswith("demo"):
                    warnings.append(f"{feature['path'].name}: using silent demo.mp4")
                recording = feature["path"] / "artifacts" / "recording.json"
                if recording.is_file():
                    logo = json.loads(recording.read_text(encoding="utf-8")).get("logo") or {}
                    if logo.get("visible_seconds", LOGO_SECONDS) > 0:
                        warnings.append(
                            f"{feature['path'].name}: recorded with the logo; set "
                            "`logo_seconds: 0` in its actions.yaml and record it again"
                        )
                card = render_card(browser, {
                    "kind": "feature", "orientation": orientation, "accent": feature["accent"],
                    "duration": float(config.get("card_seconds", CARD_SECONDS)),
                    "eyebrow": release_label, "index": number, "total": len(features),
                    "title": feature["title"], "why": feature.get("why") or "",
                }, work / f"card-{number:02d}.mp4", cache)
                plan.append((f"Feature {number} card", card, TRANSITION_IN))
                plan.append((feature["title"], clip, TRANSITION_OUT))
            outro = config.get("outro")
            if outro:
                card = render_card(browser, {
                    "kind": "outro", "orientation": orientation, "accent": ACCENTS[0],
                    "duration": float(outro.get("seconds", OUTRO_SECONDS)),
                    "title": outro.get("title") or "Try it today",
                    "why": outro.get("why") or "", "command": outro.get("command") or "",
                }, work / "outro.mp4", cache)
                plan.append(("Outro", card, TRANSITION_IN))
        finally:
            for opened in launched:
                opened.close()

        pieces = []
        for number, (label, source, transition) in enumerate(plan):
            width, height = video_size(source)
            if (width > height) != (orientation == "horizontal"):
                raise SystemExit(f"{source} is {width}x{height}; the reel is {orientation}")
            normalized = work / f"piece-{number:02d}.mp4"
            # Feature clips start narrating NARRATION_OFFSET_SECONDS in, inside
            # the transition window; the lead keeps the first word clear of it.
            lead = TRANSITION_SECONDS if transition == TRANSITION_OUT else 0.0
            duration = normalize(source, normalized, orientation, lead, cache)
            if label in {feature["title"] for feature in features} and duration - lead > MAX_SEGMENT_SECONDS:
                warnings.append(f"{label}: {duration - lead:.1f}s is long for a reel segment")
            pieces.append((normalized, duration, transition or "fade"))
        reel = artifacts / f"reel{suffix}.mp4"
        starts = join(pieces, reel)
        total = probe_duration(reel)
        chapters = []
        for number, (label, _, _) in enumerate(plan):
            end = starts[number + 1] if number + 1 < len(starts) else total
            chapters.append({"label": label, "start": round(starts[number], 2), "end": round(end, 2)})
        review_sheet(reel, chapters, artifacts / f"reel-review{suffix}.png", work)
        # Cover image: the intro card once its feature list has drawn in.
        thumb_width, thumb_height = (1080, 1920) if orientation == "vertical" else (1280, 720)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(3.5, float(chapters[0]['end']) - 0.6):.2f}",
             "-i", str(reel), "-frames:v", "1", "-vf", f"scale={thumb_width}:{thumb_height}",
             "-q:v", "3", str(artifacts / f"reel-thumbnail{suffix}.jpg")],
            check=True,
        )

    report = {
        "reel": str(reel),
        "duration_seconds": round(total, 2),
        "orientation": orientation,
        "release": release,
        "chapters": chapters,
        "warnings": warnings,
    }
    (artifacts / f"reel{suffix}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reel-dir", type=Path, required=True, help="Directory holding reel.yaml")
    parser.add_argument(
        "--orientation", choices=("both", "vertical", "horizontal"), default="both",
        help="Every reel ships in both orientations unless you ask for one",
    )
    args = parser.parse_args(argv)
    reel_dir = args.reel_dir.resolve()
    primary = load_reel(reel_dir)["orientation"]
    orientations = (
        [primary, "horizontal" if primary == "vertical" else "vertical"]
        if args.orientation == "both"
        else [args.orientation]
    )
    for orientation in orientations:
        report = build(reel_dir, orientation)
        print(f"Wrote {report['reel']} ({report['duration_seconds']:.1f}s)")
        for chapter in report["chapters"]:
            minutes, seconds = divmod(chapter["start"], 60)
            print(f"  {int(minutes)}:{seconds:05.2f}  {chapter['label']}")
        for warning in report["warnings"]:
            print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
