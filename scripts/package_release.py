#!/usr/bin/env python3
"""Package tracked skill trees with version provenance and SHA-256 checksums."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path


def package(repo: Path, tag: str, output: Path) -> list[Path]:
    if not re.fullmatch(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", tag):
        raise ValueError("Release tags must use vMAJOR.MINOR.PATCH")
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for variant, tree in [("codex", ".agents"), ("claude", ".claude")]:
        data = subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "archive",
                "--format=zip",
                f"HEAD:{tree}/skills/shiny-component-shorts",
            ]
        )
        path = output / f"shiny-component-shorts-{tag}-{variant}.zip"
        prefix = "shiny-component-shorts/"
        with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(
            path, "w", compression=zipfile.ZIP_DEFLATED
        ) as dest:
            for item in source.infolist():
                dest.writestr(prefix + item.filename, source.read(item))
            dest.writestr(prefix + "VERSION", tag[1:] + "\n")
            dest.writestr(
                prefix + "release.json",
                json.dumps(
                    {
                        "version": tag[1:],
                        "tag": tag,
                        "commit": commit,
                        "variant": variant,
                    },
                    indent=2,
                )
                + "\n",
            )
        archives.append(path)
    (output / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
            for path in archives
        )
    )
    return archives


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for path in package(repo, args.tag, args.output):
        print(path)


if __name__ == "__main__":
    main()
