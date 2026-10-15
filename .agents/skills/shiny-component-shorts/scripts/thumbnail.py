#!/usr/bin/env python3
"""Make a cover image for each finished video of a demo.

Takes the payoff frame (one second before the end, after every reaction has
landed) and adds the Shiny logo plus an optional title plate in the reserved
top band. Writes `artifacts/thumbnail.jpg` for the primary video and
`artifacts/thumbnail-<orientation>.jpg` for the companion, sized for upload:
1080x1920 vertical and 1280x720 horizontal, as JPEG under 2 MB.

The title comes from `--title` or a top-level `title:` in `actions.yaml`.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS / "shiny-logo.png"
FONT_PATH = ASSETS / "fonts" / "OpenSans-Latin.woff2"
SIZES = {"vertical": (1080, 1920), "horizontal": (1280, 720)}
PAYOFF_OFFSET_SECONDS = 1.0
MAX_BYTES = 2 * 1024 * 1024

PAGE = """<!doctype html><html><head><style>
@font-face {{ font-family: 'Open Sans'; font-weight: 300 800;
  src: url(data:font/woff2;base64,{font}) format('woff2'); }}
* {{ margin: 0; box-sizing: border-box; }}
html, body {{ width: {width}px; height: {height}px; overflow: hidden; }}
body {{ background: url(data:image/png;base64,{frame}) center / cover no-repeat;
  font-family: 'Open Sans', system-ui, sans-serif; position: relative; }}
.logo {{ position: absolute; top: 4%; left: 4%; width: {logo_width}px; }}
.title {{ position: absolute; left: {title_left}; right: 4%; top: {title_top}; background: #007BC2;
  color: #FFFFFF; font-weight: 800; font-size: {font_size}px; line-height: 1.12;
  padding: .45em .6em; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }}
</style></head><body><img class="logo" src="data:image/png;base64,{logo}"></body></html>"""


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def payoff_frame(video: Path, output: Path) -> None:
    moment = max(0.0, probe_duration(video) - PAYOFF_OFFSET_SECONDS)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{moment:.2f}", "-i", str(video),
         "-frames:v", "1", str(output)],
        check=True,
    )


def logo_is_dark_backdrop(frame: Path) -> bool:
    """Flip the black wordmark to white over a dark top-left corner."""
    out = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(frame), "-vf",
         "crop=iw*0.3:ih*0.1:0:0,scale=1:1,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    return bool(out) and out[0] < 128


def render(frame: Path, output: Path, orientation: str, title: str | None) -> Path:
    from playwright.sync_api import sync_playwright

    width, height = SIZES[orientation]
    vertical = orientation == "vertical"
    html = PAGE.format(
        width=width, height=height,
        frame=base64.b64encode(frame.read_bytes()).decode("ascii"),
        logo=base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii"),
        font=base64.b64encode(FONT_PATH.read_bytes()).decode("ascii"),
        logo_width=round(width * (0.2 if vertical else 0.14)),
        # Vertical: a plate under the logo. Horizontal: beside it, inside the top band.
        title_top="9%" if vertical else "3%",
        title_left="4%" if vertical else f"calc(6% + {round(width * 0.14)}px)",
        font_size=round(width * (0.06 if vertical else 0.03)),
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html)
            if logo_is_dark_backdrop(frame):
                page.eval_on_selector(".logo", "el => el.style.filter = 'invert(1)'")
            if title:
                page.evaluate(
                    "text => { const d = document.createElement('div'); d.className = 'title';"
                    " d.textContent = text; document.body.append(d); }",
                    title,
                )
            page.evaluate("document.fonts.ready")
            for quality in (90, 80, 70):
                page.screenshot(path=str(output), type="jpeg", quality=quality)
                if output.stat().st_size <= MAX_BYTES:
                    break
        finally:
            browser.close()
    return output


def video_orientation(video: Path) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return "horizontal" if int(stream["width"]) > int(stream["height"]) else "vertical"


def project_title(project_dir: Path) -> str | None:
    actions = project_dir / "actions.yaml"
    if not actions.is_file():
        return None
    config = yaml.safe_load(actions.read_text(encoding="utf-8")) or {}
    title = str(config.get("title") or "").strip() if isinstance(config, dict) else ""
    return title or None


def thumbnail_for(video: Path, output: Path, title: str | None) -> Path:
    with tempfile.TemporaryDirectory(prefix="thumb-") as temp:
        frame = Path(temp) / "frame.png"
        payoff_frame(video, frame)
        return render(frame, output, video_orientation(video), title)


def make_thumbnails(project_dir: Path, title: str | None = None) -> list[Path]:
    """Cover images for the primary video and, when present, its companion."""
    artifacts = project_dir / "artifacts"
    title = title or project_title(project_dir)
    made = []
    primary = next(
        (artifacts / name for name in ("final_with_audio.mp4", "demo.mp4") if (artifacts / name).is_file()),
        None,
    )
    if primary is not None:
        made.append(thumbnail_for(primary, artifacts / "thumbnail.jpg", title))
    for orientation in SIZES:
        for name in (f"final_with_audio-{orientation}.mp4", f"demo-{orientation}.mp4"):
            companion = artifacts / name
            if companion.is_file():
                made.append(thumbnail_for(companion, artifacts / f"thumbnail-{orientation}.jpg", title))
                break
    return made


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--title", help="Title plate text; defaults to `title:` in actions.yaml")
    args = parser.parse_args(argv)
    made = make_thumbnails(args.project_dir.resolve(), args.title)
    if not made:
        print("No finished video found in artifacts/", file=sys.stderr)
        return 1
    for path in made:
        print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
