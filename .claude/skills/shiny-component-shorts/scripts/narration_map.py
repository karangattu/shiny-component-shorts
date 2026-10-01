#!/usr/bin/env python3
"""Show where narration sentences and phrases land, for authoring cues.

`record_demo.py --dry-run` resolves cue times once `actions.yaml` exists; this
answers "when is this phrase spoken?" before it does.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import align_narration  # noqa: E402


def sentence_lines(timing: dict) -> list[str]:
    """One line per spoken sentence: narration time, video time, text."""
    lines = []
    for number, sentence in enumerate(timing["sentences"], start=1):
        video = sentence["start"] + align_narration.NARRATION_OFFSET_SECONDS
        lines.append(
            f"{number:>3}  narration {sentence['start']:6.2f}s  video {video:6.2f}s  "
            f"{sentence['text']}"
        )
    return lines


def phrase_line(timing: dict, phrase: str, occurrence: int) -> str:
    found = align_narration.find_phrase(timing["words"], phrase, occurrence)
    video = found["start"] + align_narration.NARRATION_OFFSET_SECONDS
    return (
        f"{phrase!r} (occurrence {occurrence}): narration "
        f"{found['start']:.2f}-{found['end']:.2f}s -> video {video:.2f}s "
        f"(sentence {found['sentence'] + 1})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, help="Demo directory")
    parser.add_argument(
        "--phrase", action="append", default=[], help="Cue phrase to resolve (repeatable)"
    )
    parser.add_argument("--occurrence", type=int, default=1, help="Nth spoken occurrence")
    args = parser.parse_args(argv)

    project = Path(args.project_dir)
    timing = align_narration.load_timing(project)
    if timing is None:
        print(
            "No usable word timing for the current narration.wav; run "
            f"align_narration.py --project-dir {project} (or batch --phase narration) first."
        )
        return 1

    duration = timing.get("duration_seconds", 0.0)
    print(
        f"narration: {duration:.2f}s of speech; every video time below adds "
        f"{align_narration.NARRATION_OFFSET_SECONDS:.2f}s of lead-in"
    )
    for line in sentence_lines(timing):
        print(line)
    for phrase in args.phrase:
        try:
            print(phrase_line(timing, phrase, args.occurrence))
        except ValueError as exc:
            print(exc)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
