#!/usr/bin/env python3
"""Install a verified release per production; reuse that exact snapshot thereafter."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = "karangattu/shiny-component-shorts"
API = f"https://api.github.com/repos/{REPOSITORY}"
DOWNLOAD = f"https://github.com/{REPOSITORY}/releases/download/"
LOCK = "skill-lock.json"
SNAPSHOT = ".video-skill"
MANIFEST = "skill-manifest.json"
IGNORED = {"__pycache__", ".git", ".DS_Store", ".pytest_cache"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "shiny-component-shorts",
            "Accept": (
                "application/octet-stream"
                if not url.startswith(API)
                else "application/vnd.github+json"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Skill download exceeds 64 MiB")
    return data


def files(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            set(relative.parts) & IGNORED
            or path.suffix == ".pyc"
            or relative.as_posix() == MANIFEST
        ):
            continue
        if path.is_symlink():
            raise ValueError(f"Skill snapshot cannot contain symlinks: {relative}")
        if path.is_file():
            result[relative.as_posix()] = digest(path.read_bytes())
    return result


def verify(root: Path, expected: str | None = None) -> str:
    manifest = root / MANIFEST
    if manifest.is_symlink() or root.is_symlink():
        raise ValueError("Skill snapshot must be a regular directory")
    raw = manifest.read_bytes()
    if expected and digest(raw) != expected:
        raise ValueError(
            "Pinned skill manifest changed; preserve it and restore the original snapshot"
        )
    if json.loads(raw) != files(root):
        raise ValueError(
            "Skill files changed or are missing; preserve edits and restore the original snapshot"
        )
    return digest(raw)


def variant_for(source: Path) -> str:
    metadata = source / "release.json"
    variant = (
        json.loads(metadata.read_text())["variant"]
        if metadata.is_file()
        else ("claude" if ".claude" in source.parts else "codex")
    )
    if variant not in {"codex", "claude"}:
        raise ValueError("Unknown skill variant")
    return variant


def release_into(destination: Path, variant: str) -> dict:
    release = json.loads(fetch(f"{API}/releases/latest"))
    tag = release["tag_name"]
    if (
        release.get("draft")
        or release.get("prerelease")
        or not re.fullmatch(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", tag)
    ):
        raise ValueError("Expected a stable semantic-version release")
    name = f"shiny-component-shorts-{tag}-{variant}.zip"
    assets = {
        asset["name"]: asset["browser_download_url"] for asset in release["assets"]
    }
    for item in [name, "SHA256SUMS"]:
        if assets.get(item) != DOWNLOAD + tag + "/" + item:
            raise ValueError(f"Missing or untrusted release asset: {item}")
    sums = fetch(assets["SHA256SUMS"]).decode().splitlines()
    hashes = [
        line.split()[0]
        for line in sums
        if len(line.split()) == 2 and line.split()[1] == name
    ]
    data = fetch(assets[name])
    if len(hashes) != 1 or hashes[0] != digest(data):
        raise ValueError("Release checksum verification failed")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if sum(item.file_size for item in entries) > 128 * 1024 * 1024:
            raise ValueError("Unpacked skill exceeds 128 MiB")
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or not path.parts
                or path.parts[0] != "shiny-component-shorts"
            ):
                raise ValueError("Unsafe path in skill archive")
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or item.filename in seen:
                raise ValueError("Symlink or duplicate entry in skill archive")
            seen.add(item.filename)
            target = destination.joinpath(*path.parts[1:])
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
    verify(destination)
    meta = json.loads((destination / "release.json").read_text())
    if (
        meta.get("tag") != tag
        or meta.get("version") != tag[1:]
        or meta.get("variant") != variant
        or not re.fullmatch(r"[0-9a-f]{40}", meta.get("commit", ""))
        or (destination / "VERSION").read_text().strip() != tag[1:]
    ):
        raise ValueError("Release provenance does not match requested package")
    if not (destination / "SKILL.md").is_file():
        raise ValueError("Release has no skill instructions")
    return {
        **meta,
        "channel": "release",
        "archive_sha256": digest(data),
        "repository": REPOSITORY,
    }


def existing_production(project: Path) -> bool:
    # A narration draft is still a new production; recorded/derived media is not.
    artifacts = project / "artifacts"
    return artifacts.exists() and any(
        path.suffix.lower() in {".wav", ".mp3", ".mp4", ".mov", ".webm"}
        for path in artifacts.rglob("*")
        if path.is_file()
    )


def ensure_pin(
    project: Path, source: Path, *, variant: str | None = None, local: bool = False
) -> Path:
    project, source = project.resolve(), source.resolve()
    if project == source or source in project.parents:
        raise ValueError("Production directories must be outside the installed skill")
    variant = variant or variant_for(source)
    if variant not in {"codex", "claude"}:
        raise ValueError("Unknown skill variant")
    for parent in [project, *project.parents]:
        lock_path = parent / LOCK
        if lock_path.is_file():
            lock = json.loads(lock_path.read_text())
            if (
                lock.get("schema") != 1
                or lock.get("variant") != variant
                or lock.get("snapshot") != SNAPSHOT
            ):
                raise ValueError(
                    "Production lock schema, variant, or snapshot is incompatible"
                )
            pinned = parent / SNAPSHOT
            verify(pinned, lock["manifest_sha256"])
            return pinned
    project.mkdir(parents=True, exist_ok=True)
    busy = project / ".skill-bootstrap.lock"
    try:
        descriptor = os.open(busy, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            "Another bootstrap is active; retry after it finishes (inspect a stale .skill-bootstrap.lock before removing it)"
        ) from exc
    os.close(descriptor)
    try:
        pinned = project / SNAPSHOT
        if pinned.exists() or pinned.is_symlink():
            raise ValueError(
                "Unmanaged .video-skill exists; preserve it and choose a fresh production directory"
            )
        legacy = existing_production(project)
        with tempfile.TemporaryDirectory(
            prefix=".skill-download-", dir=project
        ) as temp:
            staged = Path(temp) / "skill"
            if local or legacy:
                shutil.copytree(
                    source,
                    staged,
                    ignore=shutil.ignore_patterns(*IGNORED, "*.pyc", MANIFEST),
                )
                manifest = json.dumps(files(staged), sort_keys=True, indent=2) + "\n"
                (staged / MANIFEST).write_text(manifest)
                metadata = {
                    "channel": "local" if local else "legacy-local",
                    "variant": variant,
                    "source": str(source),
                }
                print(
                    "Preserving installed tools for an existing production."
                    if legacy and not local
                    else "Pinning explicitly selected local tools."
                )
            else:
                staged.mkdir()
                metadata = release_into(staged, variant)
            lock = {
                "schema": 1,
                "snapshot": SNAPSHOT,
                "variant": variant,
                **metadata,
                "manifest_sha256": verify(staged),
            }
            staged_lock = Path(temp) / LOCK
            staged_lock.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
            staged.rename(pinned)
            staged_lock.rename(project / LOCK)
        return pinned
    finally:
        busy.unlink()


def guard(project: Path, script: Path, argv: list[str] | None = None) -> None:
    """CLI boundary: execute the pinned script using the selected interpreter."""
    source = script.resolve().parent.parent
    pinned = ensure_pin(project, source)
    if pinned != source:
        target = pinned / "scripts" / script.name
        if not target.is_file():
            raise ValueError(
                f"Pinned skill lacks {script.name}; do not substitute another version"
            )
        print(f'Using pinned skill: {pinned / "SKILL.md"}', flush=True)
        os.execv(
            sys.executable,
            [sys.executable, str(target), *(sys.argv[1:] if argv is None else argv)],
        )


def guard_batch(projects: list[Path], script: Path, argv: list[str]) -> None:
    """Group projects by pinned tool version without mixing imports across versions."""
    source = script.resolve().parent.parent
    groups: dict[Path, list[Path]] = {}
    for project in projects:
        groups.setdefault(ensure_pin(project, source), []).append(project)
    if all(root == source for root in groups):
        return
    retained = []
    skipping = False
    for arg in argv:
        if arg == "--dirs" or arg.startswith("--dirs="):
            skipping = True
        elif arg.startswith("--"):
            skipping = False
            retained.append(arg)
        elif not skipping:
            retained.append(arg)
    codes = []
    for root, members in groups.items():
        codes.append(
            subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / script.name),
                    *retained,
                    "--dirs",
                    *(str(project) for project in members),
                ],
                check=False,
            ).returncode
        )
    raise SystemExit(1 if any(codes) else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument(
        "--local",
        action="store_true",
        help="Explicitly pin local tools for development/offline work; never an automatic fallback",
    )
    args = parser.parse_args()
    try:
        pinned = ensure_pin(
            args.project_dir, Path(__file__).resolve().parent.parent, local=args.local
        )
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(
            f"Skill bootstrap stopped: {exc}. Retry the update; do not silently use older tools.",
            file=sys.stderr,
        )
        return 1
    print(
        f'Read {pinned / "SKILL.md"} before planning. Use scripts from {pinned / "scripts"}.'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
