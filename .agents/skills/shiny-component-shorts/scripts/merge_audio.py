#!/usr/bin/env python3
"""Merge narration audio into a demo recording.

Runs two-pass loudnorm to the -14 LUFS short-form target, applies a 70 Hz
high-pass and short edge fades, encodes 48 kHz 192 kbps AAC, and copies the
video stream untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

LOUDNORM_TARGET = "I=-14:TP=-1.5:LRA=11"
HIGHPASS = "highpass=f=70"


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def require_nonempty(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty {label}: {path}")


def measure_loudness(audio: Path) -> dict:
    """First loudnorm pass: measure through the same high-pass used at encode."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(audio),
            "-af",
            f"{HIGHPASS},loudnorm={LOUDNORM_TARGET}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    blocks = re.findall(r"\{[^{}]*\}", result.stderr)
    if not blocks:
        raise SystemExit("Could not parse loudnorm measurement from ffmpeg output")
    return json.loads(blocks[-1])


def merge(video: Path, audio: Path, output: Path) -> None:
    measured = measure_loudness(audio)
    audio_duration = probe_duration(audio)
    video_duration = probe_duration(video)
    if video_duration + 0.25 < audio_duration:
        raise SystemExit(
            f"Video ({video_duration:.2f}s) is shorter than narration "
            f"({audio_duration:.2f}s); extend the recording before merging"
        )
    loudnorm = (
        f"loudnorm={LOUDNORM_TARGET}"
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
        ":linear=true"
    )
    fade_out_start = max(0.0, audio_duration - 0.25)
    filters = (
        f"{HIGHPASS},{loudnorm},"
        f"afade=t=in:st=0:d=0.15,afade=t=out:st={fade_out_start:.2f}:d=0.25,apad"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-af",
            filters,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-shortest",
            str(output),
        ],
        check=True,
    )
    require_nonempty(output, "merged output")
    print(f"Merged: {output}")
    print(
        f"Input loudness {measured['input_i']} LUFS -> -14 LUFS target "
        f"(two-pass linear); audio {audio_duration:.2f}s in video {video_duration:.2f}s"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, default=Path("artifacts/demo.mp4"))
    parser.add_argument("--audio", type=Path, default=Path("artifacts/narration.wav"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/final_with_audio.mp4")
    )
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required to merge audio")

    project_dir = args.project_dir.resolve()
    video = args.video if args.video.is_absolute() else project_dir / args.video
    audio = args.audio if args.audio.is_absolute() else project_dir / args.audio
    output = args.output if args.output.is_absolute() else project_dir / args.output
    require_nonempty(video, "video")
    require_nonempty(audio, "narration audio")
    merge(video, audio, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
