#!/usr/bin/env python3
"""Turn source-shots.yaml into faithful, separately framed editorial stills."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import textwrap
from pathlib import Path
from typing import Any

import bootstrap_skill
import yaml
from playwright.sync_api import sync_playwright

import code_style
import context_cards

SIZES = {"vertical": (720, 1280), "horizontal": (1280, 720)}
CONTINUATION_INDENT = 4  # extra characters before the wrapped part of a code line
HIGHLIGHT_PADDING = (6, 3)  # logical pixels between the glyphs and the outline
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


def panel_html(
    project: Path, panel: dict, sources: dict, *, code_wrap: bool = True, code_theme: str = "light"
) -> str:
    """Read exact source text or embed a clean capture without manufacturing content."""
    path = (project / panel["file"]).resolve()
    raw = path.read_bytes()
    sources[str(path)] = {"file": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    kind = panel.get("kind", "code")
    label = html.escape(str(panel.get("label", panel["file"])))
    head = "" if panel.get("label") == "" or (kind == "image" and "label" not in panel) else (
        f'<p class="filename">{label}</p>'
    )
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
    code_lines = [line.expandtabs(4) for line in lines[first - 1 : last]]
    if kind == "code" and not code_wrap:
        code_lines = textwrap.dedent("\n".join(code_lines)).split("\n")
    rows = []
    for number, text in enumerate(code_lines, start=first):
        marked = ' data-highlight="true"' if number == highlight else ""
        # A wrapped code line continues past its own indentation, so it still reads as one line.
        hang = len(text) - len(text.lstrip(" ")) + CONTINUATION_INDENT if kind == "code" and code_wrap else 0
        style = f' style="padding-left:{hang}ch;text-indent:-{hang}ch"' if hang else ""
        rows.append(
            f'<div class="line"{marked}><span class="number">{number}</span><span class="text"{style}>{html.escape(text)}</span></div>'
        )
    theme = f"github-{code_theme}" if kind == "code" else "github-light"
    whole_lines = " whole-lines" if kind == "code" and not code_wrap else ""
    return (
        head
        + f'<div class="code {theme}{whole_lines}" data-file="{html.escape(panel["file"], quote=True)}" data-language="{html.escape(language,quote=True)}">'
        + "".join(rows)
        + "</div>"
    )


def prepare(project: Path) -> dict:
    """Prepare the requested views, refusing source mistakes and unreadable overflow."""
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
    orientations = context_cards.orientations(config)
    result = {key: config[key] for key in ("target_seconds", "orientations") if key in config}
    result.update(
        generated_by="prepare_editorial.py",
        source_manifest="artifacts/editorial-sources/provenance.json",
        shots=[],
    )
    result["context"] = context_cards.resolve(project, config)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for index, shot in enumerate(config["shots"], start=1):
                if not isinstance(shot, dict) or not shot.get("cue"):
                    raise ValueError("Every shot needs its narration phrase cue")
                built = {key: shot[key] for key in ("cue", "source", "chapter") if key in shot}
                built["views"] = {}
                for orientation in orientations:
                    width, height = SIZES[orientation]
                    view = shot.get("views", {}).get(orientation, {})
                    panels = view.get("panels", shot.get("panels"))
                    if not isinstance(panels, list) or not panels:
                        raise ValueError(f"Shot {index} needs panels for {orientation}")
                    size = view.get("font_size", 26 if orientation == "vertical" else 32)
                    if type(size) not in (int, float) or not 20 <= size <= 40:
                        raise ValueError(
                            "font_size must be 20–40 logical pixels; use shorter excerpts instead of tiny code"
                        )
                    code_wrap = view.get("code_wrap", True)
                    code_theme = view.get("code_theme", "light")
                    if type(code_wrap) is not bool or code_theme not in ("light", "dark"):
                        raise ValueError("code_wrap must be a boolean and code_theme must be light or dark")
                    content = "".join(
                        "<section>"
                        + panel_html(project, panel, sources, code_wrap=code_wrap, code_theme=code_theme)
                        + "</section>"
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
.code.github-dark{{background:#1D1F21;color:#FFFFFF;border-radius:16px;padding:24px 20px}}
.github-dark .number{{color:#CDD4DA}}
.whole-lines .text{{white-space:pre;overflow-wrap:normal}}
"""
                    )
                    if orientation == "vertical" and result["context"]["layout"] == "showcase":
                        css += (
                            "section+section{margin-top:14px}"
                            "img{max-height:52vh;border-radius:16px}"
                            ".filename{font-weight:700;margin-bottom:12px}"
                        )
                    if view.get("layout") == "columns":
                        css += (
                            f"main{{display:grid;grid-template-columns:repeat({len(panels)},minmax(0,1fr));gap:40px;align-items:center}}"
                            "section+section{margin-top:0}"
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
                        overflow = page.evaluate("""() => {
 const row = [...document.querySelectorAll('.whole-lines .line')].find(
   row => { const text = row.querySelector('.text'); return text.scrollWidth > text.clientWidth; });
 return row ? row.closest('.code').dataset.file + ':' + row.querySelector('.number').textContent : null;
}""")
                        if overflow:
                            raise ValueError(
                                f"{overflow} does not fit in the {orientation} code card. "
                                "Shorten the excerpt or add a line break in the actual source."
                            )
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
                        if not code_wrap:
                            frame["motion"] = "none"
                        if marked.count():
                            # Outline the characters, including a wrapped part, not the empty row.
                            rect = marked.evaluate(
                                """(node, [padX, padY]) => {
 const range = document.createRange(); range.selectNodeContents(node);
 const r = range.getBoundingClientRect();
 const x = Math.max(0, r.left - padX), y = Math.max(0, r.top - padY);
 return {x, y, width: Math.min(innerWidth, r.right + padX) - x,
         height: Math.min(innerHeight, r.bottom + padY) - y};
}""",
                                list(HIGHLIGHT_PADDING),
                            )
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
                if index == 1:
                    for orientation in orientations:
                        view = shot.get("views", {}).get(orientation, {})
                        panels = view.get("panels", shot.get("panels"))
                        capture = result["context"]["captures"].get(orientation)
                        if capture is None:
                            capture = (panels[0]["file"] if len(panels) == 1
                                       and panels[0].get("kind") == "image"
                                       else built["views"][orientation]["file"])
                            result["context"]["captures"][orientation] = capture
                        capture_path = (project / capture).resolve()
                        sources[str(capture_path)] = {
                            "file": str(capture_path),
                            "sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
                        }
                        context_cards.render(browser, project, result["context"], orientation, capture_path)
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
    views = ", ".join(context_cards.orientations(result))
    print(f'Prepared {len(result["shots"])} source-derived shots for {views}')


if __name__ == "__main__":
    main()
