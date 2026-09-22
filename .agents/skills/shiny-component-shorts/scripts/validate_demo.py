#!/usr/bin/env python3
"""Validate a generated Shiny component short and its media artifacts."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import align_narration  # noqa: E402
from align_narration import NARRATION_OFFSET_SECONDS  # noqa: E402


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
        "cue",
        "screenshot",
    }
)
REMOVED_ACTIONS = {
    "zoom": "zoom was removed; punch-ins fire at unpredictable moments — "
    "cut the action and let the reveal breathe at full frame"
}
MEANINGFUL_ACTIONS = frozenset(
    {"click", "drag", "select_option", "hover", "fill", "type", "press"}
)
VISIBLE_ACTIONS = MEANINGFUL_ACTIONS | {"code"}
# A cued reaction may lead its phrase by a second or trail it by half a second.
CUE_EARLY_SECONDS = 1.0
CUE_LATE_SECONDS = 0.5
MIN_CUED_ACTIONS = 3
CODE_EXIT_MS = 320  # the code card fades out before the next action runs
TAG_RE = re.compile(r"\[[^\]]+\]")
WORD_RE = re.compile(r"\b[\w’'-]+\b")
FORBIDDEN_VOCALIZATION_RE = re.compile(
    r"\[[^\]]*\b(?:laugh(?:ing|ter|s)?|giggl(?:e|es|ing)|chuckl(?:e|es|ing))\b[^\]]*\]",
    re.IGNORECASE,
)


def code_hold_ms(text: str, override: int | None = None, context: str = "") -> int:
    return override or max(
        7500, min(16000, 4800 + 70 * len(text) + 18 * len(context))
    )


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
        elif name == "type" and isinstance(value, dict):
            total_ms += len(str(value.get("value", ""))) * int(value.get("delay", 45)) + 1000
        elif name == "code" and isinstance(value, dict):
            text = str(value.get("text", "")).rstrip("\n")
            context = str(value.get("before", "")) + str(value.get("after", ""))
            total_ms += len(text) * int(value.get("type_ms", 22))
            total_ms += code_hold_ms(text, value.get("duration"), context) + CODE_EXIT_MS
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
            "stream=width,height:format=duration",
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
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "duration": float(payload["format"]["duration"]),
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


def code_block_source_errors(
    index: int, value: dict, source_lines: list[str]
) -> list[str]:
    """The code card must mirror the app source, including indentation.

    Every non-comment line must exist in the source, and one uniform
    indentation offset must map the card onto the source so relative
    indentation is preserved exactly.
    """
    problems: list[str] = []
    offsets: set[int] | None = None
    for key in ("before", "text", "after"):
        block = str(value.get(key) or "")
        for line in block.strip("\n").split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            candidates = {
                (len(source) - len(source.lstrip(" "))) - indent
                for source in source_lines
                if source.strip() == stripped
            }
            if not candidates:
                problems.append(
                    f"Action {index} code line is not in the app source "
                    f"verbatim: {stripped!r}"
                )
                continue
            offsets = candidates if offsets is None else offsets & candidates
    if offsets is not None and not offsets and not problems:
        problems.append(
            f"Action {index} code indentation does not mirror the app source: "
            "the card's lines need one uniform indentation offset from their "
            "source lines — copy the leading whitespace exactly (use a YAML "
            "block indicator such as `before: |2` so it is not stripped)"
        )
    return problems


def shift_windows(windows: list[dict] | None, offset: float) -> list[dict] | None:
    """Narration windows in video time: the merge starts narration `offset` in."""
    if windows is None:
        return None
    return [
        {**window, "start": round(window["start"] + offset, 2),
         "end": round(window["end"] + offset, 2)}
        for window in windows
    ]


def cue_value(value: object) -> dict:
    """Normalize a `cue` action: a phrase, {phrase, occurrence}, or {at: seconds}."""
    if isinstance(value, str) and value.strip():
        return {"phrase": value.strip(), "occurrence": 1}
    if isinstance(value, dict):
        if "at" in value and isinstance(value["at"], (int, float)):
            return {"at": float(value["at"])}
        phrase = value.get("phrase")
        occurrence = value.get("occurrence", 1)
        if isinstance(phrase, str) and phrase.strip() and isinstance(occurrence, int) and occurrence >= 1:
            return {"phrase": phrase.strip(), "occurrence": occurrence}
    raise ValueError(
        "cue needs a spoken phrase, {phrase: ..., occurrence: N}, or {at: narration seconds}"
    )


def resolve_cue_times(actions: list[dict], timing: dict | None) -> dict[int, dict]:
    """Video time of every cue, keyed by its 0-based action index."""
    resolved: dict[int, dict] = {}
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or "cue" not in action or len(action) != 1:
            continue
        spec = cue_value(action["cue"])
        if "at" in spec:
            resolved[index] = {"phrase": None, "narration": spec["at"]}
        else:
            if timing is None:
                raise ValueError(
                    "cue actions need word timing for the current narration.wav: run "
                    "align_narration.py --project-dir <demo> (or batch --phase narration)"
                )
            found = align_narration.find_phrase(timing["words"], spec["phrase"], spec["occurrence"])
            resolved[index] = {"phrase": spec["phrase"], "narration": found["start"]}
        resolved[index]["target"] = round(resolved[index]["narration"] + NARRATION_OFFSET_SECONDS, 2)
    return resolved


def cue_problems(actions: list[dict]) -> list[str]:
    """A cue anchors the very next visible action, so nothing may sit between them."""
    problems: list[str] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or "cue" not in action:
            continue
        try:
            cue_value(action["cue"])
        except ValueError as exc:
            problems.append(f"Action {index + 1}: {exc}")
            continue
        following = actions[index + 1] if index + 1 < len(actions) else None
        name = next(iter(following)) if isinstance(following, dict) and following else None
        if name not in VISIBLE_ACTIONS:
            problems.append(
                f"Action {index + 1}: a cue must be followed directly by the visible "
                f"action it anchors (click, drag, select_option, hover, fill, type, press, "
                f"or code); found {name or 'nothing'}"
            )
    return problems


def project_simulated_timeline(
    actions: list[dict], cue_times: dict[int, dict] | None = None
) -> list[dict]:
    timeline: list[dict] = []
    current_ms = 0.0
    pending: dict | None = None
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or len(action) != 1:
            continue
        name, value = next(iter(action.items()))
        if name == "cue":
            pending = (cue_times or {}).get(index)
            continue
        if pending is not None and name in VISIBLE_ACTIONS:
            # Pointer actions travel early, then react exactly on the phrase.
            lead_ms = 0 if name in {"code", "press"} else 600
            current_ms = max(current_ms, pending["target"] * 1000 - lead_ms)
        started = current_ms
        if name == "wait" and isinstance(value, (int, float)):
            current_ms += value
        elif name in {"click", "select_option", "hover", "fill", "press"}:
            current_ms += 1000
        elif name == "drag":
            current_ms += 1500
        elif name == "type" and isinstance(value, dict):
            current_ms += len(str(value.get("value", ""))) * int(value.get("delay", 45)) + 1000
        elif name == "code" and isinstance(value, dict):
            text = str(value.get("text", "")).rstrip("\n")
            context = str(value.get("before", "")) + str(value.get("after", ""))
            current_ms += len(text) * int(value.get("type_ms", 22))
            current_ms += code_hold_ms(text, value.get("duration"), context) + CODE_EXIT_MS
        elif name == "screenshot":
            current_ms += 100
        entry: dict = {
            "action": name,
            "start": round(started / 1000.0, 2),
            "end": round(current_ms / 1000.0, 2),
        }
        if pending is not None and name in VISIBLE_ACTIONS:
            lead = 0.0 if name in {"code", "press"} else 0.6
            entry["reaction"] = round(max(pending["target"], started / 1000.0 + lead), 2)
            entry["cue"] = {"phrase": pending["phrase"], "target": pending["target"]}
            pending = None
        timeline.append(entry)
    return timeline


def load_or_estimate_sentence_windows(project_dir: Path) -> list[dict] | None:
    timing = align_narration.load_timing(project_dir)
    if timing is not None:
        return timing["sentences"]
    timing_file = project_dir / "artifacts" / "narration-timing.json"
    if timing_file.is_file():
        try:
            data = json.loads(timing_file.read_text(encoding="utf-8"))
            if "sentence_windows" in data:
                return data["sentence_windows"]
        except (json.JSONDecodeError, OSError):
            pass

    wav_file = project_dir / "artifacts" / "narration.wav"
    if wav_file.is_file() and wav_file.stat().st_size > 0:
        windows = narration_sentence_windows(wav_file)
        if windows:
            return windows

    txt_file = project_dir / "artifacts" / "narration.txt"
    if txt_file.is_file() and txt_file.stat().st_size > 0:
        text = txt_file.read_text(encoding="utf-8")
        if "Transcript:" in text:
            transcript = text.split("Transcript:", 1)[1]
            spoken = TAG_RE.sub("", transcript)
            sentences = [s.strip() for s in re.split(r"[.!?]+", spoken) if s.strip()]
            if sentences:
                total_words = len(WORD_RE.findall(spoken))
                duration = max(10.0, total_words / 2.5 + 2.0)
                windows = []
                cursor = 0.0
                for s in sentences:
                    w_count = len(WORD_RE.findall(s))
                    s_dur = max(1.5, round(w_count / 2.5, 2))
                    windows.append({"start": round(cursor, 2), "end": round(min(duration, cursor + s_dur), 2)})
                    cursor += s_dur + 0.4
                return windows
    return None


def validate_project(
    project_dir: Path,
    require_audio: bool = False,
    app_dir: Path | None = None,
    simulate_timing: bool = False,
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

    app_source_lines: list[str] | None = None
    for app_name in ("app.py", "app.R"):
        app_path = app_dir / app_name
        if app_path.is_file():
            app_source_lines = app_path.read_text(encoding="utf-8").split("\n")
            break

    meaningful = 0
    screenshot_actions = 0
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict) or len(action) != 1:
            errors.append(f"Action {index} must contain exactly one key")
            continue
        name, value = next(iter(action.items()))
        if name in REMOVED_ACTIONS:
            errors.append(f"Action {index}: {REMOVED_ACTIONS[name]}")
            continue
        if name not in SUPPORTED_ACTIONS:
            errors.append(f"Action {index} uses unsupported action: {name}")
            continue
        if name in MEANINGFUL_ACTIONS:
            meaningful += 1
        if name == "wait" and (not isinstance(value, (int, float)) or value < 0):
            errors.append(f"Action {index} has an invalid wait")
        elif name == "wait" and value > 3000:
            errors.append(f"Action {index} has an idle wait over 3000 ms")
        if name == "code" and isinstance(value, dict) and app_source_lines is not None:
            errors.extend(code_block_source_errors(index, value, app_source_lines))
        if name == "screenshot":
            screenshot_actions += 1
            if not isinstance(value, dict) or value.get("path") != "artifacts/final.png":
                errors.append("The screenshot action must target artifacts/final.png")

    if meaningful < 3:
        errors.append(f"Need at least 3 meaningful actions; found {meaningful}")
    errors.extend(cue_problems(actions))
    if screenshot_actions != 1:
        errors.append(f"Need exactly one final screenshot action; found {screenshot_actions}")

    opening_wait_ms = 0
    for action in actions:
        if not isinstance(action, dict) or len(action) != 1:
            continue
        name, value = next(iter(action.items()))
        if name in MEANINGFUL_ACTIONS or name in {"code", "cue"}:
            break
        if name == "wait" and isinstance(value, (int, float)):
            opening_wait_ms += value
    if actions and opening_wait_ms > 2000:
        errors.append(
            f"Opening waits total {opening_wait_ms:.0f} ms before the first meaningful "
            "action; keep them at or under 2000 ms so the first action starts with the "
            "narration hook, and move slack to holds after reveals instead"
        )

    word_timing = align_narration.load_timing(project_dir)
    try:
        cue_times = resolve_cue_times(actions, word_timing)
    except ValueError as exc:
        errors.append(str(exc))
        cue_times = {}
    projected = project_simulated_timeline(actions, cue_times)
    # Cues hold actions until their phrase, so the projection beats a plain sum.
    action_seconds = max(
        estimate_action_seconds(actions), projected[-1]["end"] if projected else 0.0
    )
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
            if not 95 <= words <= 130:
                errors.append(f"Narration must contain 95–130 spoken words; found {words}")
            if not 3 <= tags <= 6:
                errors.append(f"Narration must contain 3–6 audio tags; found {tags}")
            if action_seconds + 0.25 < narration_seconds + NARRATION_OFFSET_SECONDS:
                errors.append(
                    f"Estimated actions ({action_seconds:.2f}s) are shorter than narration "
                    f"with buffer ({narration_seconds:.2f}s)"
                )

    timeline: list = []
    sentence_windows: list[dict] | None = None
    if word_timing is not None:
        report["alignment_method"] = word_timing.get("alignment_method")
        check = word_timing.get("transcript_check") or {}
        report["transcript_check"] = {
            key: check.get(key) for key in ("word_error_rate", "differences", "vocalizations")
        }
        errors.extend(
            f"Narration audio: {problem}" for problem in align_narration.check_problems(word_timing)
        )
        rate = check.get("word_error_rate") or 0.0
        if align_narration.WARN_WORD_ERROR_RATE < rate <= align_narration.MAX_WORD_ERROR_RATE:
            warnings.append(
                f"Narration differs from the transcript in places (word error rate {rate:.0%}); "
                "check transcript_check.differences for mispronounced code"
            )
    elif require_audio:
        errors.append(
            "No word timing for the current narration.wav: run align_narration.py "
            "--project-dir <demo> (or batch --phase narration) so cues and sync checks "
            "use the spoken words instead of silence gaps"
        )
    if not simulate_timing:
        if require_nonempty(video_path, errors):
            try:
                video = probe_video(video_path)
                report["video"] = video
                recording_path = project_dir / "artifacts" / "recording.json"
                recording = {}
                if recording_path.is_file():
                    recording = json.loads(recording_path.read_text(encoding="utf-8"))
                if recording and not recording.get("logo"):
                    errors.append(
                        "Recording carries no Shiny wordmark: artifacts/recording.json has "
                        "no `logo` entry, so this video predates the brand overlay — "
                        "re-record it with the bundled recorder"
                    )
                orientation = recording.get("orientation", config.get("orientation", "vertical"))
                expected = (1440, 2560) if orientation == "vertical" else (2560, 1440)
                if orientation not in {"vertical", "horizontal"}:
                    errors.append(f"Unsupported orientation in actions.yaml: {orientation}")
                elif (video["width"], video["height"]) != expected:
                    errors.append(
                        f"Video is {video['width']}x{video['height']}; expected "
                        f"{expected[0]}x{expected[1]} for {orientation}"
                    )
                measured_narration = report.get("measured_narration_seconds")
                if measured_narration:
                    overrun = video["duration"] - measured_narration - NARRATION_OFFSET_SECONDS
                    if not 0.75 <= overrun <= 3.5:
                        errors.append(
                            f"Video runs {overrun:.2f}s past the narration "
                            f"({video['duration']:.2f}s video vs {measured_narration:.2f}s "
                            f"audio starting at {NARRATION_OFFSET_SECONDS:.2f}s); the payoff needs 1–3 s of screen time after the last "
                            "sentence — adjust the closing holds, never the opening wait"
                        )
                elif narration_seconds and video["duration"] + 0.25 < narration_seconds:
                    errors.append(
                        f"Video ({video['duration']:.2f}s) is shorter than narration "
                        f"with buffer ({narration_seconds:.2f}s)"
                    )
            except (KeyError, ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
                errors.append(f"Cannot validate video: {exc}")

        timeline_path = project_dir / "artifacts" / "recording.json"
        if timeline_path.is_file():
            try:
                timeline = json.loads(timeline_path.read_text(encoding="utf-8")).get(
                    "action_timeline", []
                )
            except json.JSONDecodeError:
                timeline = []
        sentence_windows = (
            word_timing["sentences"]
            if word_timing is not None
            else narration_sentence_windows(project_dir / "artifacts" / "narration.wav")
        )
    else:
        report["simulated_timing"] = True
        timeline = projected
        sentence_windows = load_or_estimate_sentence_windows(project_dir)
        measured_or_est = report.get("measured_narration_seconds") or report.get("estimated_narration_seconds") or narration_seconds
        if measured_or_est:
            overrun = action_seconds - measured_or_est - NARRATION_OFFSET_SECONDS
            if not 0.75 <= overrun <= 3.5:
                errors.append(
                    f"Simulated actions run {overrun:.2f}s past narration "
                    f"({action_seconds:.2f}s actions vs {measured_or_est:.2f}s "
                    "narration); the payoff needs 1–3 s of screen time after the last "
                    "sentence — adjust the closing holds, never the opening wait"
                )

    sentence_windows = shift_windows(sentence_windows, NARRATION_OFFSET_SECONDS)
    if timeline:
        report["action_timeline"] = timeline
    if sentence_windows:
        report["narration_sentences"] = sentence_windows
    errors.extend(cue_timing_errors(timeline, actions, require_audio and word_timing is not None))
    if timeline and sentence_windows:
        narration_end = sentence_windows[-1]["end"]
        visible_events = [
            entry
            for entry in timeline
            if entry.get("action") in MEANINGFUL_ACTIONS
            or entry.get("action") == "code"
        ]
        def moment(entry: dict) -> float:
            """When the viewer sees the action: its reaction, else its start."""
            return float(entry.get("reaction", entry["start"]))

        first_meaningful = next(
            (entry for entry in visible_events if entry["action"] in MEANINGFUL_ACTIONS),
            None,
        )
        if (
            first_meaningful is not None
            and moment(first_meaningful) > sentence_windows[0]["end"] + 0.5
        ):
            errors.append(
                f"First meaningful action starts at {moment(first_meaningful):.2f}s, "
                f"after the first narration sentence ends at "
                f"{sentence_windows[0]['end']:.2f}s; re-time the opening so the action "
                "is underway during the hook"
            )
        late = [
            entry
            for entry in visible_events
            if moment(entry) > narration_end + 0.25
        ]
        if late:
            errors.append(
                f"{len(late)} visible action(s) start after the narration ends at "
                f"{narration_end:.2f}s (first: {late[0]['action']} at "
                f"{moment(late[0]):.2f}s); everything the viewer must see belongs "
                "inside the spoken track — after it, only hold the payoff"
            )
        previous_end = 0.0
        for entry in visible_events:
            if moment(entry) >= narration_end:
                break
            gap = moment(entry) - previous_end
            if gap > 8.0:
                errors.append(
                    f"Dead air: no visible action between {previous_end:.2f}s and "
                    f"{moment(entry):.2f}s while narration plays; keep a reaction, "
                    "contrast, or the code card on screen at least every 8 s"
                )
            previous_end = max(previous_end, entry["end"])
        if visible_events and narration_end - previous_end > 8.0:
            errors.append(
                f"Dead air: the last visible action ends at {previous_end:.2f}s but "
                f"narration continues to {narration_end:.2f}s; add a proof or hold a "
                "changing state under the closing sentences"
            )

    if not simulate_timing:
        require_nonempty(screenshot_path, errors)

    if require_audio and not simulate_timing:
        require_nonempty(project_dir / "artifacts" / "narration.wav", errors)
        require_nonempty(project_dir / "artifacts" / "final_with_audio.mp4", errors)

    return errors, report


def cue_timing_errors(timeline: list, actions: list[dict], require_cues: bool) -> list[str]:
    """Hold every cued reaction to the moment its phrase is spoken."""
    errors: list[str] = []
    cued = [entry for entry in timeline if isinstance(entry, dict) and entry.get("cue")]
    for entry in cued:
        target = float(entry["cue"]["target"])
        reaction = float(entry.get("reaction", entry.get("start", 0.0)))
        offset = reaction - target
        if not -CUE_EARLY_SECONDS <= offset <= CUE_LATE_SECONDS:
            label = entry["cue"].get("phrase") or f"{target:.2f}s"
            errors.append(
                f"{entry['action']} reacts at {reaction:.2f}s, {offset:+.2f}s from its cue "
                f"{label!r} at {target:.2f}s (allowed −{CUE_EARLY_SECONDS:.1f} to "
                f"+{CUE_LATE_SECONDS:.1f} s); shorten the waits before it or move the cue"
            )
    if require_cues:
        names = [next(iter(a)) for a in actions if isinstance(a, dict) and len(a) == 1]
        anchored = {
            names[i + 1] for i, name in enumerate(names[:-1]) if name == "cue"
        }
        cued_meaningful = sum(
            1 for i, name in enumerate(names[:-1])
            if name == "cue" and names[i + 1] in MEANINGFUL_ACTIONS
        )
        if cued_meaningful < MIN_CUED_ACTIONS:
            errors.append(
                f"Anchor at least {MIN_CUED_ACTIONS} meaningful actions to the phrases "
                f"that describe them with `cue` actions; found {cued_meaningful}"
            )
        if "code" in names and "code" not in anchored:
            errors.append("Anchor the code action to the sentence that introduces the code with a `cue`")
    return errors


def write_report(project_dir: Path, report: dict) -> Path | None:
    """Park the full report beside the media instead of in the reader's face."""
    if not project_dir.is_dir():
        return None
    path = project_dir / "artifacts" / "validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def timing_lines(report: dict) -> list[str]:
    """Each visible action against the narration sentence it lands in.

    This is the comparison the verification gate asks for, resolved here so
    nobody has to eyeball two arrays of timestamps.
    """
    timeline = report.get("action_timeline") or []
    windows = report.get("narration_sentences") or []
    if not timeline or not windows:
        return []
    lines: list[str] = []
    for entry in timeline:
        action = entry.get("action")
        if action not in MEANINGFUL_ACTIONS and action != "code":
            continue
        start = float(entry.get("reaction", entry.get("start", 0.0)))
        index = next(
            (
                number
                for number, window in enumerate(windows, start=1)
                # A reaction may lead its sentence by up to a second.
                if window["start"] - 1.0 <= start <= window["end"]
            ),
            None,
        )
        landing = f"sentence {index}" if index else "no sentence"
        cue = entry.get("cue")
        if cue:
            offset = start - float(cue["target"])
            landing += f", {offset:+.2f}s from cue {cue.get('phrase') or cue['target']!r}"
        lines.append(f"  {action:<14} {start:6.2f}s  {landing}")
    return lines


def summary_lines(report: dict) -> list[str]:
    lines = []
    if report.get("simulated_timing"):
        lines.append("mode: simulated timing (pre-recording dry-run)")
    lines.append(
        f"actions: {report.get('meaningful_actions', 0)} meaningful, "
        f"~{report.get('estimated_action_seconds', 0)}s, "
        f"opening wait {report.get('opening_wait_ms', 0)} ms"
    )
    video = report.get("video")
    if video:
        lines.append(
            f"video: {video['width']}x{video['height']}, {video['duration']:.2f}s"
        )
    measured = report.get("measured_narration_seconds")
    estimated = report.get("estimated_narration_seconds")
    if measured or estimated:
        source = "measured" if measured else "estimated"
        lines.append(
            f"narration: {report.get('narration_words', '?')} words, "
            f"{report.get('narration_tags', '?')} tags, "
            f"{measured or estimated:.2f}s ({source})"
        )
    timing = timing_lines(report)
    if timing:
        lines.append("timing (visible action → narration sentence):")
        lines.extend(timing)
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--app-dir", type=Path)
    parser.add_argument("--require-audio", action="store_true")
    parser.add_argument(
        "--simulate-timing",
        action="store_true",
        help="Simulate and validate actions.yaml timing against narration without requiring video recording",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full report instead of the summary",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors, report = validate_project(
        args.project_dir,
        args.require_audio,
        args.app_dir,
        simulate_timing=args.simulate_timing,
    )
    report_path = write_report(args.project_dir, report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for line in summary_lines(report):
            print(line)
        if report_path is not None:
            print(f"full report: {report_path}")
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
