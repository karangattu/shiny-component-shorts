#!/usr/bin/env python3
"""Stitch per-feature clips into one changelog reel with animated feature cards.

Reads `reel.yaml` in the reel directory:

    title: What's new in Shiny for Python
    release: "1.8.0"              # or "Unreleased"
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
segment: a directory with `explainer.yaml` and `artifacts/narration.wav`. The
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
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_narration import NARRATION_OFFSET_SECONDS  # noqa: E402
from merge_audio import merge, probe_duration  # noqa: E402

FPS = 30
SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
SCALE = 2  # 720x1280 CSS pixels render to the 1440x2560 recording size
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "shiny-logo.png"
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
"""

# Builds the card from JSON with textContent, so changelog text never becomes HTML.
PAGE_JS = r"""
(spec) => {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const at = (node, delay) => { node.style.animationDelay = delay + 's'; return node; };
  document.body.className = spec.orientation;
  document.body.style.setProperty('--accent', spec.accent);
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
    band.append(at(el('div', 'eyebrow rise', spec.eyebrow), 0.05));
    band.append(at(el('div', 'title wipe', spec.title), 0.2));
    band.append(at(el('div', 'bar'), 0.6));
    const list = el('ul', 'list');
    spec.points.forEach((point, i) => {
      const li = at(el('li', 'rise'), point.at);
      li.append(el('b', '', '→'), el('span', '', point.text));
      list.append(li);
    });
    band.append(list);
    if (spec.code) band.append(at(el('div', 'code rise', spec.code), spec.codeAt));
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


def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")


def render_card(browser, spec: dict, output: Path) -> Path:
    """Render a card frame by frame at FPS, so the animation is deterministic."""
    width, height = SIZES[spec["orientation"]]
    spec = {
        "logoSeconds": 0, **spec, "logo": logo_data_uri(),
        "logoWidth": LOGO_WIDTHS[spec["orientation"]], "logoFade": LOGO_FADE_SECONDS,
    }
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=SCALE)
    page.set_content(f"<!doctype html><html><head><style>{PAGE_CSS}</style></head><body></body></html>")
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


def explainer_spec(segment: Path, feature: dict, release: str, orientation: str) -> tuple[dict, Path]:
    """An explainer segment shows its points as the narration reaches them."""
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
    raw_points = config.get("points") or []
    if not 1 <= len(raw_points) <= 4:
        raise SystemExit(f"{segment}/explainer.yaml needs 1-4 points")

    def start_of(sentence: object, fallback: float) -> float:
        if isinstance(sentence, int) and 1 <= sentence <= len(sentences):
            return NARRATION_OFFSET_SECONDS + float(sentences[sentence - 1]["start"])
        return fallback

    points: list[dict[str, Any]] = []
    for number, point in enumerate(raw_points):
        if isinstance(point, str):
            point = {"text": point}
        even = 1.0 + number * max(1.2, (duration - 3.0) / len(raw_points))
        points.append({"text": str(point["text"]), "at": round(start_of(point.get("sentence"), even), 2)})
    code_at = start_of(config.get("code_sentence"), max(points[-1]["at"] + 1.0, duration * 0.6))
    spec = {
        "kind": "explainer",
        "orientation": orientation,
        "accent": feature["accent"],
        "duration": round(duration, 2),
        "eyebrow": config.get("eyebrow") or release,
        "title": config.get("title") or feature["title"],
        "points": points,
        "code": config.get("code"),
        "codeAt": round(code_at, 2),
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


def normalize(source: Path, output: Path, orientation: str, lead: float = 0.0) -> float:
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
    release_label = (
        "Coming in the next release" if release.lower() == "unreleased" else f"New in {release}"
    )
    artifacts = reel_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="reel-") as temp, sync_playwright() as playwright:
        work = Path(temp)
        browser = playwright.chromium.launch()
        try:
            for feature in features:  # explainer segments become clips first
                if (feature["path"] / "explainer.yaml").is_file():
                    spec, audio = explainer_spec(feature["path"], feature, release_label, orientation)
                    silent = feature["path"] / "artifacts" / f"demo{suffix}.mp4"
                    render_card(browser, spec, silent)
                    merge(silent, audio, feature["path"] / "artifacts" / f"final_with_audio{suffix}.mp4")
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
            }, work / "intro.mp4")
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
                }, work / f"card-{number:02d}.mp4")
                plan.append((f"Feature {number} card", card, TRANSITION_IN))
                plan.append((feature["title"], clip, TRANSITION_OUT))
            outro = config.get("outro")
            if outro:
                card = render_card(browser, {
                    "kind": "outro", "orientation": orientation, "accent": ACCENTS[0],
                    "duration": float(outro.get("seconds", OUTRO_SECONDS)),
                    "title": outro.get("title") or "Try it today",
                    "why": outro.get("why") or "", "command": outro.get("command") or "",
                }, work / "outro.mp4")
                plan.append(("Outro", card, TRANSITION_IN))
        finally:
            browser.close()

        pieces = []
        for number, (label, source, transition) in enumerate(plan):
            width, height = video_size(source)
            if (width > height) != (orientation == "horizontal"):
                raise SystemExit(f"{source} is {width}x{height}; the reel is {orientation}")
            normalized = work / f"piece-{number:02d}.mp4"
            # Feature clips start narrating NARRATION_OFFSET_SECONDS in, inside
            # the transition window; the lead keeps the first word clear of it.
            lead = TRANSITION_SECONDS if transition == TRANSITION_OUT else 0.0
            duration = normalize(source, normalized, orientation, lead)
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
