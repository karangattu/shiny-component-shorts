#!/usr/bin/env python3
"""List the new features in one release of a Shiny changelog.

Reads a Keep a Changelog file (`## [1.8.0] - 2026-09-12` / `### New features`,
as in py-shiny and shinychat) or an R `NEWS.md` (`# shiny 1.14.0` /
`## New features`). Picks the unreleased section by default, or the version
given with `--version`, and writes one entry per feature bullet to JSON.

The source can be a local path, a raw URL, a GitHub blob URL, or
`owner/repo[:path]` (fetched with `gh`, so private repos work too).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

UNRELEASED = re.compile(r"unreleased|development version|\(dev\)", re.IGNORECASE)
VERSION = re.compile(r"\d+\.\d+(?:\.\d+)*(?:[-.]?(?:a|b|rc|dev)\d*)?")
HEADING = re.compile(r"^(#{1,4})\s+(.*?)\s*#*\s*$")
BULLET = re.compile(r"^[*-]\s+(.*)$")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
FEATURE_SECTIONS = re.compile(r"new features?|api additions?", re.IGNORECASE)
IMPROVEMENT_SECTIONS = re.compile(r"improvements?|enhancements?", re.IGNORECASE)
PR_REF = re.compile(r"(?:\b([\w.-]+/[\w.-]+))?#(\d+)\b")
FIX_ITEM = re.compile(r"^(fixed|fix|fixes)\b", re.IGNORECASE)
UNSORTED = "Unsorted"
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
DEFAULT_PATHS = ("CHANGELOG.md", "NEWS.md", "pkg-py/CHANGELOG.md", "pkg-r/NEWS.md")


def _gh_raw(repo: str, path: str, ref: str | None) -> str:
    endpoint = f"repos/{repo}/contents/{path}" + (f"?ref={ref}" if ref else "")
    result = subprocess.run(
        ["gh", "api", endpoint, "-H", "Accept: application/vnd.github.raw"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FileNotFoundError(f"{repo}:{path} ({result.stderr.strip()})")
    return result.stdout


def read_source(source: str) -> tuple[str, str | None]:
    """Return the changelog text and the GitHub repo it came from, if known."""
    path = Path(source).expanduser()
    if path.is_file():
        return path.read_text(encoding="utf-8"), None
    blob = re.match(r"https://github\.com/([^/]+/[^/]+)/(?:blob|raw)/([^/]+)/(.+)", source)
    if blob:
        repo, ref, file_path = blob.groups()
        return _gh_raw(repo, file_path, ref), repo
    raw = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/", source)
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return response.read().decode("utf-8"), raw.group(1) if raw else None
    short = re.fullmatch(r"([\w.-]+/[\w.-]+)(?::(.+))?", source)
    if short:
        repo, file_path = short.groups()
        for candidate in [file_path] if file_path else DEFAULT_PATHS:
            try:
                return _gh_raw(repo, candidate, None), repo
            except FileNotFoundError:
                continue
        raise SystemExit(f"No changelog found in {repo}; pass owner/repo:path")
    raise SystemExit(f"Changelog source not found: {source}")


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", LINK.sub(r"\1", text)).strip()


def parse_releases(text: str) -> list[dict]:
    """Split a changelog into releases, each with named sections of bullets."""
    lines = text.splitlines()
    headings = [
        (index, len(match.group(1)), match.group(2))
        for index, line in enumerate(lines)
        if (match := HEADING.match(line))
    ]
    release_level = next(
        (
            level
            for _, level, title in headings
            if UNRELEASED.search(title) or VERSION.search(title)
        ),
        None,
    )
    if release_level is None:
        return []
    releases: list[dict] = []
    release: dict[str, Any] | None = None
    section: dict[str, Any] | None = None
    bullet: list[str] | None = None

    def close_bullet() -> None:
        nonlocal bullet
        if bullet and section is not None:
            section["items"].append(_plain(" ".join(bullet)))
        bullet = None

    for line in lines:
        match = HEADING.match(line)
        if match and len(match.group(1)) <= release_level + 1:
            close_bullet()
            level, title = len(match.group(1)), match.group(2)
            if level == release_level and (UNRELEASED.search(title) or VERSION.search(title)):
                number = VERSION.search(title)
                version = None if UNRELEASED.search(title) or not number else number.group(0)
                date = DATE.search(title)
                release = {
                    "heading": title,
                    "version": version,
                    "date": date.group(0) if date else None,
                    "sections": [],
                }
                releases.append(release)
                section = None
            elif level == release_level + 1 and release is not None:
                section = {"title": title.strip(), "items": []}
                release["sections"].append(section)
            elif level <= release_level:
                release = section = None
            continue
        if release is None:
            continue
        stripped = line.strip()
        item = BULLET.match(line)
        if item:
            close_bullet()
            if section is None:  # bullets directly under the release heading
                section = {"title": UNSORTED, "items": []}
                release["sections"].append(section)
            bullet = [item.group(1)]
        elif bullet is not None and stripped and line[:1].isspace():
            bullet.append(stripped)
        elif not stripped:
            continue
        else:
            close_bullet()
    close_bullet()
    return releases


def pick_release(releases: list[dict], version: str | None) -> dict:
    if not releases:
        raise SystemExit("No release headings found in the changelog")
    if version in (None, "", "unreleased"):
        for release in releases:
            if release["version"] is None:
                return release
        available = ", ".join(r["version"] for r in releases[:5] if r["version"])
        raise SystemExit(
            f"The changelog has no unreleased section; pass --version (latest: {available})"
        )
    wanted = version.lstrip("v")
    for release in releases:
        if release["version"] == wanted:
            return release
    available = ", ".join(r["version"] or "unreleased" for r in releases[:8])
    raise SystemExit(f"Version {version} not found; recent: {available}")


def feature_entries(
    release: dict, include_improvements: bool, sections: list[str] | None, repo: str | None
) -> list[dict]:
    def wanted(title: str) -> bool:
        if title == UNSORTED:  # no subsections: the agent sorts features from the rest
            return True
        if sections:
            return any(name.lower() in title.lower() for name in sections)
        return bool(
            FEATURE_SECTIONS.search(title)
            or (include_improvements and IMPROVEMENT_SECTIONS.search(title))
        )

    entries = []
    for section in release["sections"]:
        if not wanted(section["title"]):
            continue
        for text in section["items"]:
            if section["title"] == UNSORTED and FIX_ITEM.match(text):
                continue
            refs = []
            for other_repo, number in PR_REF.findall(text):
                if other_repo:
                    refs.append(f"https://github.com/{other_repo}/pull/{number}")
                elif repo:
                    refs.append(f"https://github.com/{repo}/pull/{number}")
            code = re.findall(r"`([^`]+)`", text)
            entries.append(
                {
                    "index": len(entries) + 1,
                    "section": section["title"],
                    "text": text,
                    "symbols": list(dict.fromkeys(code))[:6],
                    "references": list(dict.fromkeys(refs)),
                }
            )
    return entries


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="Changelog path, URL, GitHub blob URL, or owner/repo[:path]",
    )
    parser.add_argument(
        "--version",
        help="Release to read, e.g. 1.8.0; default is the unreleased section",
    )
    parser.add_argument(
        "--include-improvements",
        action="store_true",
        help="Also list items from Improvements sections",
    )
    parser.add_argument(
        "--section",
        action="append",
        help="Read only sections whose title contains this text (repeatable)",
    )
    parser.add_argument("--output", type=Path, help="Write the feature list as JSON here")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text, repo = read_source(args.source)
    release = pick_release(parse_releases(text), args.version)
    features = feature_entries(release, args.include_improvements, args.section, repo)
    report = {
        "source": args.source,
        "repo": repo,
        "release": release["heading"],
        "version": release["version"] or "unreleased",
        "date": release["date"],
        "sections": [section["title"] for section in release["sections"]],
        "features": features,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['release']}: {len(features)} feature(s); sections: {', '.join(report['sections'])}")
    for feature in features:
        print(f"  {feature['index']}. [{feature['section']}] {feature['text'][:140]}")
    if any(feature["section"] == UNSORTED for feature in features):
        print(
            "This release has no section headings: the list skips items that start with "
            "'Fixed' but may still hold fixes and internal changes. Keep only new, "
            "user-facing features.",
            file=sys.stderr,
        )
    if not features:
        print(
            "No feature items in this release. Try --include-improvements, "
            "--section, or another --version.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
