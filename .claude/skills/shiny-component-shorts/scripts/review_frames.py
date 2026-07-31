#!/usr/bin/env python3
"""Tile a recording's key frames into one phone-size review sheet.

The verification gate asks whether the video reads on a phone, so review it at
phone width: one sheet holding the first, reveal, code, and final frames at
390 logical px each answers that question better than four 1440x2560 PNGs, and
costs an agent a fraction of the context to look at.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

MEANINGFUL_ACTIONS = frozenset(
    {"click", "drag", "select_option", "hover", "fill", "type", "press"}
)
# iPhone logical width: the size the recording is actually judged at.
PHONE_WIDTH = 390
TILE_BACKGROUND = "0x1D1F21"
# Two marks closer than this would render as the same frame twice.
MIN_MARK_GAP = 0.25


def require_media_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required to build a review sheet")


def probe(path: Path, entries: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            entries,
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def frame_size(path: Path) -> tuple[int, int]:
    stream = probe(path, "stream=width,height")["streams"][0]
    return int(stream["width"]), int(stream["height"])


def media_duration(path: Path) -> float:
    return float(probe(path, "format=duration")["format"]["duration"])


def load_timeline(recording_path: Path) -> list[dict]:
    if not recording_path.is_file():
        return []
    try:
        payload = json.loads(recording_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    timeline = payload.get("action_timeline")
    return [entry for entry in timeline if isinstance(entry, dict)] if isinstance(timeline, list) else []


def review_marks(timeline: list[dict], duration: float) -> list[tuple[str, float]]:
    """Timestamps for the frames the verification gate asks to inspect.

    The recorded action timeline places the reveal and code marks on the beats
    that matter; without one, the marks fall back to even spacing.
    """
    marks: list[tuple[str, float]] = [("first", min(0.4, duration / 4))]

    meaningful = [entry for entry in timeline if entry.get("action") in MEANINGFUL_ACTIONS]
    if meaningful:
        marks.append(("reveal", float(meaningful[0].get("end", 0.0)) + 0.6))
    else:
        marks.append(("reveal", duration / 3))

    code = next((entry for entry in timeline if entry.get("action") == "code"), None)
    if code is not None:
        start = float(code.get("start", 0.0))
        end = float(code.get("end", start))
        # Land inside the hold, after the card has typed itself out.
        marks.append(("code", start + max(2.0, (end - start) * 0.6)))
    else:
        marks.append(("code", duration * 2 / 3))

    marks.append(("final", duration - 0.3))

    limit = max(0.0, duration - 0.05)
    ordered: list[tuple[str, float]] = []
    for name, at in marks:
        clamped = round(min(max(at, 0.0), limit), 2)
        if ordered and abs(clamped - ordered[-1][1]) < MIN_MARK_GAP:
            continue
        ordered.append((name, clamped))
    return ordered


def extract_frame(video_path: Path, at: float, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{at:.2f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ],
        check=True,
    )


def build_sheet(images: list[Path], output_path: Path, width: int) -> dict:
    """Scale every frame to phone width and tile them into a single image."""
    if not images:
        raise ValueError("A review sheet needs at least one frame")
    source_width, source_height = frame_size(images[0])
    tile_width = width
    tile_height = max(1, round(width * source_height / source_width))
    columns = 1 if len(images) == 1 else 2
    rows = math.ceil(len(images) / columns)
    cells = columns * rows

    inputs: list[str] = []
    for image in images:
        inputs.extend(["-i", str(image)])
    for _ in range(cells - len(images)):
        # Fill the grid so xstack always has a complete layout.
        inputs.extend(
            ["-f", "lavfi", "-i", f"color=c={TILE_BACKGROUND}:s={tile_width}x{tile_height}"]
        )

    fit = (
        f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease,"
        f"pad={tile_width}:{tile_height}:(ow-iw)/2:(oh-ih)/2:color={TILE_BACKGROUND},setsar=1"
    )
    steps = [f"[{index}:v]{fit}[v{index}]" for index in range(cells)]
    target = "[v0]"
    if cells > 1:
        layout = "|".join(
            f"{(index % columns) * tile_width}_{(index // columns) * tile_height}"
            for index in range(cells)
        )
        labels = "".join(f"[v{index}]" for index in range(cells))
        steps.append(f"{labels}xstack=inputs={cells}:layout={layout}[sheet]")
        target = "[sheet]"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(steps),
            "-map",
            target,
            "-frames:v",
            "1",
            str(output_path),
        ],
        check=True,
    )
    return {
        "path": str(output_path),
        "tile_width": tile_width,
        "tile_height": tile_height,
        "columns": columns,
        "rows": rows,
        "width": columns * tile_width,
        "height": rows * tile_height,
    }


def resolve_input(project_dir: Path, path: Path) -> Path:
    if path.is_absolute() or path.is_file():
        return path
    return project_dir / path


def collect_frames(
    project_dir: Path, video_path: Path, images: list[Path] | None, work_dir: Path
) -> list[tuple[str, Path, str]]:
    """Return (label, image path, note) for every tile, in reading order."""
    if images:
        return [
            (path.stem, resolve_input(project_dir, path), str(path))
            for path in images
        ]

    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty recording: {video_path}")
    duration = media_duration(video_path)
    timeline = load_timeline(project_dir / "artifacts" / "recording.json")
    final_png = project_dir / "artifacts" / "final.png"

    frames: list[tuple[str, Path, str]] = []
    for label, at in review_marks(timeline, duration):
        if label == "final" and final_png.is_file() and final_png.stat().st_size > 0:
            frames.append((label, final_png, "artifacts/final.png"))
            continue
        extracted = work_dir / f"{label}.png"
        extract_frame(video_path, at, extracted)
        frames.append((label, extracted, f"{at:.2f}s"))
    return frames


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument(
        "--video", type=Path, help="Recording to sample (default: artifacts/demo.mp4)"
    )
    parser.add_argument(
        "--images",
        nargs="+",
        type=Path,
        help="Tile these images instead of sampling the recording",
    )
    parser.add_argument(
        "--output", type=Path, help="Sheet path (default: artifacts/review.png)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=PHONE_WIDTH,
        help=f"Tile width in logical px (default: {PHONE_WIDTH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.width < 40:
        print("--width must be at least 40 px")
        return 2
    project_dir = args.project_dir.resolve()
    video_path = (
        resolve_input(project_dir, args.video)
        if args.video
        else project_dir / "artifacts" / "demo.mp4"
    )
    output_path = (
        resolve_input(project_dir, args.output)
        if args.output
        else project_dir / "artifacts" / "review.png"
    )

    try:
        require_media_tools()
        with tempfile.TemporaryDirectory() as work_dir:
            frames = collect_frames(
                project_dir, video_path, args.images, Path(work_dir)
            )
            for _, path, _ in frames:
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError(f"Missing or empty frame: {path}")
            sheet = build_sheet([path for _, path, _ in frames], output_path, args.width)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Could not build the review sheet: {exc}")
        return 1

    print(
        f"Review sheet: {output_path} "
        f"({sheet['width']}x{sheet['height']}, {len(frames)} tiles at "
        f"{sheet['tile_width']}x{sheet['tile_height']})"
    )
    print("Tiles, left to right and top to bottom:")
    for index, (label, _, note) in enumerate(frames, start=1):
        print(f"  {index}. {label} — {note}")
    print("Read this one image; it shows every required frame at phone size.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
