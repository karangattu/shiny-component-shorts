#!/usr/bin/env python3
"""Generate narration with a reference voice through local-voice-cloning.

The transcript is synthesized in one request and the engine's audio is used
byte-for-byte. Named pause tags ([short pause], [medium pause], [long pause])
become sentence breaks in the text so the model places its own natural pauses.
An exact pause tag such as [pause 2s] is the one exception: the transcript is
synthesized in segments and joined with that much digital silence.
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

# Exact-duration pause, e.g. [pause 2s] or [pause 0.5s]. Unlike the named tags it
# inserts real silence between separately synthesized segments.
EXACT_PAUSE_RE = re.compile(r"\[pause\s+(\d+(?:\.\d+)?)\s*s\]", re.IGNORECASE)
MAX_EXACT_PAUSE_SECONDS = 10.0

MIN_SPEAKING_RATE = 0.5
MAX_SPEAKING_RATE = 1.5
DEFAULT_MAX_WPM = 160.0
SILENCE_THRESHOLD_DB = -35.0
MIN_SILENCE_SECONDS = 0.15
OUTPUT_SAMPLE_RATE = 24000
# The engine's REST service. Used whenever it answers, so takes skip the CLI's
# per-call model load (about 10 s each).
DEFAULT_API_URL = "http://127.0.0.1:8001"
# Only these engines change speed natively; the others time-stretch finished
# audio, which the skill never allows. Shorten the script instead.
NATIVE_SPEED_ENGINES = frozenset({"omnivoice"})


def speed_problem(engine: str, speaking_rate: float) -> str | None:
    if engine in NATIVE_SPEED_ENGINES or speaking_rate == 1.0:
        return None
    return (
        f"speaking_rate {speaking_rate:g} would time-stretch {engine} audio after "
        "synthesis. Keep speaking_rate at 1.0 for this engine; if the voice runs "
        "fast, add pause tags or split long sentences so the engine pauses more, "
        "then shorten the script if it runs long, and regenerate."
    )


def sidecar_transcript(reference: Path) -> str:
    """The corrected transcript saved beside a voice sample (`<name>.json`)."""
    sidecar = reference.with_suffix(".json")
    if not sidecar.is_file():
        return ""
    try:
        return str(json.loads(sidecar.read_text(encoding="utf-8")).get("transcript", "")).strip()
    except (OSError, ValueError, AttributeError):
        return ""


def _local_opener() -> urllib.request.OpenerDirector:
    # Local samples must not follow a redirect or be sent through an HTTP proxy.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def api_is_up(url: str, timeout: float = 1.0) -> bool:
    try:
        with _local_opener().open(validate_api_url(url) + "/health", timeout=timeout) as response:
            return json.loads(response.read()).get("status") == "ok"
    except (OSError, ValueError):
        return False


def resolve_api_url(explicit: str | None, transport: str = "auto") -> str | None:
    """The API origin to use, or None for the CLI."""
    if transport == "cli":
        return None
    if explicit:
        return explicit
    if transport == "api":
        return DEFAULT_API_URL
    return DEFAULT_API_URL if api_is_up(DEFAULT_API_URL) else None


def warm_up(api_url: str, engine: str, quality: str, timeout: float = 900) -> dict:
    """Load the engine's models once, so no take pays the load time."""
    body = urllib.parse.urlencode({"engine": engine, "quality": quality}).encode()
    request = urllib.request.Request(
        validate_api_url(api_url) + "/warmup", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with _local_opener().open(request, timeout=timeout) as response:
        return json.loads(response.read())


def local_voice_script(prompt: str) -> str:
    """Return the spoken text as one script (exact pauses count as line breaks).

    Performance tags are stripped. Named pause tags become line breaks — the
    text before a pause tag ends with sentence punctuation and the next
    thought starts on a fresh line. The engine places its own short pause at
    line breaks; phrasing inside each line is left to punctuation.
    """
    return "\n".join(part for part in local_voice_parts(prompt) if isinstance(part, str))


def local_voice_parts(prompt: str) -> list[str | float]:
    """Split the transcript at exact `[pause Ns]` tags.

    Returns text segments and pause lengths in seconds, in order. Without an
    exact pause tag the result is one text segment, synthesized in one request.
    """
    if "Transcript:" not in prompt:
        raise ValueError("Narration prompt is missing the Transcript: section")
    transcript = prompt.split("Transcript:", 1)[1]
    parts: list[str | float] = []
    tokens = EXACT_PAUSE_RE.split(transcript)
    for index, token in enumerate(tokens):
        if index % 2:
            seconds = float(token)
            if seconds > MAX_EXACT_PAUSE_SECONDS:
                raise ValueError(
                    f"[pause {token}s] is longer than {MAX_EXACT_PAUSE_SECONDS:g} seconds"
                )
            if parts and isinstance(parts[-1], float):
                parts[-1] += seconds
            else:
                parts.append(seconds)
            continue
        text = _named_pause_lines(token)
        if index:
            # Text after an exact pause often starts with a stray "." or ",".
            text = text.lstrip(" .,;")
        if not re.search(r"\w", text):
            continue
        if parts and isinstance(parts[-1], float) and len(parts) > 1:
            previous = parts[-2]
            if isinstance(previous, str):
                parts[-2] = _close_sentence(previous)
        parts.append(text)
    return parts


def _close_sentence(text: str) -> str:
    """End the text before a pause with sentence punctuation."""
    text = text.rstrip(" ,;")
    return text if text.endswith((".", "!", "?", ":", "…")) else text + "."


def _named_pause_lines(transcript: str) -> str:
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
    return "\n".join(line for line in lines if line)


def join_with_silence(segments: list[Path | float], output: Path) -> None:
    """Concatenate WAV files and exact silences (seconds) into one WAV."""
    params = None
    frames = bytearray()
    for segment in segments:
        if isinstance(segment, float):
            if params is None:
                raise ValueError("Leading pause needs audio to match; place it after some text")
            count = round(segment * params.framerate)
            frames.extend(b"\x00" * count * params.sampwidth * params.nchannels)
            continue
        with wave.open(str(segment), "rb") as wav_file:
            if params is None:
                params = wav_file.getparams()
            elif (wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()) != (
                params.framerate, params.sampwidth, params.nchannels
            ):
                raise ValueError("Segments have different audio formats")
            frames.extend(wav_file.readframes(wav_file.getnframes()))
    if params is None:
        raise ValueError("No audio to join")
    with wave.open(str(output), "wb") as out:
        out.setparams(params)
        out.writeframes(bytes(frames))


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("api_url must be a loopback HTTP origin, e.g. http://127.0.0.1:8001")
    return url.rstrip("/")


def synthesize_api(args: argparse.Namespace, script: str, output: Path | None = None) -> None:
    """Send the same multipart contract as local-voice-cloning/src/api.py."""
    origin = validate_api_url(args.api_url)
    boundary = uuid.uuid4().hex
    ref_text = args.ref_text or sidecar_transcript(args.reference)
    fields = {"text": script, "ref_text": ref_text, "quality": args.quality,
              "language": args.language, "engine": args.engine,
              "speed": str(args.speaking_rate), "output_format": "wav"}
    body = bytearray()
    for key, value in fields.items():
        body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"'
                     f'\r\n\r\n{value}\r\n').encode())
    suffix = args.reference.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]+", suffix):
        raise ValueError("Reference audio must have an audio file extension")
    # The real name lets the service find the saved voice's sidecar transcript.
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", args.reference.stem) or "reference"
    body.extend((f'--{boundary}\r\nContent-Disposition: form-data; name="reference_audio"; '
                 f'filename="{stem}{suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode())
    body.extend(args.reference.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(origin + "/synthesize", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with _local_opener().open(request, timeout=1800) as response:
        audio = response.read()
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "narration.wav"
        candidate.write_bytes(audio)
        if wave_duration(candidate) <= 0:
            raise ValueError("API returned empty narration")
    (output or args.output).write_bytes(audio)


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
    ref_text = args.ref_text or sidecar_transcript(args.reference)
    if ref_text:
        command.extend(["--ref-text", ref_text])
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
            f"{max_wpm:g} WPM gate. Add pause tags or split long sentences so the "
            "engine pauses more, shorten the script if it runs long, and regenerate "
            "(never time-stretch the audio). "
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
    parser.add_argument("--editorial", action="store_true", help="Allow detailed editorial narration without component-short word/tag quotas")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--usage-output", required=True, type=Path)
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--ref-text", default="")
    parser.add_argument("--quality", choices=("high", "fast"), default="high")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--api-url", help=f"Local REST API origin; by default {DEFAULT_API_URL} "
                        "is used when it answers, else the CLI")
    parser.add_argument("--transport", choices=("auto", "api", "cli"), default="auto",
                        help="auto (default) prefers a running API over the CLI")
    parser.add_argument("--engine", choices=("qwen", "omnivoice"), default="qwen")
    parser.add_argument("--speaking-rate", type=_speaking_rate_type, default=1.0,
                        help="Native synthesis rate 0.5-1.5 for omnivoice (default 1.0). "
                             "Qwen time-stretches finished audio, so it must stay at 1.0; "
                             "shorten the script to fix a rushed voice")
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
    problem = speed_problem(args.engine, args.speaking_rate)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    args.api_url = resolve_api_url(args.api_url, args.transport)
    if not args.api_url and not args.engine_dir.is_dir():
        print(
            f"Local voice cloning directory does not exist: {args.engine_dir}",
            file=sys.stderr,
        )
        return 2

    prompt = args.input.read_text(encoding="utf-8").strip()
    errors = validate_narration_prompt(prompt, editorial=args.editorial)
    if errors:
        print(f"Invalid narration prompt in {args.input}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    try:
        parts = local_voice_parts(prompt)
    except ValueError as exc:
        print(f"Invalid narration prompt in {args.input}: {exc}", file=sys.stderr)
        return 2
    script = "\n".join(part for part in parts if isinstance(part, str))
    if not script:
        print("Narration transcript is empty after removing tags.", file=sys.stderr)
        return 2
    if isinstance(parts[0], float):
        print("A leading [pause Ns] has no audio to follow; start with spoken text.", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    texts = [part for part in parts if isinstance(part, str)]
    exact_pauses = len(texts) != len(parts)
    try:
        uv = None
        if not args.api_url:
            uv = shutil.which("uv")
            if uv is None:
                print(
                    "Missing dependency: install uv to run local-voice-cloning.",
                    file=sys.stderr,
                )
                return 2

        def synthesize(text: str, output: Path) -> int:
            if args.api_url:
                synthesize_api(args, text, output)
                return 0
            if uv is None:
                raise ValueError("uv is required for the CLI transport")
            command = build_cli_command(uv, args, text, output)
            completed = subprocess.run(command, cwd=args.engine_dir, capture_output=True, text=True)
            if completed.returncode != 0:
                print(completed.stderr or completed.stdout or "Local voice cloning failed", file=sys.stderr)
                return completed.returncode or 1
            return 0

        if not exact_pauses:
            status = synthesize(script, args.output)
            if status:
                return status
        else:
            with tempfile.TemporaryDirectory() as directory:
                joined: list[Path | float] = []
                for index, part in enumerate(parts):
                    if isinstance(part, float):
                        joined.append(part)
                        continue
                    segment = Path(directory) / f"segment-{index}.wav"
                    status = synthesize(part, segment)
                    if status:
                        return status
                    joined.append(segment)
                join_with_silence(joined, args.output)
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
        "reference_transcript": (
            "given" if args.ref_text
            else "sidecar" if sidecar_transcript(args.reference)
            else "engine transcription"
        ),
        "speaking_rate": args.speaking_rate,
        "synthesis_requests": len(texts),
        "exact_pause_seconds": round(sum(p for p in parts if isinstance(p, float)), 3),
        "audio_modified": exact_pauses,
        "pace_gate_max_wpm": args.max_wpm,
        **pace,
        "usage_source": "Local Apple MLX generation",
        "estimated_paid_tier_cost_usd": 0,
        "actual_billed_cost_usd": 0,
        "note": "Local compute; no paid TTS API was called. "
        + ("Engine audio joined with exact silences." if exact_pauses else "Engine audio used as-is."),
    }
    args.usage_output.parent.mkdir(parents=True, exist_ok=True)
    args.usage_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated local narration: {args.output}")
    print(f"Reference voice: {args.reference}")
    print(f"Usage report: {args.usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
