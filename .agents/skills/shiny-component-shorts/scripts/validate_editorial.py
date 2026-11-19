#!/usr/bin/env python3
"""Decode editorial exports and check framing, chapters, cues, and source freshness."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

import yaml

import stitch_reel as reel

LAYOUT_COPY_NAMES = {"app_portrait.py", "portrait.py"}
CORRUPTED_NUMBER_RE = re.compile(r"\b\d[\d,]*\.?\s+(?:hundred|thousand)\b", re.IGNORECASE)


def _srt_seconds(stamp: str) -> float:
    hms, ms = stamp.strip().split(",")
    h, m, s = (int(part) for part in hms.split(":"))
    return h * 3600 + m * 60 + s + int(ms) / 1000.0


def parse_srt(srt_path: Path) -> list[tuple[float, float, str]]:
    text = srt_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\r?\n\r?\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start_s, end_s = lines[1].split("-->", 1)
        cues.append((_srt_seconds(start_s), _srt_seconds(end_s), " ".join(lines[2:])))
    return cues


def check_captions(srt_path: Path, shots: list[dict]) -> None:
    if not srt_path.is_file() or not srt_path.stat().st_size:
        raise ValueError(f"Missing or empty captions file: {srt_path}")
    cues = parse_srt(srt_path)
    if not cues:
        raise ValueError(f"Captions file has no SRT cues: {srt_path}")
    for _, _, body in cues:
        if CORRUPTED_NUMBER_RE.search(body):
            raise ValueError(f"Corrupted numeric caption in {srt_path}: {body!r}")
    end_card_start = next(
        (
            float(shot["start"])
            for shot in shots
            if "end-card" in str(shot.get("source", "")) or shot.get("label") == "End card"
        ),
        None,
    )
    if end_card_start is not None and cues[-1][1] > end_card_start - 0.01:
        raise ValueError(
            f"Caption bleed: last cue ends at {cues[-1][1]:.2f}s, overlapping end card at {end_card_start:.2f}s"
        )


def longest_static_hold(video_path: Path, shots: list[dict], width: int, height: int) -> float:
    """Measure the longest frozen stretch (seconds) inside non-still video shots."""
    live_windows = [
        (float(shot["start"]), float(shot["end"]))
        for shot in shots
        if not str(shot.get("source", "")).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    if not live_windows:
        return 0.0
    sample_fps = 2
    sw = 96
    sh = max(2, round(sw * height / width / 2) * 2)
    raw = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(video_path),
            "-vf", f"fps={sample_fps},scale={sw}:{sh}:flags=fast_bilinear,format=gray",
            "-f", "rawvideo", "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    frame_bytes = sw * sh
    total_frames = len(raw) // frame_bytes
    max_run = 0.0
    run = 0.0
    prev_mv = None
    prev_window = None
    mv = memoryview(raw)
    sampled = max(1, frame_bytes // 2)
    for idx in range(total_frames):
        t = idx / sample_fps
        window = next(
            (w_idx for w_idx, (a, b) in enumerate(live_windows) if a + 0.15 <= t <= b - 0.15),
            None,
        )
        curr_mv = mv[idx * frame_bytes : (idx + 1) * frame_bytes]
        if window is None or window != prev_window or prev_mv is None:
            run = 0.0
            prev_mv = curr_mv
            prev_window = window
            continue
        changed = sum(1 for p in range(0, frame_bytes, 2) if abs(curr_mv[p] - prev_mv[p]) >= 10)
        if changed / sampled < 0.002:
            run += 1.0 / sample_fps
            if run > max_run:
                max_run = run
        else:
            run = 0.0
        prev_mv = curr_mv
    return round(max_run, 2)


def validate_report(
    report: dict,
    *,
    max_static_hold: float = 0.0,
    srt_path: Path | None = None,
) -> dict:
    """Fail on a stale source plan, malformed timeline, missing audio, or bad encode."""
    if report.get("style") != "editorial" or not report.get("segments"):
        raise ValueError(
            "Re-render with the current editorial renderer to record source provenance"
        )
    orientation = report["orientation"]
    for segment in report["segments"]:
        seg_dir = Path(segment["path"])
        plan = reel.editorial_plan(seg_dir, orientation)
        if reel.cache_key(plan) != segment["plan_key"]:
            raise ValueError(
                f"Export is stale: source media, narration, framing, or renderer changed in {segment['path']}"
            )
        source_shots = seg_dir / "source-shots.yaml"
        if source_shots.is_file():
            ss = yaml.safe_load(source_shots.read_text(encoding="utf-8")) or {}
            for shot in ss.get("shots") or []:
                panels = list(shot.get("panels") or [])
                for view in (shot.get("views") or {}).values():
                    panels.extend(view.get("panels") or [])
                for panel in panels:
                    if (
                        panel.get("kind", "code") == "code"
                        and Path(str(panel.get("file", ""))).name in LAYOUT_COPY_NAMES
                        and not panel.get("allow_layout_copy")
                    ):
                        raise ValueError(
                            f"Code card references layout copy {panel['file']}; reference real app.py"
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
        # A cut may lead its phrase by a few frames; it never trails it.
        if index and not (
            -reel.MAX_CUT_LEAD_SECONDS - 0.001
            <= shot["start"] - shot["cue_time"]
            <= 1 / reel.FPS + 0.001
        ):
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
    static_hold = longest_static_hold(path, shots, dimensions[0], dimensions[1]) if shots else 0.0
    if max_static_hold > 0 and static_hold > max_static_hold:
        raise ValueError(
            f"Static hold {static_hold:.1f}s exceeds max_static_hold {max_static_hold:.1f}s in live footage"
        )
    if srt_path is not None:
        check_captions(srt_path, shots)
    return {
        "video": str(path),
        "orientation": orientation,
        "seconds": duration,
        "frames": frames,
        "max_static_hold_seconds": static_hold,
        "decode": "passed",
        "sources": "current",
        "phrase_sync": "each cut leads its phrase by at most half a second",
        "listening": "not assessed by this tool",
    }


def validate(
    reel_dir: Path,
    orientation: str = "both",
    *,
    max_static_hold: float = 0.0,
    srt_path: Path | None = None,
) -> list[dict]:
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
    results = [
        validate_report(report, max_static_hold=max_static_hold, srt_path=srt_path)
        for report in reports
    ]
    (artifacts / "editorial-validation.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reel-dir", type=Path, required=True)
    parser.add_argument("--orientation", choices=("both", *reel.SIZES), default="both")
    parser.add_argument("--max-static-hold", type=float, default=0.0, help="Fail if any live video hold stays static longer than N seconds")
    parser.add_argument("--srt", type=Path, help="Optional SRT captions file to check against end-card bleed and numeric corruption")
    args = parser.parse_args()
    for result in validate(args.reel_dir, args.orientation, max_static_hold=args.max_static_hold, srt_path=args.srt):
        print(
            f"{result['orientation']}: {result['seconds']:.3f}s, full decode passed; sources and cues current"
        )


if __name__ == "__main__":
    main()
