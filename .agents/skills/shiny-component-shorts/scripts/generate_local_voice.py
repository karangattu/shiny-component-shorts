#!/usr/bin/env python3
"""Generate narration with a reference voice through local-voice-cloning."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
import uuid
import wave
from pathlib import Path

from generate_tts import validate_narration_prompt


TAG_RE = re.compile(r"\[[^\]]+\]")


def local_voice_script(prompt: str) -> str:
    """Return one continuous transcript without forced local-engine pause breaks."""
    if "Transcript:" not in prompt:
        raise ValueError("Narration prompt is missing the Transcript: section")
    transcript = prompt.split("Transcript:", 1)[1].strip()
    # Newlines split local synthesis into separate takes and add fixed silence.
    # Leave phrasing to punctuation instead of forwarding performance cues.
    transcript = TAG_RE.sub(" ", transcript)
    return re.sub(r"\s+", " ", transcript).strip()


def validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("api_url must be a loopback HTTP origin, e.g. http://127.0.0.1:8001")
    return url.rstrip("/")


def synthesize_api(args: argparse.Namespace, script: str) -> None:
    """Send the same multipart contract as local-voice-cloning/src/api.py."""
    origin = validate_api_url(args.api_url)
    boundary = uuid.uuid4().hex
    fields = {"text": script, "ref_text": args.ref_text, "quality": args.quality,
              "language": args.language, "engine": args.engine, "output_format": "wav"}
    body = bytearray()
    for key, value in fields.items():
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f'\r\n\r\n{value}\r\n').encode())
    suffix = args.reference.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]+", suffix):
        raise ValueError("Reference audio must have an audio file extension")
    body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="reference_audio"; '
                 f'filename="reference{suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode())
    body.extend(args.reference.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(origin + "/synthesize", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    # Local samples must not follow a redirect or be sent through an HTTP proxy.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=1800) as response:
        audio = response.read()
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "narration.wav"
        candidate.write_bytes(audio)
        if wave_duration(candidate) <= 0:
            raise ValueError("API returned empty narration")
    args.output.write_bytes(audio)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--usage-output", required=True, type=Path)
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--ref-text", default="")
    parser.add_argument("--quality", choices=("high", "fast"), default="high")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--api-url", help="Running local REST API origin; omit to use CLI")
    parser.add_argument("--engine", choices=("qwen", "omnivoice"), default="qwen")
    parser.add_argument("--speaking-rate", type=float, choices=(1.0,), default=1.0,
                        help="Natural speed only (1.0); retime the video to the voice")
    return parser.parse_args(argv)


def wave_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for name in ("input", "output", "usage_output", "engine_dir", "reference"):
        setattr(args, name, getattr(args, name).expanduser().resolve())
    for path, label in (
        (args.input, "narration prompt"),
        (args.reference, "reference voice"),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            print(f"Missing or empty {label}: {path}", file=sys.stderr)
            return 2
    if not args.api_url and not args.engine_dir.is_dir():
        print(
            f"Local voice cloning directory does not exist: {args.engine_dir}",
            file=sys.stderr,
        )
        return 2

    prompt = args.input.read_text(encoding="utf-8").strip()
    errors = validate_narration_prompt(prompt)
    if errors:
        print(f"Invalid narration prompt in {args.input}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    script = local_voice_script(prompt)
    if not script:
        print("Narration transcript is empty after removing tags.", file=sys.stderr)
        return 2

    uv = shutil.which("uv")
    if uv is None and not args.api_url:
        print(
            "Missing dependency: install uv to run local-voice-cloning.",
            file=sys.stderr,
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        uv,
        "run",
        "--project",
        str(args.engine_dir),
        "python",
        "-m",
        "src.cli",
        "--reference",
        str(args.reference),
        "--text",
        script,
        "--engine",
        args.engine,
        "--quality",
        args.quality,
        "--language",
        args.language,
        "--output",
        str(args.output),
    ]
    if args.ref_text:
        command.extend(["--ref-text", args.ref_text])
    try:
        if args.api_url:
            synthesize_api(args, script)
        else:
            completed = subprocess.run(command, cwd=args.engine_dir, capture_output=True, text=True)
            if completed.returncode != 0:
                print(completed.stderr or completed.stdout or "Local voice cloning failed", file=sys.stderr)
                return completed.returncode or 1
    except (OSError, ValueError, EOFError, wave.Error, subprocess.CalledProcessError) as exc:
        print(f"Local voice cloning failed: {exc}", file=sys.stderr)
        return 1
    if not args.output.is_file() or args.output.stat().st_size <= 44:
        print(
            f"Local voice cloning did not create a valid WAV file: {args.output}",
            file=sys.stderr,
        )
        return 1

    try:
        duration = wave_duration(args.output)
    except (OSError, wave.Error, ZeroDivisionError) as exc:
        print(f"Could not read generated WAV file: {exc}", file=sys.stderr)
        return 1
    report = {
        "provider": "Local voice cloning",
        "model": f"{args.engine} · {args.quality}",
        "voice": str(args.reference),
        "transport": "api" if args.api_url else "cli",
        "speaking_rate": args.speaking_rate,
        "audio_duration_seconds": round(duration, 3),
        "usage_source": "Local Apple MLX generation",
        "estimated_paid_tier_cost_usd": 0,
        "actual_billed_cost_usd": 0,
        "note": "Local compute; no paid TTS API was called.",
    }
    args.usage_output.parent.mkdir(parents=True, exist_ok=True)
    args.usage_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated local narration: {args.output}")
    print(f"Reference voice: {args.reference}")
    print(f"Usage report: {args.usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
