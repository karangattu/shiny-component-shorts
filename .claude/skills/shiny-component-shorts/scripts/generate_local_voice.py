#!/usr/bin/env python3
"""Generate narration with a reference voice through local-voice-cloning."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from generate_tts import validate_narration_prompt


TAG_RE = re.compile(r"\[[^\]]+\]")
PAUSE_TAG_RE = re.compile(r"\[(short|medium|long) pause\]", re.IGNORECASE)
PAUSE_BREAKS = {"short": "\n", "medium": "\n", "long": "\n\n"}


def local_voice_script(prompt: str) -> str:
    """Return tag-free transcript text with explicit local-engine pause breaks."""
    if "Transcript:" not in prompt:
        raise ValueError("Narration prompt is missing the Transcript: section")
    transcript = prompt.split("Transcript:", 1)[1].strip()
    transcript = re.sub(r"\s+", " ", transcript)
    transcript = PAUSE_TAG_RE.sub(
        lambda match: PAUSE_BREAKS[match.group(1).lower()], transcript
    )
    transcript = TAG_RE.sub("", transcript)
    transcript = re.sub(r"[ \t]*\n[ \t]*", "\n", transcript)
    transcript = re.sub(r" {2,}", " ", transcript)
    return transcript.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--usage-output", required=True, type=Path)
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--ref-text", default="")
    parser.add_argument("--quality", choices=("high", "fast"), default="high")
    parser.add_argument("--language", default="auto")
    return parser.parse_args(argv)


def wave_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for path, label in (
        (args.input, "narration prompt"),
        (args.reference, "reference voice"),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            print(f"Missing or empty {label}: {path}", file=sys.stderr)
            return 2
    if not args.engine_dir.is_dir():
        print(
            f"Local voice cloning directory does not exist: {args.engine_dir}",
            file=sys.stderr,
        )
        return 2

    prompt = args.input.read_text(encoding="utf-8").strip()
    errors = validate_narration_prompt(prompt)
    if errors:
        print(f"Invalid narration prompt in {args.input}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    script = local_voice_script(prompt)
    if not script:
        print("Narration transcript is empty after removing tags.", file=sys.stderr)
        return 2

    uv = shutil.which("uv")
    if uv is None:
        print(
            "Missing dependency: install uv to run local-voice-cloning.",
            file=sys.stderr,
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        uv,
        "run",
        "--project",
        str(args.engine_dir),
        "python",
        "-m",
        "src.cli",
        "--reference",
        str(args.reference),
        "--text",
        script,
        "--quality",
        args.quality,
        "--language",
        args.language,
        "--output",
        str(args.output),
    ]
    if args.ref_text:
        command.extend(["--ref-text", args.ref_text])
    completed = subprocess.run(
        command,
        cwd=args.engine_dir,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(
            completed.stderr or completed.stdout or "Local voice cloning failed",
            file=sys.stderr,
        )
        return completed.returncode or 1
    if not args.output.is_file() or args.output.stat().st_size <= 44:
        print(
            f"Local voice cloning did not create a valid WAV file: {args.output}",
            file=sys.stderr,
        )
        return 1

    try:
        duration = wave_duration(args.output)
    except (OSError, wave.Error, ZeroDivisionError) as exc:
        print(f"Could not read generated WAV file: {exc}", file=sys.stderr)
        return 1
    report = {
        "provider": "Local voice cloning",
        "model": f"Qwen3-TTS 1.7B · {args.quality}",
        "voice": str(args.reference),
        "audio_duration_seconds": round(duration, 3),
        "usage_source": "Local Apple MLX generation",
        "estimated_paid_tier_cost_usd": 0,
        "actual_billed_cost_usd": 0,
        "note": "Local compute; no paid TTS API was called.",
    }
    args.usage_output.parent.mkdir(parents=True, exist_ok=True)
    args.usage_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated local narration: {args.output}")
    print(f"Reference voice: {args.reference}")
    print(f"Usage report: {args.usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
