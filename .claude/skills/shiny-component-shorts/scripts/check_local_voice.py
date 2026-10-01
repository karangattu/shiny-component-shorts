#!/usr/bin/env python3
"""Probe the local voice cloning service before spending a takes run on it.

Checks reachability, engine settings, saved voices, whether `speed` is
honored, and whether transcription works — the failures that otherwise show
up as one opaque rejected take at a time.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

DEFAULT_API_URL = "http://127.0.0.1:8001"
PROBE_TEXT = "Speed check one two three four five six seven."


def request_json(url: str, timeout: float = 15.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def request_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, Path],
    timeout: float = 600.0,
) -> tuple[dict[str, str], bytes]:
    """POST multipart form data; raise with the server's message on failure."""
    boundary = secrets.token_hex(16)
    body = bytearray()
    for name, value in fields.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"\r\n\r\n{value}\r\n'
        ).encode()
    for name, path in files.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"; filename="{path.name}"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(  # noqa: S310
        url,
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}") from exc


def sidecar_transcript(reference: Path) -> str:
    sidecar = reference.with_suffix(".json")
    if not sidecar.is_file():
        return ""
    try:
        return str(json.loads(sidecar.read_text(encoding="utf-8")).get("transcript", ""))
    except (OSError, json.JSONDecodeError):
        return ""


def synthesize_seconds(
    api_url: str, reference: Path, engine: str, quality: str, speed: float
) -> float:
    fields = {
        "text": PROBE_TEXT,
        "ref_text": sidecar_transcript(reference),
        "quality": quality,
        "language": "English",
        "engine": engine,
        "speed": str(speed),
        "output_format": "wav",
    }
    headers, audio = request_multipart(
        f"{api_url}/synthesize", fields, {"reference_audio": reference}
    )
    if len(audio) < 1000:
        raise RuntimeError(f"probe synthesis returned only {len(audio)} bytes")
    return float(headers.get("x-duration-seconds", 0.0))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--engine-dir", type=Path, help="local-voice-cloning checkout")
    parser.add_argument("--saved-voice", default="karan")
    parser.add_argument("--engine", default="qwen")
    parser.add_argument("--quality", default="high")
    parser.add_argument("--skip-speed", action="store_true", help="Skip the two probe syntheses")
    args = parser.parse_args(argv)

    engine_dir = args.engine_dir or (SCRIPTS_DIR.parents[4] / "local-voice-cloning")
    reference = engine_dir / "voice_samples" / f"{args.saved_voice}.wav"
    warnings: list[str] = []

    try:
        health = request_json(f"{args.api_url}/health")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"FAIL: no service at {args.api_url} ({exc}); start it with "
              "`uv run uvicorn src.api:app --host 127.0.0.1 --port 8001`")
        return 1
    print(f"service: {args.api_url} status={health.get('status')} "
          f"model_loaded={health.get('model_loaded')}")
    if "version" not in health:
        warnings.append(
            "health has no version field: the service predates versioned /health and "
            "may be running stale code; restart it"
        )
    else:
        print(f"  version: {health.get('version')}")
    capabilities = health.get("capabilities")
    if capabilities:
        print(f"  capabilities: {capabilities}")

    try:
        info = request_json(f"{args.api_url}/info")
        engines = ", ".join(info.get("engines", {})) or "unknown"
        print(f"  engines: {engines} (probing {args.engine})")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        warnings.append(f"/info failed: {exc}")

    if not reference.is_file():
        print(f"FAIL: saved voice not found: {reference}")
        return 1
    transcript = sidecar_transcript(reference)
    voices = sorted((engine_dir / "voice_samples").glob("*.wav"))
    print(f"saved voices: {', '.join(path.stem for path in voices) or 'none'}")
    if not transcript:
        warnings.append(
            f"no sidecar transcript for {reference.name}; write "
            f"{reference.with_suffix('.json').name} or set reference_text in tts-settings.json "
            "so synthesis never depends on the server's transcription"
        )
    else:
        print(f"  sidecar transcript for {reference.stem}: {len(transcript.split())} words")

    if not args.skip_speed:
        try:
            normal = synthesize_seconds(args.api_url, reference, args.engine, args.quality, 1.0)
            slowed = synthesize_seconds(args.api_url, reference, args.engine, args.quality, 0.5)
            print(f"speed probe: {PROBE_TEXT!r} -> {normal:.2f}s at 1.0, {slowed:.2f}s at 0.5")
            if slowed <= normal * 1.25:
                warnings.append(
                    "speed is not honored (0.5 produced no longer audio): speaking_rate "
                    "will not slow a rushed take; restart the service with current code"
                )
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"FAIL: synthesis probe failed: {exc}")
            return 1

    try:
        request_multipart(
            f"{args.api_url}/transcribe", {}, {"reference_audio": reference}
        )
        print("transcribe: ok")
    except (RuntimeError, ValueError, OSError) as exc:
        warnings.append(
            f"transcription is unavailable ({str(exc)[:120]}); pass reference_text or "
            "use a sidecar transcript instead"
        )

    for warning in warnings:
        print(f"warn: {warning}")
    print("doctor: OK" if not warnings else f"doctor: OK with {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
