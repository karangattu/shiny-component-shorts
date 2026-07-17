#!/usr/bin/env python3
"""Batch process Shiny component short videos with parallel execution and caching."""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import os
import subprocess
import sys
import time
from pathlib import Path

# Add the scripts directory to path to import build_cache
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import build_cache

BASE_PORT = 8000
PORT_RANGE_SIZE = 100


def start_port_for(project_index: int) -> int:
    port = BASE_PORT + project_index * PORT_RANGE_SIZE
    if port + PORT_RANGE_SIZE - 1 > 65535:
        raise ValueError("Too many projects to assign non-overlapping port ranges")
    return port


def has_failures(results: list[dict]) -> bool:
    failed_states = {"FAILED", "ERROR", "BLOCKED"}
    return any(
        result["errors"]
        or any(
            result[step] in failed_states
            for step in ("record", "tts", "merge", "validate")
        )
        for result in results
    )


def discover_projects(base_dir: Path, patterns: list[str] | None = None) -> list[Path]:
    """Find directories containing app.py/app.R and actions.yaml."""
    projects = []
    
    # Common directories to ignore
    ignored_dirs = {".git", ".github", ".venv", ".agents", ".claude", "tests", "assets", "artifacts"}

    # If specific glob patterns are provided, match folders in base_dir
    if patterns:
        for pattern in patterns:
            # Handle direct directory paths or globs
            matched = False
            for path in base_dir.glob(pattern):
                if path.is_dir():
                    if (path / "actions.yaml").is_file() and ((path / "app.py").is_file() or (path / "app.R").is_file()):
                        projects.append(path)
                        matched = True
            if not matched:
                # Try relative to CWD if not found in base_dir
                path = Path(pattern).resolve()
                if path.is_dir() and (path / "actions.yaml").is_file() and ((path / "app.py").is_file() or (path / "app.R").is_file()):
                    projects.append(path)
        return sorted(list(set(projects)))

    # Otherwise, auto-discover in base_dir
    for root, dirs, files in os.walk(base_dir):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        root_path = Path(root)
        if (root_path / "actions.yaml").is_file() and ((root_path / "app.py").is_file() or (root_path / "app.R").is_file()):
            projects.append(root_path)
            # Don't descend further into a project directory
            dirs.clear()

    return sorted(projects)


def process_project(
    project_dir: Path,
    start_port: int,
    tts_enabled: bool,
    merge_enabled: bool,
    force: bool,
) -> dict:
    """Process a single project (record, generate TTS, merge, validate)."""
    start_time = time.time()
    result = {
        "name": project_dir.name,
        "record": "SKIPPED",
        "tts": "SKIPPED",
        "merge": "SKIPPED",
        "validate": "SKIPPED",
        "errors": [],
        "duration": 0.0,
    }

    # Determine app type
    if (project_dir / "app.py").is_file():
        app_type = "python"
    elif (project_dir / "app.R").is_file():
        app_type = "r"
    else:
        result["errors"].append("No app.py or app.R found")
        result["validate"] = "FAILED"
        return result

    # 1. Recording Step
    actions_yaml = project_dir / "actions.yaml"
    demo_mp4 = project_dir / "artifacts" / "demo.mp4"
    recording_json = project_dir / "artifacts" / "recording.json"
    final_png = project_dir / "artifacts" / "final.png"

    rec_inputs = build_cache.collect_project_inputs(
        project_dir, [SCRIPTS_DIR / "record_demo.py"]
    )
    rec_outputs = [demo_mp4, recording_json, final_png]

    try:
        # Check cache
        if not force and build_cache.check_cache(project_dir, "recording", rec_inputs, rec_outputs):
            result["record"] = "CACHED"
        else:
            cmd = [
                sys.executable,
                str(SCRIPTS_DIR / "record_demo.py"),
                "--project-dir", str(project_dir),
                "--app-type", app_type,
                "--actions", str(actions_yaml),
                "--port", str(start_port),
            ]
            
            # Run record_demo as a subprocess
            proc_res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            if proc_res.returncode == 0:
                result["record"] = "SUCCESS"
                build_cache.update_cache(project_dir, "recording", rec_inputs)
            else:
                result["record"] = "FAILED"
                result["errors"].append(f"Recording failed:\n{proc_res.stderr or proc_res.stdout}")
                result["validate"] = "FAILED"
                return result
    except Exception as exc:
        result["record"] = "FAILED"
        result["errors"].append(f"Recording error: {exc}")
        result["validate"] = "FAILED"
        return result

    # 2. TTS Generation Step
    narration_txt = project_dir / "artifacts" / "narration.txt"
    narration_wav = project_dir / "artifacts" / "narration.wav"
    narration_json = project_dir / "artifacts" / "narration.usage.json"

    if tts_enabled and narration_txt.is_file():
        tts_inputs = [narration_txt, SCRIPTS_DIR / "generate_tts.py"]
        tts_outputs = [narration_wav, narration_json]
        
        try:
            if not force and build_cache.check_cache(project_dir, "tts", tts_inputs, tts_outputs):
                result["tts"] = "CACHED"
            else:
                cmd = [
                    sys.executable,
                    str(SCRIPTS_DIR / "generate_tts.py"),
                    "--input", str(narration_txt),
                    "--output", str(narration_wav),
                    "--usage-output", str(narration_json),
                ]
                proc_res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if proc_res.returncode == 0:
                    result["tts"] = "SUCCESS"
                    build_cache.update_cache(project_dir, "tts", tts_inputs)
                else:
                    result["tts"] = "FAILED"
                    result["errors"].append(f"TTS generation failed:\n{proc_res.stderr or proc_res.stdout}")
        except Exception as exc:
            result["tts"] = "FAILED"
            result["errors"].append(f"TTS generation error: {exc}")
    elif tts_enabled:
        result["tts"] = "FAILED"
        result["errors"].append("TTS requested but artifacts/narration.txt is missing")

    # 3. Audio/Video Merge Step
    final_with_audio = project_dir / "artifacts" / "final_with_audio.mp4"
    tts_ready = not tts_enabled or result["tts"] in ("SUCCESS", "CACHED")
    if merge_enabled and not tts_ready:
        result["merge"] = "BLOCKED"
    elif merge_enabled and (not narration_wav.is_file() or narration_wav.stat().st_size == 0):
        result["merge"] = "FAILED"
        result["errors"].append("Merge requested but artifacts/narration.wav is missing or empty")
    elif merge_enabled:
        merge_inputs = [demo_mp4, narration_wav, SCRIPTS_DIR / "batch_process.py"]
        merge_outputs = [final_with_audio]
        
        try:
            if not force and build_cache.check_cache(project_dir, "merge", merge_inputs, merge_outputs):
                result["merge"] = "CACHED"
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(demo_mp4),
                    "-i", str(narration_wav),
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,apad",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(final_with_audio)
                ]
                proc_res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )
                if proc_res.returncode == 0:
                    result["merge"] = "SUCCESS"
                    build_cache.update_cache(project_dir, "merge", merge_inputs)
                else:
                    result["merge"] = "FAILED"
                    result["errors"].append(f"Merge failed:\n{proc_res.stderr or proc_res.stdout}")
        except Exception as exc:
            result["merge"] = "FAILED"
            result["errors"].append(f"Merge error: {exc}")

    # 4. Validation Step
    try:
        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "validate_demo.py"),
            "--project-dir", str(project_dir),
        ]
        if merge_enabled:
            cmd.append("--require-audio")
            
        proc_res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if proc_res.returncode == 0:
            result["validate"] = "PASSED"
        else:
            result["validate"] = "FAILED"
            result["errors"].append(f"Validation failed:\n{proc_res.stdout or proc_res.stderr}")
    except Exception as exc:
        result["validate"] = "FAILED"
        result["errors"].append(f"Validation launch error: {exc}")

    result["duration"] = round(time.time() - start_time, 2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch process Shiny component short videos in the background.")
    parser.add_argument("--dirs", nargs="*", help="List of directory names or glob patterns to process")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of concurrent workers (default: 2)")
    parser.add_argument("--tts", action="store_true", help="Generate Gemini TTS audio")
    parser.add_argument("--merge", action="store_true", help="Merge audio and video using FFmpeg")
    parser.add_argument("--force", action="store_true", help="Ignore build cache and rebuild everything")
    
    args = parser.parse_args()
    base_dir = Path.cwd()

    projects = discover_projects(base_dir, args.dirs)
    if not projects:
        print("No project directories discovered.")
        return 0
    try:
        start_ports = [start_port_for(index) for index in range(len(projects))]
    except ValueError as exc:
        print(exc)
        return 2

    print(f"Discovered {len(projects)} projects:")
    for proj in projects:
        print(f" - {proj.relative_to(base_dir)}")
    print(f"Starting batch execution with concurrency={args.concurrency}...\n")

    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {}
        for project_dir, start_port in zip(projects, start_ports):
            fut = executor.submit(
                process_project,
                project_dir=project_dir,
                start_port=start_port,
                tts_enabled=args.tts,
                merge_enabled=args.merge,
                force=args.force,
            )
            futures[fut] = project_dir

        for fut in concurrent.futures.as_completed(futures):
            project_dir = futures[fut]
            try:
                res = fut.result()
                results.append(res)
                status_icon = "✅" if res["validate"] == "PASSED" and not res["errors"] else "❌"
                print(f"{status_icon} Processed {res['name']} ({res['duration']}s) - Record: {res['record']}, TTS: {res['tts']}, Merge: {res['merge']}, Validation: {res['validate']}")
                if res["errors"]:
                    print(f"   Errors for {res['name']}:")
                    for err in res["errors"]:
                        print(f"     * {err}")
            except Exception as exc:
                print(f"❌ Worker crashed for {project_dir.name}: {exc}")
                results.append({
                    "name": project_dir.name,
                    "record": "ERROR",
                    "tts": "ERROR",
                    "merge": "ERROR",
                    "validate": "FAILED",
                    "errors": [str(exc)],
                    "duration": 0.0,
                })

    # Summary Report
    print("\n" + "="*80)
    print("BATCH PROCESSING SUMMARY REPORT")
    print("="*80)
    print(f"{'Project Name':<28} | {'Record':<8} | {'TTS':<8} | {'Merge':<8} | {'Validate':<8} | {'Time (s)':<8}")
    print("-"*80)
    
    passed_count = 0
    for res in sorted(results, key=lambda x: x["name"]):
        if res["validate"] == "PASSED":
            passed_count += 1
        print(f"{res['name']:<28} | {res['record']:<8} | {res['tts']:<8} | {res['merge']:<8} | {res['validate']:<8} | {res['duration']:<8}")
        
    print("-"*80)
    print(f"Total: {len(results)} projects | Passed Validation: {passed_count}/{len(results)}")
    print("="*80)

    if has_failures(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
