#!/usr/bin/env python3
"""Build caching library for Shiny component short videos."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


def calculate_hash(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    if not filepath.is_file():
        return ""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def get_cache_manifest_path(project_dir: Path) -> Path:
    """Get path to the build cache manifest."""
    return project_dir / "artifacts" / "build_cache.json"


def check_cache(
    project_dir: Path,
    step: str,
    input_files: list[Path],
    output_files: list[Path],
) -> bool:
    """
    Check if a step's cache is valid.
    
    Returns True if cache is valid and outputs exist and are non-empty.
    """
    # 1. Check if all outputs exist and are non-empty
    for outfile in output_files:
        if not outfile.is_file() or outfile.stat().st_size == 0:
            return False

    # 2. Load manifest
    manifest_path = get_cache_manifest_path(project_dir)
    if not manifest_path.is_file():
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    step_data = manifest.get(step)
    if not step_data or "inputs" not in step_data:
        return False

    # 3. Verify input files hashes
    inputs = step_data["inputs"]
    for infile in input_files:
        rel_path = str(infile.relative_to(project_dir)) if infile.is_relative_to(project_dir) else str(infile)
        stored_hash = inputs.get(rel_path)
        if not stored_hash:
            return False
        
        current_hash = calculate_hash(infile)
        if current_hash != stored_hash:
            return False

    return True


def update_cache(
    project_dir: Path,
    step: str,
    input_files: list[Path],
) -> None:
    """Update cache manifest for the specified step."""
    manifest_path = get_cache_manifest_path(project_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    inputs = {}
    for infile in input_files:
        rel_path = str(infile.relative_to(project_dir)) if infile.is_relative_to(project_dir) else str(infile)
        inputs[rel_path] = calculate_hash(infile)

    manifest[step] = {
        "inputs": inputs,
        "timestamp": time.time(),
    }

    try:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
