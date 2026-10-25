#!/usr/bin/env python3
"""Turn source-shots.yaml into faithful, separately framed editorial stills."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
from typing import Any

import bootstrap_skill
import yaml
from playwright.sync_api import sync_playwright

import code_style

SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
LANGUAGES = {
    ".py": "python",
    ".r": "r",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sh": "bash",
}


def panel_html(project: Path, panel: dict, sources: dict) -> str:
    """Read exact source text or embed a clean capture without manufacturing content."""
    path = (project / panel["file"]).resolve()
    raw = path.read_bytes()
    sources[str(path)] = {"file": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    kind = panel.get("kind", "code")
    label = html.escape(str(panel.get("label", panel["file"])))
    head = "" if kind == "image" and "label" not in panel else f'<p class="filename">{label}</p>'
    if kind == "image":
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower())
        if mime is None:
            raise ValueError("Image panels need PNG, JPEG, or WebP captures")
        return head + f'<img src="data:{mime};base64,{base64.b64encode(raw).decode()}">'
    if kind not in ("code", "text", "output"):
        raise ValueError(f"Unknown panel kind: {kind}")
    lines = raw.decode("utf-8").splitlines()
    selected = panel.get("lines", [1, len(lines)])
    if (
        not isinstance(selected, list)
        or len(selected) != 2
        or any(type(v) is not int for v in selected)
        or not 1 <= selected[0] <= selected[1] <= len(lines)
    ):
        raise ValueError(f"{path}: lines must be an inclusive source range")
    first, last = selected
    highlight = panel.get("highlight")
    if highlight is not None and (
        kind != "code" or type(highlight) is not int or not first <= highlight <= last
    ):
        raise ValueError("highlight must name one visible code line")
    if kind == "text":
        return (
            head
            + '<div class="prose">'
            + html.escape("\n".join(lines[first - 1 : last]))
            + "</div>"
        )
    language = (
        str(panel.get("language", LANGUAGES.get(path.suffix.lower(), "plaintext")))
        if kind == "code"
        else "plaintext"
    )
    rows = []
    for number in range(first, last + 1):
        marked = ' data-highlight="true"' if number == highlight else ""
        rows.append(
            f'<div class="line"{marked}><span class="number">{number}</span><span class="text">{html.escape(lines[number-1])}</span></div>'
        )
    return (
        head
        + f'<div class="code github-light" data-language="{html.escape(language,quote=True)}">'
        + "".join(rows)
        + "</div>"
    )


def prepare(project: Path) -> dict:
    """Prepare both views, refusing source mistakes and unreadable overflow."""
    project = project.resolve()
    config = yaml.safe_load((project / "source-shots.yaml").read_text())
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("shots"), list)
        or not config["shots"]
    ):
        raise ValueError("source-shots.yaml needs a non-empty shots list")
    output = project / "editorial.yaml"
    if (
        output.exists()
        and (yaml.safe_load(output.read_text()) or {}).get("generated_by") != "prepare_editorial.py"
    ):
        raise ValueError(
            "Keep hand-authored editorial.yaml separate; this command only replaces its own generated output"
        )
    destination = project / "artifacts/editorial-sources"
    destination.mkdir(parents=True, exist_ok=True)
    sources: dict[str, Any] = {}
    result = {key: config[key] for key in ("target_seconds",) if key in config}
    result.update(
        generated_by="prepare_editorial.py",
        source_manifest="artifacts/editorial-sources/provenance.json",
        shots=[],
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for index, shot in enumerate(config["shots"], start=1):
                if not isinstance(shot, dict) or not shot.get("cue"):
                    raise ValueError("Every shot needs its narration phrase cue")
                built = {key: shot[key] for key in ("cue", "source", "chapter") if key in shot}
                built["views"] = {}
                for orientation, (width, height) in SIZES.items():
                    view = shot.get("views", {}).get(orientation, {})
                    panels = view.get("panels", shot.get("panels"))
                    if not isinstance(panels, list) or not panels:
                        raise ValueError(f"Shot {index} needs panels for {orientation}")
                    size = view.get("font_size", 26 if orientation == "vertical" else 32)
                    if type(size) not in (int, float) or not 20 <= size <= 40:
                        raise ValueError(
                            "font_size must be 20–40 logical pixels; use shorter excerpts instead of tiny code"
                        )
                    content = "".join(
                        "<section>" + panel_html(project, panel, sources) + "</section>"
                        for panel in panels
                    )
                    css = (
                        code_style.font_css()
                        + code_style.stylesheet()
                        + f"""
*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;background:#F8F8F8;color:#1D1F21}}
body{{font-family:'Open Sans',sans-serif;padding:12vh 5vw 7vh;display:flex;align-items:center}}
main{{width:100%}}section+section{{margin-top:28px}}.filename{{font-size:20px;color:#48505F;margin:0 0 16px;overflow-wrap:anywhere}}
.code,.prose{{font-size:{size}px;line-height:1.55}}.code{{font-family:'Source Code Pro',monospace}}
.line{{display:grid;grid-template-columns:24px minmax(0,1fr);gap:12px}}.number{{font-size:14px;color:#707782;text-align:right;padding-top:8px}}
.text,.prose{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{display:block;max-width:100%;max-height:{height*.65}px;margin:auto;object-fit:contain}}
"""
                    )
                    page = browser.new_page(
                        viewport={"width": width, "height": height}, device_scale_factor=2
                    )
                    try:
                        page.set_content(
                            '<!doctype html><meta charset="utf-8"><style>'
                            + css
                            + "</style><main>"
                            + content
                            + "</main>"
                        )
                        if not page.locator("img").evaluate_all(
                            "nodes => nodes.every(img => img.complete && img.naturalWidth > 0)"
                        ):
                            raise ValueError(
                                f"Shot {index} {orientation} contains an unreadable source image"
                            )
                        page.evaluate(code_style.browser_script())
                        page.evaluate(
                            """() => {for(const block of document.querySelectorAll('.code')){
 const rows=[...block.querySelectorAll('.text')];
 const painted=shinyHighlightLines(rows.map(el=>el.textContent).join('\\n'),block.dataset.language);
 rows.forEach((row,index)=>row.innerHTML=painted[index]);
}}"""
                        )
                        page.evaluate("document.fonts.ready")
                        box = page.locator("main").bounding_box()
                        if (
                            not box
                            or box["y"] < height * 0.12 - 1
                            or box["y"] + box["height"] > height * 0.93 + 1
                            or page.evaluate("document.documentElement.scrollWidth>innerWidth")
                        ):
                            raise ValueError(
                                f"Shot {index} {orientation} does not fit: shorten excerpts or reframe panels; never shrink text to hide overflow"
                            )
                        marked = page.locator("[data-highlight] .text")
                        if marked.count() > 1:
                            raise ValueError("Use one highlight at a time")
                        frame: dict[str, Any] = {
                            "file": str(
                                (destination / f"shot-{index:03d}-{orientation}.png").relative_to(
                                    project
                                )
                            ),
                            "fit": "contain",
                        }
                        if marked.count():
                            rect = marked.bounding_box()
                            assert rect
                            frame["highlight"] = [
                                rect["x"] / width,
                                rect["y"] / height,
                                rect["width"] / width,
                                rect["height"] / height,
                            ]
                        path = project / frame["file"]
                        page.screenshot(path=str(path))
                        path.with_suffix(".html").write_text(page.content())
                        built["views"][orientation] = frame
                    finally:
                        page.close()
                result["shots"].append(built)
        finally:
            browser.close()
    config_file = project / "source-shots.yaml"
    sources[str(config_file)] = {
        "file": str(config_file),
        "sha256": hashlib.sha256(config_file.read_bytes()).hexdigest(),
    }
    (destination / "provenance.json").write_text(
        json.dumps({"sources": list(sources.values()), "shots": result["shots"]}, indent=2) + "\n"
    )
    output.write_text(yaml.safe_dump(result, sort_keys=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    args = parser.parse_args()
    if __name__ == "__main__":
        bootstrap_skill.guard(args.project_dir, Path(__file__))
    result = prepare(args.project_dir)
    print(f'Prepared {len(result["shots"])} source-derived shots in both orientations')


if __name__ == "__main__":
    main()
