#!/usr/bin/env python3
"""Load and apply spoken and display pronunciation lexicons."""

from __future__ import annotations

import functools
import re
from pathlib import Path

import yaml

DEFAULT_LEXICON = Path(__file__).resolve().parent.parent / "assets" / "pronunciations.yaml"


def lexicon_files(project: Path | None = None) -> list[Path]:
    paths = [DEFAULT_LEXICON]
    if project is not None:
        paths.append(project / DEFAULT_LEXICON.name)
    return [path for path in paths if path.is_file()]


def project_for_artifact(path: Path) -> Path:
    """Find the project for a narration prompt, finished WAV, or raw take."""
    folder = path.resolve().parent
    if folder.name == "narration-takes" and folder.parent.name == "artifacts":
        folder = folder.parent
    return folder.parent if folder.name == "artifacts" else folder


def load_lexicon(project: Path | None = None) -> dict[str, dict[str, str]]:
    """Return merged default and optional project-level pronunciation maps."""
    merged: dict[str, dict[str, str]] = {"spoken": {}, "display": {}}
    for path in lexicon_files(project):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: lexicon must be a YAML mapping")
        for kind in ("spoken", "display"):
            section = payload.get(kind) or {}
            if not isinstance(section, dict):
                raise ValueError(f"{path}: {kind} must be a mapping")
            for key, value in section.items():
                merged[kind][str(key)] = str(value)
    return merged


@functools.lru_cache(maxsize=32)
def _compiled_pattern(items: tuple[tuple[str, str], ...]) -> re.Pattern[str]:
    keys = sorted((key for key, _ in items), key=len, reverse=True)
    joined = "|".join(re.escape(key) for key in keys)
    return re.compile(rf"(?<![A-Za-z0-9_-])(?:{joined})(?![A-Za-z0-9_-])")


def _apply(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text
    items = tuple(sorted(mapping.items()))
    pattern = _compiled_pattern(items)
    return pattern.sub(lambda match: mapping[match.group(0)], text)


def to_spoken(text: str, lexicon: dict[str, dict[str, str]] | None = None) -> str:
    """Replace technical spellings with TTS-friendly spoken forms."""
    active = load_lexicon() if lexicon is None else lexicon
    return _apply(text, active.get("spoken") or {})


def to_display(text: str, lexicon: dict[str, dict[str, str]] | None = None) -> str:
    """Restore canonical technical spellings in caption phrases."""
    active = load_lexicon() if lexicon is None else lexicon
    return _apply(text, active.get("display") or {})
