#!/usr/bin/env python3
"""Draft one py-shinywidgets gallery episode production.

This scaffolder is specific to the py-shinywidgets gallery. It reads a local clone's
`website/gallery/<gallery>/app.py`, `requirements.txt`, and `index.md` front matter when
they exist. A link to a component page, pull request, or commit is accepted as provenance,
but those pages do not carry gallery front matter, so the draft keeps TODO metadata instead
of inventing an example, an accessor, or a hook. Nothing is fetched from the network.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

HERE = Path(__file__).resolve().parent
STARTER = HERE
ACCESSOR_NAMES = (
    "predicate", "selected_rows", "selected", "clicked", "click_callback",
    "bounds", "view_config", "camera", "hovered", "selection", "value",
)


def front_matter(path: Path) -> dict[str, Any]:
    """Parse the YAML block between the first two `---` lines, if there is one."""
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1:end]))
            except yaml.YAMLError:
                return {}
            return data if isinstance(data, dict) else {}
    return {}


def classify_url(url: str) -> tuple[str | None, str]:
    """Return the gallery path (when the link names one) and the link's kind."""
    path = urlparse(url).path
    gallery = re.search(r"/gallery/((?:templates|showcases)/[a-z0-9-]+)/?", path)
    if gallery:
        return gallery.group(1), "gallery"
    if re.search(r"/(?:pull/\d+|commit/[0-9a-f]+)", path):
        return None, "changeset"
    if "/widgets/" in path:
        return None, "component"
    return None, "link"


def find_repo(explicit: str | None) -> Path | None:
    """Locate a py-shinywidgets clone with the gallery tree."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if "PY_SHINYWIDGETS_DIR" in os.environ:
        candidates.append(Path(os.environ["PY_SHINYWIDGETS_DIR"]).expanduser())
    cwd = Path.cwd()
    for base in (cwd, cwd.parent, HERE.parents[4]):
        candidates += [base / "py-shinywidgets", base.parent / "py-shinywidgets"]
    for candidate in candidates:
        if (candidate / "website" / "gallery").is_dir():
            return candidate.resolve()
    return None


def detect_renderers(app: str) -> list[str]:
    seen: list[str] = []
    for pattern in (r"@render_([a-zA-Z_]\w*)", r"@render\.([a-zA-Z_]\w*)"):
        for name in re.findall(pattern, app):
            if name not in seen:
                seen.append(name)
    return seen


def detect_accessor(app: str) -> tuple[str, int, list[str]]:
    """Find `render_fn.method(...)` reads, preferring the known reactive accessors."""
    functions = re.findall(r"@render_\w+[^\n]*\n\s*def\s+(\w+)\s*\(", app)
    found: list[tuple[str, int, str]] = []
    for number, line in enumerate(app.splitlines(), start=1):
        for function in functions:
            match = re.search(rf"\b{re.escape(function)}\.([a-zA-Z_]\w*)\s*\(", line)
            if match:
                found.append((f"{function}.{match.group(1)}()", number, match.group(1)))
                break
    if not found:
        return "", 0, []
    ranked = sorted(found, key=lambda item: (ACCESSOR_NAMES.index(item[2]) if item[2] in ACCESSOR_NAMES else 99, item[1]))
    best = ranked[0]
    candidates = list(dict.fromkeys(item[0] for item in found))
    return best[0], best[1], candidates


def git_commit(repo: Path | None) -> str:
    if repo is None:
        return "TODO: gallery commit"
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "TODO: gallery commit"


def install_command(requirements: str, widgets: list[str]) -> str:
    extra = ""
    for widget in widgets:
        match = re.match(r"([a-zA-Z][\w-]*)", widget.strip())
        if match:
            extra = match.group(1).replace("-", "_").lower()
            break
    parts = []
    if extra:
        parts.append(f"'shinywidgets[{extra}]'")
    else:
        parts.append("shinywidgets")
    for line in requirements.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "shinywidgets")):
            parts.append(line)
    return "pip install " + " ".join(parts)


def title_from(args: argparse.Namespace, front: dict[str, Any]) -> str:
    title = args.title or str(front.get("title") or "")
    if not title:
        return "TODO: cover title, at most 32 characters"
    if len(title) > 32:
        shortened = title[:32].rsplit(" ", 1)[0]
        print(f"warning: cover title shortened to {shortened!r}", file=sys.stderr)
        return shortened
    return title


def draft(args: argparse.Namespace) -> dict[str, Any]:
    gallery, kind = classify_url(args.url or "")
    if args.gallery:
        gallery = args.gallery.strip("/")
    repo = find_repo(args.repo)
    source = repo / "website" / "gallery" / gallery if repo and gallery else None
    app = (source / "app.py").read_text(encoding="utf-8") if source and (source / "app.py").is_file() else ""
    front = front_matter(source / "index.md") if source else {}
    requirements = (source / "requirements.txt").read_text(encoding="utf-8") if source and (source / "requirements.txt").is_file() else ""

    widgets = args.widgets.split(",") if args.widgets else front.get("widgets") or []
    widgets = [str(widget).strip() for widget in widgets if str(widget).strip()]
    accessor, accessor_line, candidates = detect_accessor(app)
    if args.accessor:
        accessor = args.accessor
    renderers = detect_renderers(app)
    lines = app.splitlines()
    if args.accessor and not accessor_line:
        needle = args.accessor.split("(", 1)[0].split(".")[-1]
        for number, line in enumerate(lines, start=1):
            if needle + "(" in line:
                accessor_line = number
                break
    identifier = args.id or (gallery.rsplit("/", 1)[-1] if gallery else "new-shinywidgets-episode")
    label_widget = widgets[0] if widgets else "TODO"
    summary = str(front.get("summary") or "TODO: one sentence on what the interaction changes.")
    pattern = str(front.get("pattern") or "TODO")
    notes = [
        f"Drafted by make_episode.py; source link: {args.url or 'none'}" if args.url else "Drafted by make_episode.py",
        f"Gallery: {gallery or 'TODO: no gallery example in the link'}",
        f"Gallery commit: {git_commit(repo)}",
        f"Front matter: {'index.md' if front else 'none; metadata needs review'}",
    ]
    if kind in ("changeset", "component", "link"):
        notes.append(f"Link kind is {kind}; it does not name a gallery example. Confirm the example and accessor by hand.")
    if not app:
        notes.append("No app.py was copied. Point --repo at the py-shinywidgets clone or copy it manually.")
    if candidates and not args.accessor:
        notes.append("Accessor candidates in app.py: " + ", ".join(candidates))
    if accessor_line:
        notes.append(f"Accessor line {accessor_line} of app.py was used for the code still; verify it.")

    entry: dict[str, Any] = {
        "id": identifier,
        "gallery": gallery or "TODO: templates/... or showcases/...",
        "example": args.example or front.get("title") or title_from(args, front),
        "integration": widgets or ["TODO: libraries in the integration"],
        "label": f"Shiny for Python · {label_widget}",
        "title": title_from(args, front),
        "renderers": [f"render_{name}" for name in renderers] or ["TODO"],
        "accessor": accessor or "TODO: object.method()",
        "install": args.install or install_command(requirements, widgets),
        "hook": f"TODO: the interaction and its visible result. Gallery pattern: {pattern}.",
        "demo": [
            "TODO: first real interaction and what it shows.",
            "TODO: a second interaction that changes the same output.",
        ],
        "payoff": f"TODO: what the integration makes possible. Gallery summary: {summary}",
        "audience": "TODO: who finds this useful",
        "complexity": "medium",
        "notes": " ".join(notes),
    }
    return {
        "entry": entry,
        "source": source,
        "app": app,
        "requirements": requirements,
        "front": front,
        "accessor_line": accessor_line,
        "repo": repo,
        "gallery": gallery,
    }


def write_still_config(project: Path, data: dict[str, Any]) -> None:
    config = yaml.safe_load((STARTER / "source-shots.yaml").read_text(encoding="utf-8"))
    entry = data["entry"]
    context = config["context"]
    context["label"] = entry["label"]
    context["title"] = entry["title"]
    context["summary"] = str(data["front"].get("summary") or "TODO: one sentence on the outcome.")
    line = data["accessor_line"] or 1
    excerpt = [max(1, line - 1), line + 1] if data["app"] else [1, 2]
    for view in config["shots"][0]["views"].values():
        panel = view["panels"][0]
        panel["lines"] = excerpt
        panel["highlight"] = min(max(line, excerpt[0]), excerpt[1])
        longest = max((len(text) for text in data["app"].splitlines()[excerpt[0] - 1:excerpt[1]]), default=0)
        # Long gallery lines wrap at spaces with a short hanging indent; short ones stay whole.
        view["code_wrap"] = "smart" if longest > 44 else False
    (project / "source-shots.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8"
    )


def scaffold(args: argparse.Namespace) -> Path:
    project = args.project_dir.resolve()
    if project.exists() and any(project.iterdir()) and not args.force:
        raise SystemExit(f"{project} is not empty; use --force to overwrite the drafted files")
    project.mkdir(parents=True, exist_ok=True)
    for name in ("capture.py", "assemble.py", "look.py", "capture.yaml", "reel.yaml"):
        shutil.copy2(STARTER / name, project / name)
    data = draft(args)
    entry = data["entry"]
    if data["source"]:
        for name in ("app.py", "requirements.txt"):
            source = data["source"] / name
            if source.is_file():
                shutil.copy2(source, project / name)
        for folder in ("data", "img"):
            source = data["source"] / folder
            if source.is_dir():
                shutil.copytree(source, project / folder, dirs_exist_ok=True)
    (project / "episode.yaml").write_text(
        yaml.safe_dump(entry, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8"
    )
    header = (STARTER / "episodes.yaml").read_text(encoding="utf-8").split("episodes:", 1)[0]
    (project / "episodes.yaml").write_text(
        header + "episodes:\n" + yaml.safe_dump([entry], sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    write_still_config(project, data)
    reel = yaml.safe_load((project / "reel.yaml").read_text(encoding="utf-8"))
    reel["title"] = entry["title"]
    reel["outro"]["title"] = entry["title"]
    (project / "reel.yaml").write_text(
        yaml.safe_dump(reel, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8"
    )
    (project / "tts-settings.json").write_text(
        '{\n  "provider": "local-voice-cloning",\n  "saved_voice": "karan",\n'
        '  "engine": "qwen",\n  "quality": "high",\n  "language": "English"\n}\n',
        encoding="utf-8",
    )
    (project / "PRODUCTION.md").write_text(
        "# " + entry["title"] + "\n\n"
        "Drafted from a py-shinywidgets gallery example. Verify before narration:\n\n"
        "- [ ] The gallery `app.py` runs in a fresh environment; record versions and commit in the index.\n"
        "- [ ] The renderer, the accessor, and every control in `capture.yaml` still exist.\n"
        "- [ ] Replace every TODO in `episode.yaml`, `source-shots.yaml`, and `capture.yaml`.\n"
        "- [ ] Confirm the code still shows the accessor with real source line numbers.\n"
        "- [ ] Check both orientations; set `browser_args` if the widget needs WebGPU.\n"
        "- [ ] Run `look.py assign`, then apply the look to this production.\n"
        "- [ ] Check the release status on PyPI before putting an install command on the end card.\n\n"
        "Provenance: " + " ".join(str(part) for part in data["entry"]["notes"]) + "\n",
        encoding="utf-8",
    )
    print(f"Drafted {project}")
    print("  " + " ".join(f"{key}={entry[key]!r}" for key in ("id", "gallery", "accessor", "title")))
    print("  Review PRODUCTION.md before narration.")
    return project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--gallery", help="website/gallery path, e.g. templates/plotly-lasso-explorer")
    parser.add_argument("--url", help="gallery, component, PR, or commit link used as provenance")
    parser.add_argument("--repo", help="local py-shinywidgets clone (or PY_SHINYWIDGETS_DIR)")
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--example")
    parser.add_argument("--widgets", help="comma-separated libraries, e.g. 'Plotly, ITables'")
    parser.add_argument("--accessor", help="accessor to highlight, e.g. plot.selected_rows(df)")
    parser.add_argument("--install", help="install command for the end card (verify release status)")
    parser.add_argument("--force", action="store_true", help="overwrite drafted files in an existing directory")
    args = parser.parse_args(argv)
    if not args.gallery and not args.url:
        parser.error("give --gallery, --url, or both")
    scaffold(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
