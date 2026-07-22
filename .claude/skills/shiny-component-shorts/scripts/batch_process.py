#!/usr/bin/env python3
"""Run cached narration and finishing phases for Shiny component shorts."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import build_cache
import validate_demo


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
    ]
    settings_path = project_dir / "tts-settings.json"
    if settings_path.is_file():
        inputs.append(settings_path)
        source = audio_source_path(project_dir, load_tts_settings(project_dir))
        if source is not None:
            inputs.extend([SCRIPTS_DIR / "import_narration.py", source])
    return inputs


def load_tts_settings(project_dir: Path) -> dict[str, str]:
    path = project_dir / "tts-settings.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("tts-settings.json must contain a JSON object")
    unknown = set(payload) - {"voice", "model", "audio_source"}
    if unknown:
        raise ValueError(f"Unknown TTS settings: {', '.join(sorted(unknown))}")
    for key, value in payload.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"TTS setting {key!r} must be a non-empty string")
    if "audio_source" in payload and ("voice" in payload or "model" in payload):
        raise ValueError(
            "TTS setting 'audio_source' cannot be combined with 'voice' or 'model'"
        )
    return payload


def audio_source_path(project_dir: Path, settings: dict[str, str]) -> Path | None:
    """Resolve the optional imported-narration source declared in tts-settings.json."""
    raw = settings.get("audio_source")
    if raw is None:
        return None
    source = Path(raw)
    return source if source.is_absolute() else project_dir / source


def recording_inputs(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    return build_cache.collect_project_inputs(
        project_dir,
        [
            SCRIPTS_DIR / "record_demo.py",
            artifacts / "narration.wav",
            artifacts / "narration-timing.json",
            artifacts / "timing-approval.json",
        ],
    )


def merge_inputs(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    return [
        artifacts / "demo.mp4",
        artifacts / "narration.wav",
        SCRIPTS_DIR / "merge_audio.py",
    ]


def require_nonempty(path: Path, label: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty {label}: {path}")


def measure_narration(audio_path: Path) -> dict:
    duration = validate_demo.probe_audio_duration(audio_path)
    windows = validate_demo.narration_sentence_windows(audio_path)
    if duration is None or windows is None:
        raise RuntimeError(f"Could not measure narration audio: {audio_path}")
    return {
        "duration_seconds": round(duration, 3),
        "sentence_windows": windows,
    }


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
            if source is not None:
                command = [
                    sys.executable,
                    str(SCRIPTS_DIR / "import_narration.py"),
                    "--source",
                    str(source),
                    "--output",
                    str(audio),
                    "--usage-output",
                    str(usage),
                ]
            else:
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
                        command.extend([f"--{option}", settings[option]])
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr or completed.stdout or "TTS failed")
            require_nonempty(audio, "narration audio")
            require_nonempty(usage, "narration usage report")
            timing.write_text(
                json.dumps(measure_narration(audio), indent=2) + "\n",
                encoding="utf-8",
            )
            build_cache.update_cache(project_dir, "tts", inputs)
            result["tts"] = "SUCCESS"
    except Exception as exc:
        result["tts"] = "FAILED"
        result["errors"].append(f"Narration failed: {exc}")
    result["duration"] = round(time.time() - started, 2)
    return result


def timing_paths(project_dir: Path) -> list[Path]:
    artifacts = project_dir / "artifacts"
    return [
        project_dir / "actions.yaml",
        artifacts / "narration.wav",
        artifacts / "narration-timing.json",
    ]


def timing_hashes(project_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(project_dir)): build_cache.calculate_hash(path)
        for path in timing_paths(project_dir)
    }


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
    parser.add_argument("--phase", choices=("narration", "finish"), required=True)
    parser.add_argument("--dirs", nargs="*", help="Directories or glob patterns")
    parser.add_argument("--force", action="store_true", help="Ignore stage caches")
    parser.add_argument(
        "--approve-timing",
        action="store_true",
        help="Approve current narration timing inputs before the finish phase",
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
