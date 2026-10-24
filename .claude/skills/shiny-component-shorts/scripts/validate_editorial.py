#!/usr/bin/env python3
"""Decode editorial exports and check framing, chapters, cues, and source freshness."""
from __future__ import annotations

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import stitch_reel as reel


def validate_report(report: dict) -> dict:
    """Fail on a stale source plan, malformed timeline, missing audio, or bad encode."""
    if report.get("style") != "editorial" or not report.get("segments"):
        raise ValueError(
            "Re-render with the current editorial renderer to record source provenance"
        )
    orientation = report["orientation"]
    for segment in report["segments"]:
        plan = reel.editorial_plan(Path(segment["path"]), orientation)
        if reel.cache_key(plan) != segment["plan_key"]:
            raise ValueError(
                f"Export is stale: source media, narration, framing, or renderer changed in {segment['path']}"
            )
    path = Path(report["reel"])
    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-show_streams",
                "-show_format",
                "-show_chapters",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    video = next((s for s in probe["streams"] if s["codec_type"] == "video"), {})
    audio = next((s for s in probe["streams"] if s["codec_type"] == "audio"), {})
    dimensions = [size * reel.SCALE for size in reel.SIZES[orientation]]
    if [video.get("width"), video.get("height")] != dimensions or Fraction(
        video.get("avg_frame_rate", "0")
    ) != reel.FPS:
        raise ValueError("Unexpected video dimensions or frame rate")
    if (
        video.get("codec_name") != "h264"
        or audio.get("codec_name") != "aac"
        or audio.get("sample_rate") != "48000"
    ):
        raise ValueError("Expected H.264 video and 48 kHz AAC narration")
    duration = float(probe["format"]["duration"])
    frames = int(video["nb_read_frames"])
    if (
        abs(duration - report["duration_seconds"]) > 0.06
        or abs(frames / reel.FPS - report["duration_seconds"]) > 1 / reel.FPS
    ):
        raise ValueError("Export duration does not match the planned timeline")
    shots = report["shots"]
    if not shots or shots[0]["start"] != 0 or abs(shots[-1]["end"] - duration) > 0.06:
        raise ValueError("Shots must cover the complete video")
    for index, shot in enumerate(shots):
        if shot["end"] <= shot["start"] or (index and shots[index - 1]["end"] != shot["start"]):
            raise ValueError("Shot times overlap or leave a gap")
        if index and not 0 <= shot["start"] - shot["cue_time"] <= 1 / reel.FPS + 0.001:
            raise ValueError("A shot is out of sync with its spoken phrase")
    chapters = report["chapters"]
    embedded = probe.get("chapters", [])
    if (
        not chapters
        or len(chapters) != len(embedded)
        or chapters[0]["start"] != 0
        or abs(chapters[-1]["end"] - duration) > 0.06
    ):
        raise ValueError("Missing or incomplete chapter metadata")
    for expected, actual in zip(chapters, embedded):
        if actual.get("tags", {}).get("title") != expected["label"] or any(
            abs(float(actual[key + "_time"]) - expected[key]) > 0.002 for key in ("start", "end")
        ):
            raise ValueError("Embedded chapter boundaries or titles differ from the report")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "video": str(path),
        "orientation": orientation,
        "seconds": duration,
        "frames": frames,
        "decode": "passed",
        "sources": "current",
        "phrase_sync": "within one frame",
        "listening": "not assessed by this tool",
    }


def validate(reel_dir: Path, orientation: str = "both") -> list[dict]:
    """Validate only declared exports, never caches or preserved comparison renders."""
    artifacts = reel_dir / "artifacts"
    manifest = artifacts / "series.json"
    if manifest.is_file():
        reports = json.loads(manifest.read_text())["videos"]
    else:
        reports = [
            json.loads(path.read_text())
            for path in artifacts.glob("reel*.json")
            if path.name in ("reel.json", "reel-vertical.json", "reel-horizontal.json")
        ]
    if orientation != "both":
        reports = [r for r in reports if r["orientation"] == orientation]
    if not reports:
        raise ValueError("No editorial exports found")
    groups: dict[str, set[str]] = {}
    for report in reports:
        groups.setdefault(str(Path(report["reel"]).parent), set()).add(report["orientation"])
    required = set(reel.SIZES) if orientation == "both" else {orientation}
    if any(views != required for views in groups.values()):
        raise ValueError(
            "Each video needs both orientation exports unless one orientation was explicitly selected"
        )
    results = [validate_report(report) for report in reports]
    (artifacts / "editorial-validation.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reel-dir", type=Path, required=True)
    parser.add_argument("--orientation", choices=("both", *reel.SIZES), default="both")
    args = parser.parse_args()
    for result in validate(args.reel_dir, args.orientation):
        print(
            f"{result['orientation']}: {result['seconds']:.3f}s, full decode passed; sources and cues current"
        )


if __name__ == "__main__":
    main()
