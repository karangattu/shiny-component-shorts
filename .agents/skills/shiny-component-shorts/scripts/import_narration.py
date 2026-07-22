#!/usr/bin/env python3
"""Import existing narration audio (or a narrated video's audio track) as narration.wav.

Produces the same artifacts as generate_tts.py — a mono 24 kHz PCM WAV plus a
usage JSON — so the rest of the pipeline (timing measurement, actions.yaml
alignment, merge, validation) is unchanged. No TTS API is called and no
GEMINI_API_KEY is needed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Existing narration: an audio file (.wav/.mp3/.m4a) or a narrated video (.mp4/.webm/.mov)",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output .wav file")
    parser.add_argument(
        "--usage-output",
        type=Path,
        help="Usage JSON path (default: <output>.usage.json)",
    )
    return parser.parse_args()


def probe_audio(source: Path) -> float:
    """Return the audio stream duration in seconds, or raise if there is none."""
    completed = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type:format=duration",
            "-of", "json",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {source}: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout or "{}")
    if not payload.get("streams"):
        raise RuntimeError(f"No audio stream found in {source}")
    try:
        return float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Could not read audio duration from {source}") from exc


def extract_wav(source: Path, output: Path) -> None:
    """Convert the source's first audio stream to mono 24 kHz 16-bit PCM WAV."""
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(source),
            "-vn",
            "-map", "a:0",
            "-ac", "1",
            "-ar", "24000",
            "-c:a", "pcm_s16le",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed: {completed.stderr.strip()}")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg produced no output at {output}")


def write_usage_report(path: Path, *, source: Path, duration_seconds: float) -> None:
    report = {
        "provider": "Imported audio",
        "model": None,
        "voice": None,
        "source_file": str(source.resolve()),
        "input_tokens": 0,
        "output_audio_tokens": 0,
        "audio_duration_seconds": round(duration_seconds, 3),
        "usage_source": "Local ffmpeg extraction",
        "estimated_paid_tier_cost_usd": 0,
        "actual_billed_cost_usd": 0,
        "note": (
            "Narration was imported from existing audio; no TTS API was called "
            "and no API key was used."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    usage_output = args.usage_output or args.output.with_suffix(".usage.json")

    if not args.source.is_file():
        print(f"Source file does not exist: {args.source}", file=sys.stderr)
        return 2

    try:
        duration = probe_audio(args.source)
        extract_wav(args.source, args.output)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    write_usage_report(usage_output, source=args.source, duration_seconds=duration)
    print(f"Imported narration: {args.output}")
    print(f"Source: {args.source} ({duration:.2f}s audio)")
    print(f"Usage report: {usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
