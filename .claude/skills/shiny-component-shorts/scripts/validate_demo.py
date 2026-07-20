#!/usr/bin/env python3
"""Validate a generated Shiny component short and its media artifacts."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml


SUPPORTED_ACTIONS = frozenset(
    {
        "wait_for",
        "wait",
        "click",
        "drag",
        "select_option",
        "hover",
        "fill",
        "type",
        "press",
        "code",
        "zoom",
        "screenshot",
        "caption",
        "beat",
        "label",
    }
)
OVERLAY_ACTIONS = frozenset({"caption", "beat", "label"})
MEANINGFUL_ACTIONS = frozenset(
    {"click", "drag", "select_option", "hover", "fill", "type", "press"}
)
TAG_RE = re.compile(r"\[[^\]]+\]")
WORD_RE = re.compile(r"\b[\w’'-]+\b")
FORBIDDEN_VOCALIZATION_RE = re.compile(
    r"\[[^\]]*\b(?:laugh(?:ing|ter|s)?|giggl(?:e|es|ing)|chuckl(?:e|es|ing))\b[^\]]*\]",
    re.IGNORECASE,
)


def code_hold_ms(text: str, override: int | None = None) -> int:
    return override or max(5500, min(10000, 3200 + 55 * len(text)))


def estimate_action_seconds(actions: list[dict]) -> float:
    total_ms = 0
    for action in actions:
        if not isinstance(action, dict) or len(action) != 1:
            continue
        name, value = next(iter(action.items()))
        if name == "wait" and isinstance(value, (int, float)):
            total_ms += value
        elif name in {"click", "select_option", "hover", "fill", "press"}:
            total_ms += 1000
        elif name == "drag":
            total_ms += 1500
        elif name in OVERLAY_ACTIONS:
            total_ms += 300
        elif name == "zoom" and isinstance(value, dict):
            total_ms += 950 + int(value.get("hold", 1800))
        elif name == "type" and isinstance(value, dict):
            total_ms += len(str(value.get("value", ""))) * int(value.get("delay", 45)) + 1000
        elif name == "code" and isinstance(value, dict):
            text = str(value.get("text", "")).rstrip("\n")
            total_ms += len(text) * int(value.get("type_ms", 22))
            total_ms += code_hold_ms(text, value.get("duration"))
    return total_ms / 1000


def narration_metrics(path: Path) -> tuple[int, int, float]:
    text = path.read_text(encoding="utf-8")
    transcript = text.split("Transcript:", 1)[1]
    tags = len(TAG_RE.findall(transcript))
    spoken = TAG_RE.sub("", transcript)
    words = len(WORD_RE.findall(spoken))
    seconds = words / 2.5 + tags + 2
    return words, tags, seconds


def probe_video(path: Path) -> dict:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required to validate video artifacts")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    raw_bit_rate = payload["format"].get("bit_rate")
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "duration": float(payload["format"]["duration"]),
        "bit_rate": int(raw_bit_rate) if str(raw_bit_rate).isdigit() else None,
    }


def narration_sentence_windows(path: Path) -> list[dict] | None:
    """Speech spans in the WAV, derived from the gaps silencedetect reports."""
    if shutil.which("ffmpeg") is None or not path.is_file() or path.stat().st_size == 0:
        return None
    duration = probe_audio_duration(path)
    if duration is None:
        return None
    result = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-30dB:d=0.4",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", result.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", result.stderr)]
    windows: list[dict] = []
    cursor = 0.0
    for silence_start, silence_end in zip(starts, ends):
        if silence_start - cursor > 0.15:
            windows.append({"start": round(cursor, 2), "end": round(silence_start, 2)})
        cursor = silence_end
    if duration - cursor > 0.15:
        windows.append({"start": round(cursor, 2), "end": round(duration, 2)})
    return windows


def probe_audio_duration(path: Path) -> float | None:
    if shutil.which("ffprobe") is None or not path.is_file() or path.stat().st_size == 0:
        return None
    try:
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
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError):
        return None


def require_nonempty(path: Path, errors: list[str]) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        errors.append(f"Missing or empty file: {path}")
        return False
    return True


def validate_project(
    project_dir: Path,
    require_audio: bool = False,
    app_dir: Path | None = None,
) -> tuple[list[str], dict]:
    project_dir = project_dir.resolve()
    app_dir = (app_dir or project_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    report: dict = {"warnings": warnings}

    if not (app_dir / "app.py").is_file() and not (app_dir / "app.R").is_file():
        errors.append("App directory must contain app.py or app.R")

    if (app_dir / "app.R").is_file() and shutil.which("Rscript") is None:
        errors.append("Rscript command is not available in PATH; needed for R apps")
    if shutil.which("ffmpeg") is None:
        errors.append("ffmpeg command is not available in PATH; needed to compile recordings")
    if shutil.which("ffprobe") is None:
        errors.append("ffprobe command is not available in PATH; needed to validate video metrics")

    actions_path = project_dir / "actions.yaml"
    narration_path = project_dir / "artifacts" / "narration.txt"
    video_path = project_dir / "artifacts" / "demo.mp4"
    screenshot_path = project_dir / "artifacts" / "final.png"

    config: dict = {}
    actions: list[dict] = []
    if require_nonempty(actions_path, errors):
        try:
            loaded = yaml.safe_load(actions_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                errors.append("actions.yaml must contain a mapping")
            else:
                config = loaded
                if not isinstance(config.get("actions"), list):
                    errors.append("actions.yaml must contain an `actions` list")
                else:
                    actions = config["actions"]
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"Cannot read actions.yaml: {exc}")

    meaningful = 0
    screenshot_actions = 0
    caption_actions = 0
    beat_actions = 0
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict) or len(action) != 1:
            errors.append(f"Action {index} must contain exactly one key")
            continue
        name, value = next(iter(action.items()))
        if name not in SUPPORTED_ACTIONS:
            errors.append(f"Action {index} uses unsupported action: {name}")
            continue
        if name in MEANINGFUL_ACTIONS:
            meaningful += 1
        if name == "caption":
            caption_actions += 1
        if name == "beat":
            beat_actions += 1
        if name == "wait" and (not isinstance(value, (int, float)) or value < 0):
            errors.append(f"Action {index} has an invalid wait")
        elif name == "wait" and value > 3000:
            errors.append(f"Action {index} has an idle wait over 3000 ms")
        if name == "screenshot":
            screenshot_actions += 1
            if not isinstance(value, dict) or value.get("path") != "artifacts/final.png":
                errors.append("The screenshot action must target artifacts/final.png")

    if meaningful < 3:
        errors.append(f"Need at least 3 meaningful actions; found {meaningful}")
    if screenshot_actions != 1:
        errors.append(f"Need exactly one final screenshot action; found {screenshot_actions}")

    overlays = config.get("overlays")
    if not isinstance(overlays, dict) or not str(overlays.get("hook", "")).strip():
        warnings.append(
            "No retention hook: add an `overlays` block with a 5–9 word `hook`"
        )
    if actions and caption_actions == 0:
        warnings.append("No caption actions: viewers get no readable beat-by-beat text")
    if actions and beat_actions == 0:
        warnings.append("No beat actions: the progress rail never advances")

    opening_wait_ms = 0
    for action in actions:
        if not isinstance(action, dict) or len(action) != 1:
            continue
        name, value = next(iter(action.items()))
        if name in MEANINGFUL_ACTIONS or name == "code":
            break
        if name == "wait" and isinstance(value, (int, float)):
            opening_wait_ms += value
    if actions and opening_wait_ms > 2000:
        errors.append(
            f"Opening waits total {opening_wait_ms:.0f} ms before the first meaningful "
            "action; keep them at or under 2000 ms so the first action starts with the "
            "narration hook, and move slack to holds after reveals instead"
        )

    action_seconds = estimate_action_seconds(actions)
    report["meaningful_actions"] = meaningful
    report["estimated_action_seconds"] = round(action_seconds, 2)
    report["opening_wait_ms"] = round(opening_wait_ms)

    narration_seconds = 0.0
    if require_nonempty(narration_path, errors):
        narration_text = narration_path.read_text(encoding="utf-8")
        forbidden_cues = FORBIDDEN_VOCALIZATION_RE.findall(narration_text)
        if forbidden_cues:
            errors.append(
                "Narration must not contain laughing or giggling cues: "
                + ", ".join(forbidden_cues)
            )
        markers = ("Audio profile:", "Scene:", "Director's notes:", "Transcript:")
        missing_markers = [marker for marker in markers if marker not in narration_text]
        if missing_markers:
            errors.append(
                "Narration prompt is missing required sections: " + ", ".join(missing_markers)
            )
        else:
            words, tags, narration_seconds = narration_metrics(narration_path)
            report.update(
                {
                    "narration_words": words,
                    "narration_tags": tags,
                    "estimated_narration_seconds": round(narration_seconds, 2),
                }
            )
            measured = probe_audio_duration(project_dir / "artifacts" / "narration.wav")
            if measured is not None:
                narration_seconds = measured
                report["measured_narration_seconds"] = round(measured, 2)
            if not 60 <= words <= 85:
                errors.append(f"Narration must contain 60–85 spoken words; found {words}")
            if not 3 <= tags <= 6:
                errors.append(f"Narration must contain 3–6 audio tags; found {tags}")
            if action_seconds + 0.25 < narration_seconds:
                errors.append(
                    f"Estimated actions ({action_seconds:.2f}s) are shorter than narration "
                    f"with buffer ({narration_seconds:.2f}s)"
                )

    if require_nonempty(video_path, errors):
        try:
            video = probe_video(video_path)
            report["video"] = video
            recording_path = project_dir / "artifacts" / "recording.json"
            recording = {}
            if recording_path.is_file():
                recording = json.loads(recording_path.read_text(encoding="utf-8"))
            orientation = recording.get("orientation", config.get("orientation", "vertical"))
            expected = (1440, 2560) if orientation == "vertical" else (2560, 1440)
            if orientation not in {"vertical", "horizontal"}:
                errors.append(f"Unsupported orientation in actions.yaml: {orientation}")
            elif (video["width"], video["height"]) != expected:
                errors.append(
                    f"Video is {video['width']}x{video['height']}; expected "
                    f"{expected[0]}x{expected[1]} for {orientation}"
                )
            if video.get("bit_rate") is not None and video["bit_rate"] < 50_000:
                warnings.append(
                    f"Video bitrate is only {video['bit_rate'] / 1000:.0f} kbps; "
                    "screen recordings this sparse usually indicate a broken encode"
                )
            if narration_seconds and video["duration"] + 0.25 < narration_seconds:
                errors.append(
                    f"Video ({video['duration']:.2f}s) is shorter than narration "
                    f"with buffer ({narration_seconds:.2f}s)"
                )
        except (KeyError, ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot validate video: {exc}")

    timeline: list = []
    timeline_path = project_dir / "artifacts" / "recording.json"
    if timeline_path.is_file():
        try:
            timeline = json.loads(timeline_path.read_text(encoding="utf-8")).get(
                "action_timeline", []
            )
        except json.JSONDecodeError:
            timeline = []
    sentence_windows = narration_sentence_windows(
        project_dir / "artifacts" / "narration.wav"
    )
    if timeline:
        report["action_timeline"] = timeline
    if sentence_windows:
        report["narration_sentences"] = sentence_windows
    if timeline and sentence_windows:
        first_meaningful = next(
            (entry for entry in timeline if entry.get("action") in MEANINGFUL_ACTIONS),
            None,
        )
        if (
            first_meaningful is not None
            and first_meaningful["start"] > sentence_windows[0]["end"] + 0.5
        ):
            errors.append(
                f"First meaningful action starts at {first_meaningful['start']:.2f}s, "
                f"after the first narration sentence ends at "
                f"{sentence_windows[0]['end']:.2f}s; re-time the opening so the action "
                "is underway during the hook"
            )

    require_nonempty(screenshot_path, errors)

    if require_audio:
        require_nonempty(project_dir / "artifacts" / "narration.wav", errors)
        require_nonempty(project_dir / "artifacts" / "final_with_audio.mp4", errors)

    return errors, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--require-audio", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors, report = validate_project(args.project_dir, args.require_audio, args.app_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    for warning in report.get("warnings", []):
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated: {args.project_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
