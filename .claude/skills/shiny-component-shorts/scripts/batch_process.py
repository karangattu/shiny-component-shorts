#!/usr/bin/env python3
"""Run cached narration and finishing phases for Shiny component shorts."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import align_narration  # noqa: E402
import build_cache  # noqa: E402
import merge_audio  # noqa: E402
import validate_demo  # noqa: E402
from generate_local_voice import (  # noqa: E402
    MAX_SPEAKING_RATE,
    MIN_SPEAKING_RATE,
    validate_api_url,
)


BASE_PORT = 8000
PORT_RANGE_SIZE = 100
FAILED_STATES = {"FAILED", "ERROR", "BLOCKED"}


def start_port_for(project_index: int) -> int:
    port = BASE_PORT + project_index * PORT_RANGE_SIZE
    if port + PORT_RANGE_SIZE - 1 > 65535:
        raise ValueError("Too many projects to assign non-overlapping port ranges")
    return port


def new_result(project_dir: Path) -> dict:
    return {
        "name": project_dir.name,
        "record": "SKIPPED",
        "tts": "SKIPPED",
        "merge": "SKIPPED",
        "validate": "SKIPPED",
        "review_sheet": None,
        "errors": [],
        "duration": 0.0,
    }


def has_failures(results: list[dict]) -> bool:
    return any(
        result["errors"]
        or any(
            result[step] in FAILED_STATES
            for step in ("record", "tts", "merge", "validate")
        )
        for result in results
    )


def discover_projects(base_dir: Path, patterns: list[str] | None = None) -> list[Path]:
    """Find directories containing actions.yaml and an app entry point."""
    projects: list[Path] = []
    ignored = {
        ".git",
        ".github",
        ".venv",
        ".agents",
        ".claude",
        "tests",
        "assets",
        "artifacts",
    }
    if patterns:
        for pattern in patterns:
            requested = Path(pattern).expanduser()
            candidates = [] if requested.is_absolute() else list(base_dir.glob(pattern))
            direct = requested.resolve()
            if direct.is_dir():
                candidates.append(direct)
            for path in candidates:
                if (
                    path.is_dir()
                    and (path / "actions.yaml").is_file()
                    and ((path / "app.py").is_file() or (path / "app.R").is_file())
                ):
                    projects.append(path)
        return sorted(set(projects))

    for root, dirs, _files in os.walk(base_dir):
        dirs[:] = [directory for directory in dirs if directory not in ignored]
        path = Path(root)
        if (
            (path / "actions.yaml").is_file()
            and ((path / "app.py").is_file() or (path / "app.R").is_file())
        ):
            projects.append(path)
            dirs.clear()
    return sorted(projects)


def narration_inputs(project_dir: Path) -> list[Path]:
    inputs = [
        project_dir / "artifacts" / "narration.txt",
        SCRIPTS_DIR / "generate_tts.py",
        SCRIPTS_DIR / "validate_demo.py",
        SCRIPTS_DIR / "align_narration.py",
    ]
    settings_path = project_dir / "tts-settings.json"
    if settings_path.is_file():
        inputs.append(settings_path)
        settings = load_tts_settings(project_dir)
        source = audio_source_path(project_dir, settings)
        if source is not None:
            inputs.extend([SCRIPTS_DIR / "import_narration.py", source])
        reference = local_voice_reference_path(project_dir, settings)
        if reference is not None:
            inputs.extend([SCRIPTS_DIR / "generate_local_voice.py", reference])
    return inputs


def load_tts_settings(project_dir: Path) -> dict[str, str | float]:
    path = project_dir / "tts-settings.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("tts-settings.json must contain a JSON object")
    unknown = set(payload) - {
        "voice",
        "model",
        "audio_source",
        "provider",
        "saved_voice",
        "reference_voice",
        "reference_text",
        "engine_dir",
        "quality",
        "language",
        "api_url",
        "engine",
        "speaking_rate",
        "max_wpm",
        "audio_processing",
        "music_bed",
    }
    if unknown:
        raise ValueError(f"Unknown TTS settings: {', '.join(sorted(unknown))}")
    for key, value in payload.items():
        if key == "speaking_rate":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not MIN_SPEAKING_RATE <= value <= MAX_SPEAKING_RATE
            ):
                raise ValueError(
                    f"speaking_rate must be between {MIN_SPEAKING_RATE} and "
                    f"{MAX_SPEAKING_RATE}; slow a rushed voice with a value below "
                    "1.0 and retime the video instead of speeding it up"
                )
            continue
        if key == "max_wpm":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError("max_wpm must be a non-negative number (0 disables the pace gate)")
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TTS setting {key!r} must be a non-empty string")
    if "audio_source" in payload and ("voice" in payload or "model" in payload):
        raise ValueError(
            "TTS setting 'audio_source' cannot be combined with 'voice' or 'model'"
        )
    if payload.get("audio_processing", "normalize") not in {"normalize", "preserve"}:
        raise ValueError("audio_processing must be normalize or preserve")
    provider = payload.get("provider", "gemini")
    if provider not in {"gemini", "local-voice-cloning"}:
        raise ValueError(
            "TTS setting 'provider' must be 'gemini' or 'local-voice-cloning'"
        )
    if provider == "local-voice-cloning":
        if not any(key in payload for key in ("saved_voice", "reference_voice")):
            payload["saved_voice"] = "karan"
        if "api_url" in payload:
            validate_api_url(payload["api_url"])
        if payload.get("quality", "high") not in {"high", "fast"}:
            raise ValueError("quality must be high or fast")
        if payload.get("engine", "qwen") not in {"qwen", "omnivoice"}:
            raise ValueError("engine must be qwen or omnivoice")
        selected = [key for key in ("saved_voice", "reference_voice") if key in payload]
        if len(selected) != 1:
            raise ValueError(
                "Local voice cloning requires exactly one of 'saved_voice' or "
                "'reference_voice'"
            )
        if "saved_voice" in payload and not re.fullmatch(
            r"[a-z0-9_-]+", payload["saved_voice"]
        ):
            raise ValueError("TTS setting 'saved_voice' must be a saved voice name")
        incompatible = set(payload) & {"voice", "model", "audio_source"}
        if incompatible:
            raise ValueError(
                "Local voice cloning cannot use: " + ", ".join(sorted(incompatible))
            )
    return payload


def audio_source_path(
    project_dir: Path, settings: dict[str, str | float]
) -> Path | None:
    """Resolve the optional imported-narration source declared in tts-settings.json."""
    raw = settings.get("audio_source")
    if raw is None:
        return None
    source = Path(str(raw))
    return source if source.is_absolute() else project_dir / source


def local_voice_engine_dir(
    project_dir: Path, settings: dict[str, str | float]
) -> Path:
    raw = settings.get("engine_dir") or os.getenv("LOCAL_VOICE_CLONING_DIR")
    if raw:
        path = Path(str(raw)).expanduser()
        return path if path.is_absolute() else project_dir / path
    return SCRIPTS_DIR.parents[4] / "local-voice-cloning"


def local_voice_reference_path(
    project_dir: Path, settings: dict[str, str | float]
) -> Path | None:
    if settings.get("provider", "gemini") != "local-voice-cloning":
        return None
    if "reference_voice" in settings:
        path = Path(str(settings["reference_voice"])).expanduser()
        return path if path.is_absolute() else project_dir / path
    return (
        local_voice_engine_dir(project_dir, settings)
        / "voice_samples"
        / (str(settings["saved_voice"]) + ".wav")
    )


def recording_inputs(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    return build_cache.collect_project_inputs(
        project_dir,
        [
            SCRIPTS_DIR / "record_demo.py",
            SCRIPTS_DIR / "validate_demo.py",
            SCRIPTS_DIR / "align_narration.py",
            SCRIPTS_DIR.parent / "assets" / "shiny-logo.png",
            artifacts / "narration.wav",
            artifacts / "narration-timing.json",
            artifacts / "timing-approval.json",
        ],
    )


def music_bed_path(project_dir: Path, settings: dict[str, str | float]) -> Path | None:
    raw = settings.get("music_bed")
    if raw is None:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.is_absolute() else project_dir / path


def merge_inputs(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    settings_path = project_dir / "tts-settings.json"
    bed = music_bed_path(project_dir, load_tts_settings(project_dir))
    return [
        artifacts / "demo.mp4",
        artifacts / "narration.wav",
        SCRIPTS_DIR / "merge_audio.py",
        SCRIPTS_DIR / "align_narration.py",
        *([settings_path] if settings_path.is_file() else []),
        *([bed] if bed is not None else []),
    ]


def require_nonempty(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty {label}: {path}")


def measure_narration(audio_path: Path, prompt_path: Path) -> dict:
    """Word-timed narration report; a failed transcript check stops the phase."""
    report = align_narration.measure(audio_path, prompt_path.read_text(encoding="utf-8"))
    problems = align_narration.check_problems(report)
    if problems:
        raise RuntimeError("; ".join(problems))
    return report


def synthesis_command(
    project_dir: Path,
    settings: dict[str, str | float],
    narration: Path,
    audio: Path,
    usage: Path,
) -> list[str]:
    """The TTS, local-voice, or import command that writes `audio`."""
    source = audio_source_path(project_dir, settings)
    if source is not None:
        return [
            sys.executable,
            str(SCRIPTS_DIR / "import_narration.py"),
            "--source",
            str(source),
            "--output",
            str(audio),
            "--usage-output",
            str(usage),
        ]
    if settings.get("provider", "gemini") == "local-voice-cloning":
        reference = local_voice_reference_path(project_dir, settings)
        if reference is None:
            raise RuntimeError("Local voice reference could not be resolved")
        require_nonempty(reference, "local voice reference")
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "generate_local_voice.py"),
            "--input",
            str(narration),
            "--output",
            str(audio),
            "--usage-output",
            str(usage),
            "--engine-dir",
            str(local_voice_engine_dir(project_dir, settings)),
            "--reference",
            str(reference),
            "--quality",
            str(settings.get("quality", "high")),
            "--language",
            str(settings.get("language", "auto")),
        ]
        for option in ("api_url", "engine", "speaking_rate", "max_wpm"):
            if option in settings:
                command.extend(["--" + option.replace("_", "-"), str(settings[option])])
        if "reference_text" in settings:
            command.extend(["--ref-text", str(settings["reference_text"])])
        return command
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "generate_tts.py"),
        "--input",
        str(narration),
        "--output",
        str(audio),
        "--usage-output",
        str(usage),
    ]
    for option in ("voice", "model"):
        if option in settings:
            command.extend([f"--{option}", str(settings[option])])
    return command


def run_command(command: list[str], label: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or f"{label} failed")


def generate_narration(project_dir: Path, force: bool) -> dict:
    started = time.time()
    result = new_result(project_dir)
    artifacts = project_dir / "artifacts"
    narration = artifacts / "narration.txt"
    audio = artifacts / "narration.wav"
    usage = artifacts / "narration.usage.json"
    timing = artifacts / "narration-timing.json"
    outputs = [audio, usage, timing]
    try:
        require_nonempty(narration, "narration prompt")
        settings = load_tts_settings(project_dir)
        inputs = narration_inputs(project_dir)
        source = audio_source_path(project_dir, settings)
        if source is not None:
            require_nonempty(source, "narration audio source")
        if not force and build_cache.check_cache(project_dir, "tts", inputs, outputs):
            result["tts"] = "CACHED"
        else:
            run_command(
                synthesis_command(project_dir, settings, narration, audio, usage), "TTS"
            )
            require_nonempty(audio, "narration audio")
            require_nonempty(usage, "narration usage report")
            timing.write_text(
                json.dumps(measure_narration(audio, narration), indent=2) + "\n",
                encoding="utf-8",
            )
            build_cache.update_cache(project_dir, "tts", inputs)
            result["tts"] = "SUCCESS"
    except Exception as exc:
        result["tts"] = "FAILED"
        result["errors"].append(f"Narration failed: {exc}")
    result["duration"] = round(time.time() - started, 2)
    return result


def matched_gains(
    measurements: list[dict], target: float = -14.0, ceiling: float = -1.5
) -> tuple[float, list[float]]:
    """One common loudness every take reaches with linear gain under the ceiling."""
    achievable = [
        float(m["input_i"]) + ceiling - float(m["input_tp"]) for m in measurements
    ]
    common = min([target, *achievable])
    return common, [common - float(m["input_i"]) for m in measurements]


def generate_takes(project_dir: Path, count: int, force: bool) -> dict:
    """Synthesize raw local takes, loudness-match copies, and rank them."""
    started = time.time()
    result = new_result(project_dir)
    artifacts = project_dir / "artifacts"
    narration = artifacts / "narration.txt"
    takes_dir = artifacts / "narration-takes"
    try:
        require_nonempty(narration, "narration prompt")
        settings = load_tts_settings(project_dir)
        if settings.get("provider") != "local-voice-cloning":
            raise RuntimeError(
                "The takes phase synthesizes local voice-cloning takes only; set "
                "provider local-voice-cloning (paid providers are never re-run for takes)"
            )
        takes_dir.mkdir(parents=True, exist_ok=True)
        raws: list[Path] = []
        for number in range(1, count + 1):
            raw = takes_dir / f"take-{number}.wav"
            if force or not raw.is_file() or raw.stat().st_size == 0:
                run_command(
                    synthesis_command(
                        project_dir, settings, narration, raw,
                        takes_dir / f"take-{number}.usage.json",
                    ),
                    f"Take {number}",
                )
            require_nonempty(raw, f"take {number}")
            raws.append(raw)
        (takes_dir / "settings.json").write_text(
            json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        common, gains = matched_gains([merge_audio.measure_loudness(raw) for raw in raws])
        for raw, gain in zip(raws, gains):
            run_command(
                ["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw),
                 "-af", f"volume={gain:.4f}dB", "-c:a", "pcm_s16le",
                 str(raw.with_name(raw.stem + "-matched.wav"))],
                "Loudness matching",
            )
        ranking = align_narration.rank_takes(takes_dir, narration.read_text(encoding="utf-8"))
        ranking["comparison_lufs"] = round(common, 2)
        (takes_dir / "ranking.json").write_text(
            json.dumps(ranking, indent=2) + "\n", encoding="utf-8"
        )
        result["tts"] = "SUCCESS"
        result["takes"] = ranking
    except Exception as exc:
        result["tts"] = "FAILED"
        result["errors"].append(f"Takes failed: {exc}")
    result["duration"] = round(time.time() - started, 2)
    return result


def select_take(project_dir: Path, choice: str) -> Path:
    """Pin a ranked take's matched copy as the narration source."""
    takes_dir = project_dir / "artifacts" / "narration-takes"
    if choice == "recommended":
        ranking = json.loads((takes_dir / "ranking.json").read_text(encoding="utf-8"))
        choice = ranking["recommended"]
    stem = Path(choice).stem.removesuffix("-matched")
    matched = takes_dir / f"{stem}-matched.wav"
    require_nonempty(matched, "selected take")
    (project_dir / "tts-settings.json").write_text(
        json.dumps(
            {
                "audio_source": str(matched.relative_to(project_dir)),
                "audio_processing": "preserve",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return matched


def timing_paths(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    return [
        project_dir / "actions.yaml",
        artifacts / "narration.wav",
        artifacts / "narration-timing.json",
    ]


def timing_hashes(project_dir: Path) -> dict[str, str]:
    paths = timing_paths(project_dir) + narration_inputs(project_dir)
    return {str(path): build_cache.calculate_hash(path) for path in paths}


def approve_timing(project_dir: Path) -> None:
    for path in timing_paths(project_dir):
        require_nonempty(path, "timing approval input")
    approval = project_dir / "artifacts" / "timing-approval.json"
    approval.write_text(
        json.dumps({"approved_inputs": timing_hashes(project_dir)}, indent=2) + "\n",
        encoding="utf-8",
    )


def timing_is_approved(project_dir: Path) -> bool:
    approval = project_dir / "artifacts" / "timing-approval.json"
    try:
        payload = json.loads(approval.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    hashes = timing_hashes(project_dir)
    return all(hashes.values()) and payload.get("approved_inputs") == hashes


def prepare_finish(project_dir: Path, result: dict, approve: bool) -> bool:
    try:
        for path in timing_paths(project_dir):
            require_nonempty(path, "timing approval input")
        settings = load_tts_settings(project_dir)
        if settings.get("provider") == "local-voice-cloning":
            artifacts = project_dir / "artifacts"
            if not build_cache.check_cache(project_dir, "tts", narration_inputs(project_dir),
                    [artifacts / name for name in ("narration.wav", "narration.usage.json", "narration-timing.json")]):
                raise RuntimeError("Local narration is stale; rerun --phase narration before reviewing timing")
        if approve:
            approve_timing(project_dir)
        if not timing_is_approved(project_dir):
            raise RuntimeError(
                "Missing or stale timing approval; listen to the narration, adjust "
                "actions.yaml from narration-timing.json, then rerun with --approve-timing"
            )
        return True
    except Exception as exc:
        result["record"] = "BLOCKED"
        result["merge"] = "BLOCKED"
        result["validate"] = "BLOCKED"
        result["errors"].append(f"Finish preflight failed: {exc}")
        return False


def app_type(project_dir: Path) -> str:
    if (project_dir / "app.py").is_file():
        return "python"
    if (project_dir / "app.R").is_file():
        return "r"
    raise RuntimeError("No app.py or app.R found")


def record_project(
    project_dir: Path, start_port: int, result: dict, force: bool
) -> dict:
    artifacts = project_dir / "artifacts"
    inputs = recording_inputs(project_dir)
    outputs = [
        artifacts / "demo.mp4",
        artifacts / "recording.json",
        artifacts / "final.png",
    ]
    try:
        if not force and build_cache.check_cache(project_dir, "recording", inputs, outputs):
            result["record"] = "CACHED"
            return result
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "record_demo.py"),
            "--project-dir",
            str(project_dir),
            "--app-type",
            app_type(project_dir),
            "--actions",
            str(project_dir / "actions.yaml"),
            "--port",
            str(start_port),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Recording failed")
        for output in outputs:
            require_nonempty(output, "recording output")
        build_cache.update_cache(project_dir, "recording", inputs)
        result["record"] = "SUCCESS"
    except Exception as exc:
        result["record"] = "FAILED"
        result["merge"] = "BLOCKED"
        result["validate"] = "BLOCKED"
        result["errors"].append(f"Recording failed: {exc}")
    return result


def merge_project(project_dir: Path, result: dict, force: bool) -> dict:
    output = project_dir / "artifacts" / "final_with_audio.mp4"
    inputs = merge_inputs(project_dir)
    try:
        if not force and build_cache.check_cache(project_dir, "merge", inputs, [output]):
            result["merge"] = "CACHED"
            return result
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "merge_audio.py"),
            "--project-dir",
            str(project_dir),
        ]
        settings = load_tts_settings(project_dir)
        if settings.get("audio_processing") == "preserve":
            command.append("--preserve-audio")
        bed = music_bed_path(project_dir, settings)
        if bed is not None:
            require_nonempty(bed, "music bed")
            command.extend(["--bed", str(bed)])
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Merge failed")
        require_nonempty(output, "merged video")
        build_cache.update_cache(project_dir, "merge", inputs)
        result["merge"] = "SUCCESS"
    except Exception as exc:
        result["merge"] = "FAILED"
        result["validate"] = "BLOCKED"
        result["errors"].append(f"Merge failed: {exc}")
    return result


def build_review_sheet(project_dir: Path) -> str | None:
    """Leave one phone-size sheet per video so the frame review is one image."""
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_frames.py"),
            "--project-dir",
            str(project_dir),
        ],
        capture_output=True,
        text=True,
    )
    sheet = project_dir / "artifacts" / "review.png"
    return str(sheet) if completed.returncode == 0 and sheet.is_file() else None


def validate_project(project_dir: Path, result: dict) -> dict:
    try:
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "validate_demo.py"),
            "--project-dir",
            str(project_dir),
            "--require-audio",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stdout or completed.stderr or "Validation failed")
        result["validate"] = "PASSED"
        result["review_sheet"] = build_review_sheet(project_dir)
    except Exception as exc:
        result["validate"] = "FAILED"
        result["errors"].append(f"Validation failed: {exc}")
    return result


def run_parallel(
    items: list[tuple], worker: Callable[..., dict], max_workers: int
) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, *item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def run_narration_phase(
    projects: list[Path], force: bool, max_workers: int
) -> list[dict]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(generate_narration, project, force) for project in projects
        ]
        return [future.result() for future in concurrent.futures.as_completed(futures)]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("takes", "narration", "finish"), required=True)
    parser.add_argument("--dirs", nargs="*", help="Directories or glob patterns")
    parser.add_argument("--force", action="store_true", help="Ignore stage caches")
    parser.add_argument(
        "--approve-timing",
        action="store_true",
        help="Approve current narration timing inputs before the finish phase",
    )
    parser.add_argument(
        "--takes", type=int, default=3, help="Raw local takes to synthesize (takes phase)"
    )
    parser.add_argument(
        "--select-take",
        help="Pin a take (file name or 'recommended') as the narration source (takes phase)",
    )
    parser.add_argument("--tts-concurrency", type=int, default=3)
    parser.add_argument("--record-concurrency", type=int, default=2)
    parser.add_argument("--merge-concurrency", type=int, default=2)
    parser.add_argument("--validate-concurrency", type=int, default=3)
    parser.add_argument("--tts", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--merge", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def validate_cli_args(args: argparse.Namespace) -> None:
    if args.tts or args.merge:
        raise ValueError(
            "--tts/--merge are deprecated. Run --phase narration, review and adjust "
            "timing, then run --phase finish --approve-timing."
        )
    if args.approve_timing and args.phase != "finish":
        raise ValueError("--approve-timing is valid only with --phase finish")
    if args.select_take and args.phase != "takes":
        raise ValueError("--select-take is valid only with --phase takes")
    if args.takes < 1:
        raise ValueError("--takes must be at least 1")
    for name in (
        "tts_concurrency",
        "record_concurrency",
        "merge_concurrency",
        "validate_concurrency",
    ):
        if getattr(args, name) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be at least 1")


def print_summary(results: list[dict]) -> None:
    print("\nBatch summary")
    for result in sorted(results, key=lambda item: item["name"]):
        print(
            f"{result['name']}: TTS={result['tts']} Record={result['record']} "
            f"Merge={result['merge']} Validate={result['validate']}"
        )
        takes = result.get("takes")
        if takes:
            for take in takes["takes"]:
                print(
                    f"  {take['take']}: score {take['score']} "
                    f"(WER {take['word_error_rate']:.0%}, {take['words_per_minute']} WPM)"
                )
            print(f"  recommended take: {takes['recommended']}")
        if result.get("review_sheet"):
            print(f"  review sheet: {result['review_sheet']}")
        for error in result["errors"]:
            print(f"  - {error}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        validate_cli_args(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    projects = discover_projects(Path.cwd(), args.dirs)
    if not projects:
        print("No project directories discovered.")
        return 0
    try:
        ports = [start_port_for(index) for index in range(len(projects))]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.phase == "takes":
        if args.select_take:
            for project in projects:
                print(f"{project.name}: narration source -> {select_take(project, args.select_take)}")
            print("Rerun --phase narration to import and time the selected take.")
            return 0
        # Local synthesis shares one device, so takes run one project at a time.
        results = [generate_takes(project, args.takes, args.force) for project in projects]
        print_summary(results)
        return 1 if has_failures(results) else 0

    if args.phase == "narration":
        results = run_narration_phase(projects, args.force, args.tts_concurrency)
        print_summary(results)
        return 1 if has_failures(results) else 0

    started = {project: time.time() for project in projects}
    results_by_project = {project: new_result(project) for project in projects}
    ready = [
        project
        for project in projects
        if prepare_finish(project, results_by_project[project], args.approve_timing)
    ]
    run_parallel(
        [
            (project, port, results_by_project[project], args.force)
            for project, port in zip(projects, ports)
            if project in ready
        ],
        record_project,
        args.record_concurrency,
    )
    recorded = [
        project
        for project in ready
        if results_by_project[project]["record"] in {"SUCCESS", "CACHED"}
    ]
    run_parallel(
        [(project, results_by_project[project], args.force) for project in recorded],
        merge_project,
        args.merge_concurrency,
    )
    merged = [
        project
        for project in recorded
        if results_by_project[project]["merge"] in {"SUCCESS", "CACHED"}
    ]
    run_parallel(
        [(project, results_by_project[project]) for project in merged],
        validate_project,
        args.validate_concurrency,
    )
    results = [results_by_project[project] for project in projects]
    for project, result in results_by_project.items():
        result["duration"] = round(time.time() - started[project], 2)
    print_summary(results)
    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
