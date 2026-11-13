"""Result-first posters and brief opening titles for editorial videos."""
from __future__ import annotations

import base64
import hashlib
import html
import subprocess
from pathlib import Path

import yaml

import code_style

SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
INTRO_SECONDS = 3.0
MEDIA_RECTS = {
    "vertical": (0.05, 0.28, 0.90, 0.66),
    "horizontal": (0.43, 0.10, 0.52, 0.80),
}


def orientations(config: dict) -> list[str]:
    """Require both views by default and allow explicitly single-view productions."""
    views = config.get("orientations", list(SIZES))
    if (
        not isinstance(views, list)
        or not views
        or any(not isinstance(view, str) or view not in SIZES for view in views)
        or len(set(views)) != len(views)
    ):
        raise ValueError("orientations must list vertical, horizontal, or both once each")
    return views


def resolve(project: Path, config: dict) -> dict:
    """Keep old projects usable; new projects author a specific outcome sentence."""
    supplied = config.get("context", {})
    if not isinstance(supplied, dict):
        raise ValueError("context must contain a label, title, and summary")
    reel, feature = {}, {}
    for directory in (project, *project.parents):
        reel_file = directory / "reel.yaml"
        if not reel_file.exists():
            continue
        candidate = yaml.safe_load(reel_file.read_text()) or {}
        match = next(
            (f for f in candidate.get("features", [])
             if (directory / str(f.get("dir", "."))).resolve() == project.resolve()),
            {},
        )
        if match or directory == project:
            reel, feature = candidate, match
            break
    label = str(reel.get("release") or "Shiny for Python")
    app = project / "app.py"
    if not reel.get("release") and app.exists() and "shinywidgets" in app.read_text():
        label += " · shinywidgets"
    elif not app.exists() and (project / "app.R").exists() and not reel.get("release"):
        label = "Shiny for R"
    result = {
        "label": supplied.get("label", label),
        "title": supplied.get("title", feature.get("title") or reel.get("title")
                              or config["shots"][0].get("chapter") or "Shiny in action"),
        "summary": supplied.get("summary", feature.get("why") or ""),
        "captures": supplied.get("captures", {}),
        "layout": supplied.get("layout", "editorial"),
    }
    if result["layout"] not in ("editorial", "showcase"):
        raise ValueError("context.layout must be editorial or showcase")
    for name in ("label", "title", "summary"):
        if not isinstance(result[name], str) or (name != "summary" and not result[name].strip()):
            raise ValueError(f"context.{name} must be readable text")
    if not isinstance(result["captures"], dict) or any(
        key not in SIZES or not isinstance(value, str) or not value.strip()
        for key, value in result["captures"].items()
    ):
        raise ValueError("context.captures must map orientations to local media files")
    return result


def render(browser, project: Path, context: dict, orientation: str, capture: Path,
           *, media_in: float = 0.0) -> dict[str, Path]:
    """Recompose actual evidence without cropping it or covering app controls."""
    width, height = SIZES[orientation]
    destination = project / "artifacts/context"
    destination.mkdir(parents=True, exist_ok=True)
    if capture.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        raw = capture.read_bytes()
        mime = "image/" + {".jpg": "jpeg"}.get(capture.suffix.lower(), capture.suffix[1:])
    else:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(media_in), "-i", str(capture),
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, check=True,
        ).stdout
        mime = "image/png"
    uri = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    text = {key: html.escape(context[key]) for key in ("label", "title", "summary")}
    x, y, w, h = MEDIA_RECTS[orientation]
    css = code_style.font_css() + f"""*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px}}
body{{background:#F8F8F8;color:#1D1F21;font-family:'Open Sans',sans-serif}}
header{{position:absolute;left:5%;width:90%;top:5%}}
.label{{margin:0;color:#007BC2;font-size:22px;font-weight:600;line-height:1.4}}
h1{{margin:18px 0 0;font-size:58px;line-height:1.12;font-weight:700;letter-spacing:-.035em}}
.summary{{margin:22px 0 0;font-size:28px;line-height:1.5;color:#48505F}}
.evidence{{position:absolute;left:5%;top:32%;width:90%;height:63%;display:flex;align-items:flex-start;justify-content:center}}
img{{display:block;max-width:100%;max-height:100%;object-fit:contain;border:1px solid #CDD4DA;border-radius:10px;box-shadow:0 12px 36px #1D1F2110}}
.intro .summary{{display:none}}.intro h1{{font-size:48px}}
.intro .evidence{{left:{x*100}%;top:{y*100}%;width:{w*100}%;height:{h*100}%;align-items:center}}
.overlay{{background:transparent}}.overlay .evidence{{visibility:hidden}}
"""
    if orientation == "horizontal":
        css += """
header{left:5%;top:50%;transform:translateY(-50%);width:33%}
h1{font-size:54px}.summary{font-size:26px}
.evidence{left:43%;top:10%;width:52%;height:80%;align-items:center}
.intro h1{font-size:46px}
"""
    showcase = context.get("layout") == "showcase"
    if showcase:
        css += """
body{background:#1D1F21;color:#FFFFFF}
.label{color:#CDD4DA}.summary{color:#CDD4DA}
header{top:6%;transform:none}
h1{font-size:72px;font-weight:800;line-height:1.02;letter-spacing:-.055em;text-wrap:balance}
.summary{margin-top:16px;font-size:25px;line-height:1.35}
.evidence{top:29%;height:65%;align-items:center}
img{border:0;border-radius:12px;box-shadow:none}
"""
        if orientation == "horizontal":
            css += """
header{top:50%;transform:translateY(-50%)}
h1{font-size:62px}
.evidence{top:7%;height:86%}
"""
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
    files = {}
    try:
        page.set_content(
            '<!doctype html><meta charset="utf-8"><style>' + css + '</style>'
            f'<header><p class="label">{text["label"]}</p><h1>{text["title"]}</h1>'
            f'<p class="summary">{text["summary"]}</p></header>'
            f'<div class="evidence"><img src="{uri}"></div>'
        )
        page.evaluate("document.fonts.ready")
        page.evaluate("Promise.all([...document.images].map(i => i.decode()))")
        for mode in (("poster",) if showcase else ("poster", "opening", "overlay")):
            page.evaluate("mode => document.body.className = mode === 'poster' ? '' : 'intro ' + mode", mode)
            fits = page.evaluate("""() => {
 const header=document.querySelector('header').getBoundingClientRect();
 const evidence=document.querySelector('.evidence').getBoundingClientRect();
 return header.y>=innerHeight*.04 && header.bottom<=innerHeight*.96 &&
   header.right<=innerWidth*.96 && document.documentElement.scrollWidth<=innerWidth &&
   (header.bottom<=evidence.y || header.right<=evidence.x);
}""")
            if not fits:
                raise ValueError(f"Shorten the context title or summary: {orientation} {mode} overlaps the evidence")
            suffix = ".jpg" if mode == "poster" else ".png"
            path = destination / f"{mode}-{orientation}{suffix}"
            page.screenshot(path=str(path), omit_background=mode == "overlay",
                            **({"quality": 94} if mode == "poster" else {}))
            if mode != "overlay":
                path.with_suffix(".html").write_text(page.content())
            files[mode] = path
    finally:
        page.close()
    return files


def digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
