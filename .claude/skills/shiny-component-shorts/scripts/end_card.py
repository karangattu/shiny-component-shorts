"""Closing end card: one next step for the viewer, shown after the narration ends.

The card is silent, dissolves in over the last frame, and holds for a few seconds. It shows the
Shiny wordmark, a short title, an optional install command, and a link:

    outro:
      title: Try Shiny 1.9 today
      command: pip install shiny --upgrade
      link: shiny.posit.co
      seconds: 4

Editorial videos (`reel.yaml`) get the card by default; write `outro: false`
to leave it out. Standalone component videos get it when `actions.yaml` has an
`outro` key (`outro: true` uses the defaults); `merge_audio.py` appends it.
"""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

import code_style

SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
SECONDS = 4.0
DISSOLVE_SECONDS = 0.3
SECONDS_RANGE = (2.0, 8.0)
LINK = "shiny.posit.co"
COMMANDS = {"python": "pip install shiny --upgrade", "r": 'install.packages("shiny")'}
KEYS = ("title", "command", "link", "seconds")
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "shiny-logo.png"
VERSION_RE = re.compile(r"(?:shiny\s+)?v?(\d+(?:\.\d+)*)", re.IGNORECASE)


def language_of(*directories: Path) -> str:
    """R only when a directory has `app.R` and no `app.py`."""
    for directory in directories:
        if (directory / "app.R").is_file() and not (directory / "app.py").is_file():
            return "r"
    return "python"


def resolve(outro: object, *, release: object = None, language: str = "python") -> dict | None:
    """Fill the card's defaults; `False` means the video ends without a card.

    A numbered release gets "Try Shiny <version> today" and the upgrade
    command. An unreleased one gets no command by default, because the
    upgrade would not install the feature the video shows.
    """
    if outro is False:
        return None
    if outro is None or outro is True:
        outro = {}
    if not isinstance(outro, dict) or set(outro) - set(KEYS):
        raise ValueError("outro must be false or a mapping with only: " + ", ".join(KEYS))
    name = str(release or "").strip()
    version = VERSION_RE.fullmatch(name)
    if version:
        # "1.9.0" reads as "Shiny 1.9"; a real patch release keeps its number.
        number = re.sub(r"^(\d+\.\d+)\.0$", r"\1", version.group(1))
        title, command = f"Try Shiny {number} today", COMMANDS[language]
    elif name:
        title, command = "Learn more about Shiny", ""
    else:
        title, command = "Try it yourself", COMMANDS[language]
    card = {
        "title": outro.get("title", title),
        "command": outro.get("command", command) or "",
        "link": outro.get("link", LINK) or "",
        "seconds": outro.get("seconds", SECONDS),
    }
    for key in ("title", "command", "link"):
        if not isinstance(card[key], str):
            raise ValueError(f"outro.{key} must be text")
        card[key] = card[key].strip()
    if not card["title"]:
        raise ValueError("outro.title must be readable text")
    seconds = card["seconds"]
    low, high = SECONDS_RANGE
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not low <= seconds <= high:
        raise ValueError(f"outro.seconds must be between {low:g} and {high:g}")
    card["seconds"] = float(seconds)
    return card


def for_project(project_dir: Path) -> dict | None:
    """The card a standalone component video asked for in `actions.yaml`, if any."""
    actions = project_dir / "actions.yaml"
    if not actions.is_file():
        return None
    config = yaml.safe_load(actions.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("outro") in (None, False):
        return None
    return resolve(config["outro"], language=language_of(project_dir))


def render(browser, card: dict, orientation: str, output: Path, scale: float = 2) -> Path:
    """Draw the card as one still; refuse text that does not fit the safe margins."""
    width, height = SIZES[orientation]
    logo = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    command = (
        f'<pre><code>{html.escape(card["command"])}</code></pre>' if card["command"] else ""
    )
    link = (
        f'<p class="link">Learn more at <b>{html.escape(card["link"])}</b></p>'
        if card["link"] else ""
    )
    css = code_style.font_css() + f"""*{{box-sizing:border-box;margin:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#F8F8F8;color:#1D1F21;font-family:'Open Sans',sans-serif}}
main{{position:absolute;inset:5%;display:flex;flex-direction:column;align-items:center;
  justify-content:center;text-align:center}}
img{{width:200px;margin-bottom:56px}}
h1{{font-size:60px;line-height:1.14;font-weight:700;letter-spacing:-.03em;max-width:100%}}
pre{{margin-top:44px;max-width:100%;padding:18px 28px;background:#FFFFFF;border:1px solid #CDD4DA;
  border-radius:10px;font:500 30px/1.45 'Source Code Pro',monospace;white-space:pre-wrap;
  overflow-wrap:anywhere;text-align:left}}
code{{font:inherit}}
.link{{margin-top:44px;font-size:30px;line-height:1.4;color:#48505F}}
.link b{{color:#007BC2;font-weight:700}}
"""
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
    try:
        page.set_content(
            '<!doctype html><meta charset="utf-8"><style>' + css + "</style>"
            f'<main><img src="{logo}" alt="Shiny"><h1>{html.escape(card["title"])}</h1>'
            f"{command}{link}</main>"
        )
        page.evaluate("document.fonts.ready")
        page.evaluate("Promise.all([...document.images].map(i => i.decode()))")
        fits = page.evaluate("""() => {
 const box = document.querySelector('main').getBoundingClientRect();
 return [...document.querySelectorAll('main > *')].every(node => {
   const r = node.getBoundingClientRect();
   return r.top >= box.top - 1 && r.bottom <= box.bottom + 1 && node.scrollWidth <= node.clientWidth + 1;
 }) && (!document.querySelector('pre') || document.querySelector('pre').getBoundingClientRect().height <= innerHeight * .2);
}""")
        if not fits:
            raise ValueError(f"Shorten the outro title or command: it does not fit the {orientation} end card")
        page.screenshot(path=str(output))
    finally:
        page.close()
    return output


def last_frame(video: Path, output: Path) -> Path:
    """The frame the card dissolves from."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.5", "-i", str(video),
         "-update", "1", str(output)],
        check=True,
    )
    return output


def clip(still: Path, seconds: float, output: Path, size: tuple[int, int], fps: str = "30",
         previous: Path | None = None) -> Path:
    """Hold the still with a silent stereo track, so it joins narrated pieces.

    With `previous`, the card dissolves in from that frame inside its own
    length, so the video before it keeps every frame and its timing.
    """
    width, height = size
    scaled = f"scale={width}:{height},setsar=1"
    if previous is None:
        inputs = ["-loop", "1", "-framerate", fps, "-i", str(still)]
        graph = f"[0:v]{scaled},format=yuv420p[v]"
    else:
        inputs = ["-loop", "1", "-framerate", fps, "-i", str(previous),
                  "-loop", "1", "-framerate", fps, "-i", str(still)]
        graph = (
            f"[0:v]{scaled}[from];"
            f"[1:v]{scaled},format=rgba,fade=t=in:st=0:d={DISSOLVE_SECONDS}:alpha=1[card];"
            "[from][card]overlay=shortest=1,format=yuv420p[v]"
        )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", *inputs,
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-filter_complex", graph, "-map", "[v]", "-map", f"{len(inputs) // 5}:a",
            "-t", f"{seconds:.3f}", "-r", fps,
            "-c:v", "libx264", "-crf", "16", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", str(output),
        ],
        check=True,
    )
    return output


def append(video: Path, card: dict) -> float:
    """Add the card to the end of a finished narrated video, in place.

    The card matches the video's own size and frame rate. Returns its length.
    """
    from playwright.sync_api import sync_playwright

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate",
         "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout)["streams"]
    picture = next(stream for stream in streams if stream["codec_type"] == "video")
    if not any(stream["codec_type"] == "audio" for stream in streams):
        raise ValueError(f"{video} has no audio; the end card goes on the narrated video")
    width, height = int(picture["width"]), int(picture["height"])
    orientation = "horizontal" if width > height else "vertical"
    with tempfile.TemporaryDirectory(prefix="end-card-") as temporary, sync_playwright() as playwright:
        work = Path(temporary)
        browser = playwright.chromium.launch()
        try:
            still = render(browser, card, orientation, work / "end-card.png",
                           scale=width / SIZES[orientation][0])
        finally:
            browser.close()
        tail = clip(still, card["seconds"], work / "end-card.mp4", (width, height),
                    picture["r_frame_rate"], last_frame(video, work / "before-end-card.png"))
        joined = work / "joined.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(tail),
                "-filter_complex",
                "[0:v]format=yuv420p,setsar=1[v0];"
                "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
                "[v0][a0][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]", "-r", picture["r_frame_rate"],
                "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(joined),
            ],
            check=True,
        )
        shutil.copyfile(joined, video)
    return card["seconds"]

