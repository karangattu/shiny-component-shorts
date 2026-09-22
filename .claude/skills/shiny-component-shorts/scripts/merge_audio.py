#!/usr/bin/env python3
"""Merge narration audio into a demo recording.

Uses measured constant gain toward -14 LUFS without exceeding -1.5 dBTP.
Can preserve a selected take without gain or filtering; encodes AAC and copies video.

In both modes the narration starts `NARRATION_OFFSET_SECONDS` into the video
(the recorder and validator time everything to that offset), and the silent
tail after the last word fades out instead of cutting to digital zero. An
optional music bed sits far under the voice and fades in and out with the video.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_narration import NARRATION_OFFSET_SECONDS  # noqa: E402

LOUDNORM_TARGET = "I=-14:TP=-1.5:LRA=11"
HIGHPASS = "highpass=f=70"
SPEECH_FLOOR_DB = -35.0
TAIL_FADE_SECONDS = 0.3
BED_LUFS = -38.0
BED_FADE_SECONDS = 1.2


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
        check=True,
    )
    blocks = re.findall(r"\{[^{}]*\}", result.stderr)
    if not blocks:
        raise SystemExit("Could not parse loudnorm measurement from ffmpeg output")
    return json.loads(blocks[-1])


def linear_gain_db(measured: dict) -> float:
    loudness, peak = float(measured['input_i']), float(measured['input_tp'])
    if not math.isfinite(loudness) or not math.isfinite(peak):
        raise ValueError("Narration must contain measurable, non-silent audio")
    return min(-14.0 - loudness, -1.5 - peak)


def speech_end(audio: Path, duration: float) -> float:
    """When the last word ends: the start of a silence that runs to the end."""
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
         "-af", f"silencedetect=noise={SPEECH_FLOOR_DB}dB:d=0.1", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", completed.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", completed.stderr)]
    if len(starts) > len(ends):
        return max(0.0, starts[-1])
    return duration


def narration_filters(gain_db: float | None, audio_duration: float, spoken_end: float) -> str:
    """Filter chain for the voice: optional gain, tail fade, lead-in, padding."""
    chain = [] if gain_db is None else [HIGHPASS, f"volume={gain_db:.6f}dB"]
    tail = audio_duration - spoken_end
    if tail >= 0.1:
        # Fade only the room tone after the last word; speech is never touched.
        fade = min(TAIL_FADE_SECONDS, tail - 0.05)
        chain.append(f"afade=t=out:st={spoken_end + 0.05:.3f}:d={fade:.3f}")
    delay_ms = round(NARRATION_OFFSET_SECONDS * 1000)
    chain.extend([f"adelay={delay_ms}:all=1", "apad"])
    return ",".join(chain)


def bed_filters(bed_gain_db: float, video_duration: float) -> str:
    fade_out = max(0.0, video_duration - BED_FADE_SECONDS)
    return (
        f"aloop=loop=-1:size=2147483647,atrim=0:{video_duration:.3f},"
        f"volume={bed_gain_db:.3f}dB,afade=t=in:d={BED_FADE_SECONDS},"
        f"afade=t=out:st={fade_out:.3f}:d={BED_FADE_SECONDS}"
    )


def merge(
    video: Path,
    audio: Path,
    output: Path,
    preserve_audio: bool = False,
    bed: Path | None = None,
    bed_lufs: float = BED_LUFS,
) -> None:
    measured = None if preserve_audio else measure_loudness(audio)
    audio_duration = probe_duration(audio)
    video_duration = probe_duration(video)
    if video_duration + 0.25 < audio_duration + NARRATION_OFFSET_SECONDS:
        raise SystemExit(
            f"Video ({video_duration:.2f}s) is shorter than narration "
            f"({audio_duration:.2f}s from {NARRATION_OFFSET_SECONDS:.2f}s); "
            "extend the recording before merging"
        )
    # Constant gain cannot switch into loudnorm's dynamic fallback or pump gaps.
    gain = None if preserve_audio or measured is None else linear_gain_db(measured)
    voice = narration_filters(gain, audio_duration, speech_end(audio, audio_duration))
    inputs = ["-i", str(video), "-i", str(audio)]
    if bed is None:
        audio_args = ["-af", voice]
    else:
        bed_gain = bed_lufs - float(measure_loudness(bed)["input_i"])
        inputs += ["-i", str(bed)]
        audio_args = [
            "-filter_complex",
            f"[1:a]{voice}[voice];[2:a]{bed_filters(bed_gain, video_duration)}[bed];"
            "[voice][bed]amix=inputs=2:duration=shortest:normalize=0[mix]",
            "-map",
            "0:v",
            "-map",
            "[mix]",
        ]
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            *audio_args,
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
    print(f"Audio {'preserved' if gain is None else f'constant gain {gain:.2f} dB'}; "
          f"narration {audio_duration:.2f}s from {NARRATION_OFFSET_SECONDS:.2f}s "
          f"in video {video_duration:.2f}s" + (f"; bed at {bed_lufs:g} LUFS" if bed else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, default=Path("artifacts/demo.mp4"))
    parser.add_argument("--audio", type=Path, default=Path("artifacts/narration.wav"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/final_with_audio.mp4")
    )
    parser.add_argument("--preserve-audio", action="store_true",
                        help="Keep the chosen take gain and dynamics; only fade the tail, delay, and pad")
    parser.add_argument("--bed", type=Path,
                        help="Optional music bed, looped far under the voice")
    parser.add_argument("--bed-lufs", type=float, default=BED_LUFS,
                        help="Integrated loudness of the bed (default: %(default)s LUFS)")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required to merge audio")

    project_dir = args.project_dir.resolve()
    video = args.video if args.video.is_absolute() else project_dir / args.video
    audio = args.audio if args.audio.is_absolute() else project_dir / args.audio
    output = args.output if args.output.is_absolute() else project_dir / args.output
    require_nonempty(video, "video")
    require_nonempty(audio, "narration audio")
    bed = None
    if args.bed is not None:
        bed = args.bed if args.bed.is_absolute() else project_dir / args.bed
        require_nonempty(bed, "music bed")
    merge(video, audio, output, preserve_audio=args.preserve_audio, bed=bed,
          bed_lufs=args.bed_lufs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
