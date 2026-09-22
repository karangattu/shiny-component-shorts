#!/usr/bin/env python3
"""Generate narration with a reference voice through local-voice-cloning.

The transcript is synthesized in one request and the engine's audio is used
byte-for-byte. Pause tags become sentence breaks in the text so the model
places its own natural pauses; no audio is ever inserted, trimmed, or joined.
"""

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
PAUSE_TAG_RE = re.compile(r"\[((?:short|medium|long) pause)\]", re.IGNORECASE)

# Pause-tag vocabulary; any tag in this set becomes a line break in the text.
PAUSE_DURATIONS = {"short pause": 0.25, "medium pause": 0.5, "long pause": 1.0}

MIN_SPEAKING_RATE = 0.5
MAX_SPEAKING_RATE = 1.5
DEFAULT_MAX_WPM = 160.0
SILENCE_THRESHOLD_DB = -35.0
MIN_SILENCE_SECONDS = 0.15
OUTPUT_SAMPLE_RATE = 24000


def local_voice_script(prompt: str) -> str:
    """Return one continuous transcript for a single synthesis request.

    Performance tags are stripped. Pause tags become line breaks — the text
    before a pause tag ends with sentence punctuation and the next thought
    starts on a fresh line. The engine places its own short pause at line
    breaks and synthesizes the whole text in one request; phrasing inside
    each line is left to punctuation. No audio is assembled afterwards — the
    engine's output is used as-is.
    """
    if "Transcript:" not in prompt:
        raise ValueError("Narration prompt is missing the Transcript: section")
    transcript = prompt.split("Transcript:", 1)[1]
    lines: list[str] = []
    for token in PAUSE_TAG_RE.split(transcript):
        if token is not None and PAUSE_DURATIONS.get(token.lower()):
            # A pause tag closes the current line; the next text starts fresh.
            if lines and lines[-1] and not lines[-1].endswith((".", "!", "?", ":", "…")):
                lines[-1] += "."
            lines.append("")
        elif token is not None:
            text = _collapse(TAG_RE.sub(" ", token))
            if text:
                if lines and lines[-1]:
                    lines[-1] += " " + text
                else:
                    lines.append(text)
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
              "language": args.language, "engine": args.engine,
              "speed": str(args.speaking_rate), "output_format": "wav"}
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


def build_cli_command(uv: str, args: argparse.Namespace, script: str, output: Path) -> list[str]:
    """Build the local-voice-cloning CLI invocation for the full transcript."""
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
        "--speed",
        str(args.speaking_rate),
        "--output",
        str(output),
    ]
    if args.ref_text:
        command.extend(["--ref-text", args.ref_text])
    return command


class PaceRejected(ValueError):
    """Raised when a narration take is faster than the pace gate allows."""


def silence_seconds(path: Path) -> float | None:
    """Total detected silence in a WAV, or None when ffmpeg is unavailable."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    duration = wave_duration(path)
    completed = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
         "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={MIN_SILENCE_SECONDS}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", completed.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", completed.stderr)]
    total = 0.0
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else duration
        if end > start:
            total += end - start
    return round(total, 3)


def measure_pace(path: Path, words: int) -> dict:
    """Measure delivery pace: overall WPM, articulation rate, pause density."""
    duration = wave_duration(path)
    silence = silence_seconds(path)
    speech = duration - silence if silence is not None else None
    minutes = duration / 60.0
    wpm = words / minutes if minutes > 0 else 0.0
    articulation = words / (speech / 60.0) if speech and speech > 0 else None
    density = silence / duration if silence is not None and duration > 0 else None
    return {
        "words": words,
        "duration_seconds": round(duration, 3),
        "words_per_minute": round(wpm, 1),
        "articulation_words_per_minute": round(articulation, 1) if articulation is not None else None,
        "pause_seconds": silence,
        "pause_density": round(density, 3) if density is not None else None,
    }


def check_pace(path: Path, words: int, max_wpm: float) -> dict:
    """Measure pace and reject takes faster than the gate (`0` disables it)."""
    pace = measure_pace(path, words)
    if max_wpm and pace["words_per_minute"] > max_wpm:
        raise PaceRejected(
            f"Narration pace {pace['words_per_minute']:.0f} WPM exceeds the "
            f"{max_wpm:g} WPM gate. Slow the voice (--speaking-rate below 1.0), "
            "shorten the script, or add pause tags, then regenerate. "
            f"Rejected audio kept at {path} for audition."
        )
    return pace


def _speaking_rate_type(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--speaking-rate must be a number between {MIN_SPEAKING_RATE} and {MAX_SPEAKING_RATE}"
        ) from None
    if not MIN_SPEAKING_RATE <= value <= MAX_SPEAKING_RATE:
        raise argparse.ArgumentTypeError(
            f"--speaking-rate must be between {MIN_SPEAKING_RATE} and {MAX_SPEAKING_RATE}"
        )
    return value


def _max_wpm_type(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError("--max-wpm must be a non-negative number (0 disables the gate)") from None
    if value < 0:
        raise argparse.ArgumentTypeError("--max-wpm must be a non-negative number (0 disables the gate)")
    return value


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
    parser.add_argument("--speaking-rate", type=_speaking_rate_type, default=1.0,
                        help="Engine synthesis rate 0.5-1.5 (default 1.0); values below "
                             "1.0 slow a rushed voice. Never raise it to fit a duration "
                             "target; retime the video to the voice instead")
    parser.add_argument("--max-wpm", type=_max_wpm_type, default=DEFAULT_MAX_WPM,
                        help="Reject narration faster than this words-per-minute "
                             f"(default {DEFAULT_MAX_WPM:g}); 0 disables the gate")
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.api_url:
            synthesize_api(args, script)
        else:
            uv = shutil.which("uv")
            if uv is None:
                print(
                    "Missing dependency: install uv to run local-voice-cloning.",
                    file=sys.stderr,
                )
                return 2
            command = build_cli_command(uv, args, script, args.output)
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
        words = len(script.split())
        pace = check_pace(args.output, words, args.max_wpm)
        duration = pace["duration_seconds"]
    except (OSError, wave.Error, ZeroDivisionError) as exc:
        print(f"Could not read generated WAV file: {exc}", file=sys.stderr)
        return 1
    except PaceRejected as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    report = {
        "provider": "Local voice cloning",
        "model": f"{args.engine} · {args.quality}",
        "voice": str(args.reference),
        "transport": "api" if args.api_url else "cli",
        "speaking_rate": args.speaking_rate,
        "synthesis_requests": 1,
        "audio_modified": False,
        "pace_gate_max_wpm": args.max_wpm,
        **pace,
        "usage_source": "Local Apple MLX generation",
        "estimated_paid_tier_cost_usd": 0,
        "actual_billed_cost_usd": 0,
        "note": "Local compute; no paid TTS API was called. Engine audio used as-is.",
    }
    args.usage_output.parent.mkdir(parents=True, exist_ok=True)
    args.usage_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated local narration: {args.output}")
    print(f"Reference voice: {args.reference}")
    print(f"Usage report: {args.usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
