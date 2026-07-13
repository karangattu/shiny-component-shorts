#!/usr/bin/env python3
"""Generate a WAV narration file with Gemini 3.1 Flash TTS Preview."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import wave
from pathlib import Path

DEFAULT_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_VOICES = ("Kore", "Erinome", "Charon", "Achird")
INPUT_USD_PER_MILLION_TOKENS = 1.0
OUTPUT_USD_PER_MILLION_TOKENS = 20.0
PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"


def write_wave(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24_000)
        wav_file.writeframes(pcm)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synthesize a text file with Gemini 3.1 Flash TTS Preview."
    )
    parser.add_argument("--input", required=True, type=Path, help="TTS prompt text file")
    parser.add_argument("--output", required=True, type=Path, help="Output .wav file")
    parser.add_argument(
        "--voice",
        help="Gemini prebuilt voice (default: random voice from the curated pool)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini TTS model ID")
    parser.add_argument(
        "--usage-output",
        type=Path,
        help="Usage JSON path (default: <output>.usage.json)",
    )
    return parser.parse_args()


def write_usage_report(
    path: Path,
    *,
    model: str,
    voice: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
    usage_source: str,
) -> float | None:
    pricing_applies = model == DEFAULT_MODEL
    estimated_cost = None
    if pricing_applies:
        estimated_cost = (
            input_tokens * INPUT_USD_PER_MILLION_TOKENS
            + output_tokens * OUTPUT_USD_PER_MILLION_TOKENS
        ) / 1_000_000
    report = {
        "provider": "Google Gemini API",
        "model": model,
        "voice": voice,
        "input_tokens": input_tokens,
        "output_audio_tokens": output_tokens,
        "audio_duration_seconds": round(duration_seconds, 3),
        "usage_source": usage_source,
        "pricing": {
            "currency": "USD",
            "input_usd_per_million_tokens": INPUT_USD_PER_MILLION_TOKENS,
            "output_usd_per_million_audio_tokens": OUTPUT_USD_PER_MILLION_TOKENS,
            "source": PRICING_URL,
            "checked_on": "2026-07-13",
        },
        "estimated_paid_tier_cost_usd": (
            round(estimated_cost, 8) if estimated_cost is not None else None
        ),
        "actual_billed_cost_usd": None,
        "note": (
            "List-price estimate from API usage. Actual billing may be $0 on the "
            "free tier or differ under account-specific pricing. A model override "
            "requires a current model-specific price before estimating cost."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return estimated_cost


def main() -> int:
    args = parse_args()
    voice = args.voice or secrets.choice(DEFAULT_VOICES)

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        print(
            "Missing GEMINI_API_KEY or GOOGLE_API_KEY. Set one in the shell "
            "that launches your agent harness.",
            file=sys.stderr,
        )
        return 2

    if not args.input.is_file():
        print(f"Input file does not exist: {args.input}", file=sys.stderr)
        return 2

    prompt = args.input.read_text(encoding="utf-8").strip()
    if not prompt:
        print(f"Input file is empty: {args.input}", file=sys.stderr)
        return 2

    try:
        from google import genai
    except ImportError:
        print(
            "Missing dependency: install it with `python3 -m pip install google-genai`.",
            file=sys.stderr,
        )
        return 2

    try:
        client = genai.Client()
        interaction = client.interactions.create(
            model=args.model,
            input=prompt,
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        )
        audio = interaction.output_audio
        if audio is None or not audio.data:
            raise RuntimeError("Gemini returned no audio data")
        pcm = base64.b64decode(audio.data) if isinstance(audio.data, str) else audio.data
        write_wave(args.output, pcm)

        usage = getattr(interaction, "usage", None)
        input_tokens = int(getattr(usage, "total_input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "total_output_tokens", 0) or 0)
        duration_seconds = len(pcm) / (24_000 * 2)
        usage_source = "Gemini Interactions API"
        if output_tokens == 0:
            output_tokens = round(duration_seconds * 25)
            usage_source = "audio duration fallback (25 tokens/second)"
        usage_output = args.usage_output or args.output.with_suffix(".usage.json")
        estimated_cost = write_usage_report(
            usage_output,
            model=args.model,
            voice=voice,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=duration_seconds,
            usage_source=usage_source,
        )
    except Exception as exc:
        print(f"Gemini TTS failed: {exc}", file=sys.stderr)
        return 1

    if not args.output.is_file() or args.output.stat().st_size <= 44:
        print(f"Gemini TTS did not create a valid WAV file: {args.output}", file=sys.stderr)
        return 1

    print(f"Generated narration: {args.output}")
    print(f"Voice: {voice}")
    if estimated_cost is None:
        print("Gemini cost estimate unavailable for the overridden model.")
    else:
        print(f"Gemini paid-tier list-price estimate: ${estimated_cost:.6f} USD")
    print(f"Usage report: {usage_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
