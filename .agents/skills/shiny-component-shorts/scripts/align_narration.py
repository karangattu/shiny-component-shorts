#!/usr/bin/env python3
"""Word-level narration timing, transcript checks, and take scoring.

Transcribes `artifacts/narration.wav` locally with faster-whisper word
timestamps, aligns the recognized words to the `Transcript:` in
`narration.txt`, and writes `artifacts/narration-timing.json` with:

- `words`: every transcript word with its spoken start and end time,
- `sentences` / `sentence_windows`: per-sentence spans from those words,
- `transcript_check`: word error rate, every expected-vs-heard difference,
  and any non-speech vocalization the recognizer heard.

These measurements replace "listen and guess" steps: `cue` actions in
`actions.yaml` resolve spoken phrases against `words`, and the validator
checks each cued reaction against the moment its phrase is spoken.

`--takes` scores every raw take in `artifacts/narration-takes/` the same way
(transcript accuracy, pace, longest pause, peak) and ranks them.

Times are narration seconds. The merged video starts the narration
`NARRATION_OFFSET_SECONDS` in, so add that offset to compare with video time.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

# The merge delays narration by this lead-in so the first word never lands on
# frame zero; the recorder and validator add it when converting to video time.
NARRATION_OFFSET_SECONDS = 0.15

DEFAULT_MODEL = os.getenv("SHORTS_ALIGN_MODEL", "base.en")
MAX_WORD_ERROR_RATE = 0.25
WARN_WORD_ERROR_RATE = 0.10
TARGET_WPM = 150.0

TAG_RE = re.compile(r"\[[^\]]+\]")
VOCALIZATION_RE = re.compile(
    r"\b(?:laugh\w*|haha\w*|hehe\w*|giggl\w*|chuckl\w*|sigh\w*|gasp\w*|cough\w*)\b"
    r"|[\(\[][^\)\]]*[\)\]]",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
ONES: tuple[str, ...] = tuple(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
)
TENS: tuple[str, ...] = tuple(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
)

_MODEL_CACHE: dict[str, object] = {}


def number_words(value: int) -> list[str]:
    if value < 20:
        return [ONES[value]]
    if value < 100:
        return [TENS[value // 10]] + ([ONES[value % 10]] if value % 10 else [])
    if value < 1000:
        rest = number_words(value % 100) if value % 100 else []
        return [ONES[value // 100], "hundred"] + rest
    if value < 1_000_000:
        rest = number_words(value % 1000) if value % 1000 else []
        return number_words(value // 1000) + ["thousand"] + rest
    return [str(value)]


def normalize_tokens(text: str) -> list[str]:
    """Lowercase spoken tokens with digits spelled out, for fair comparison."""
    text = text.lower().replace("%", " percent ").replace("&", " and ")
    text = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    text = re.sub(r"(\d)\.(\d)", r"\1 point \2", text)
    tokens: list[str] = []
    for raw in re.split(r"[\s\-–—/_.]+", text):
        cleaned = re.sub(r"[^\w]", "", raw.replace("'", "").replace("’", ""))
        for piece in re.findall(r"\d+|[^\W\d_]+", cleaned):
            tokens.extend(number_words(int(piece)) if piece.isdigit() else [piece])
    return tokens


def spoken_transcript(prompt: str) -> str:
    if "Transcript:" not in prompt:
        raise ValueError("narration.txt is missing the Transcript: section")
    transcript = prompt.split("Transcript:", 1)[1]
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", transcript)).strip()


def transcript_sentences(spoken: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(spoken) if part.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def recognize(audio: Path, model_name: str = DEFAULT_MODEL) -> tuple[list[dict], str]:
    """Recognized words with timestamps, plus the raw recognized text."""
    try:
        from faster_whisper import WhisperModel  # pyrefly: ignore[missing-import]
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "Word timing needs faster-whisper: python -m pip install -r requirements.txt"
        ) from exc
    model = _MODEL_CACHE.get(model_name)
    if model is None:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        _MODEL_CACHE[model_name] = model
    segments, _ = model.transcribe(  # type: ignore[attr-defined]
        str(audio),
        word_timestamps=True,
        beam_size=5,
        vad_filter=False,
        # No prompt or hotwords: both leak words into the opening, and the
        # transcript check must hear only what was actually said.
    )
    words: list[dict] = []
    texts: list[str] = []
    for segment in segments:
        texts.append(segment.text)
        for word in segment.words or []:
            words.append(
                {"word": word.word.strip(), "start": float(word.start), "end": float(word.end)}
            )
    return words, " ".join(text.strip() for text in texts).strip()


def expand_heard(heard: list[dict]) -> list[dict]:
    """Split each recognized word into normalized tokens sharing its span."""
    tokens: list[dict] = []
    for word in heard:
        pieces = normalize_tokens(word["word"])
        if not pieces:
            continue
        step = (word["end"] - word["start"]) / len(pieces)
        for index, piece in enumerate(pieces):
            tokens.append(
                {
                    "token": piece,
                    "start": word["start"] + step * index,
                    "end": word["start"] + step * (index + 1),
                }
            )
    return tokens


def align(spoken: str, heard: list[dict], duration: float) -> dict:
    """Time every transcript token from the recognizer's words."""
    sentences = transcript_sentences(spoken)
    expected: list[tuple[str, int]] = [
        (token, index)
        for index, sentence in enumerate(sentences)
        for token in normalize_tokens(sentence)
    ]
    if not expected:
        raise ValueError("The transcript has no spoken words")
    hyp = expand_heard(heard)
    ref = [token for token, _ in expected]
    times: list[tuple[float, float] | None] = [None] * len(ref)
    matched = [False] * len(ref)
    differences: list[dict] = []
    edits = 0
    matcher = difflib.SequenceMatcher(a=ref, b=[t["token"] for t in hyp], autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                token = hyp[j1 + offset]
                times[i1 + offset] = (token["start"], token["end"])
                matched[i1 + offset] = True
            continue
        edits += max(i2 - i1, j2 - j1)
        at = hyp[j1]["start"] if j1 < len(hyp) else (hyp[-1]["end"] if hyp else 0.0)
        differences.append(
            {
                "expected": " ".join(ref[i1:i2]),
                "heard": " ".join(t["token"] for t in hyp[j1:j2]),
                "at": round(at, 2),
            }
        )
        if i2 > i1 and j2 > j1:
            # Spread the heard span across the expected words it replaced.
            span_start, span_end = hyp[j1]["start"], hyp[j2 - 1]["end"]
            step = (span_end - span_start) / (i2 - i1)
            for offset in range(i2 - i1):
                times[i1 + offset] = (
                    span_start + step * offset,
                    span_start + step * (offset + 1),
                )
    _interpolate(times, duration)
    words = [
        {
            "word": ref[index],
            "sentence": expected[index][1],
            "start": round(times[index][0], 3),  # type: ignore[index]
            "end": round(times[index][1], 3),  # type: ignore[index]
            "matched": matched[index],
        }
        for index in range(len(ref))
    ]
    spans: list[dict] = []
    for index, text in enumerate(sentences):
        members = [word for word in words if word["sentence"] == index]
        if members:
            spans.append(
                {
                    "text": text,
                    "start": round(members[0]["start"], 2),
                    "end": round(members[-1]["end"], 2),
                }
            )
    return {
        "words": words,
        "sentences": spans,
        "word_error_rate": round(edits / len(ref), 3),
        "differences": differences,
    }


def _interpolate(times: list[tuple[float, float] | None], duration: float) -> None:
    """Give unheard words evenly spaced times between their heard neighbours."""
    index = 0
    while index < len(times):
        if times[index] is not None:
            index += 1
            continue
        gap_end = index
        while gap_end < len(times) and times[gap_end] is None:
            gap_end += 1
        left = times[index - 1][1] if index > 0 else 0.0  # type: ignore[index]
        right = times[gap_end][0] if gap_end < len(times) else duration  # type: ignore[index]
        step = max(0.0, right - left) / (gap_end - index)
        for offset in range(gap_end - index):
            times[index + offset] = (left + step * offset, left + step * (offset + 1))
        index = gap_end


def pace(words: list[dict], word_count: int) -> dict:
    if not words:
        return {"words_per_minute": None, "longest_pause_seconds": None}
    speech = words[-1]["end"] - words[0]["start"]
    gaps = [b["start"] - a["end"] for a, b in zip(words, words[1:])]
    return {
        "words_per_minute": round(word_count / (speech / 60.0), 1) if speech > 0 else None,
        "longest_pause_seconds": round(max(gaps, default=0.0), 2),
        "speech_seconds": round(speech, 2),
    }


def peak_dbfs(audio: Path) -> float | None:
    if shutil.which("ffmpeg") is None:
        return None
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"max_volume: (-?[\d.]+) dB", completed.stderr)
    return float(match.group(1)) if match else None


def measure(audio: Path, prompt: str, model_name: str = DEFAULT_MODEL) -> dict:
    """Full timing report for one narration WAV."""
    spoken = spoken_transcript(prompt)
    duration = wav_duration(audio)
    heard, heard_text = recognize(audio, model_name)
    aligned = align(spoken, heard, duration)
    vocalizations = sorted({m.group(0) for m in VOCALIZATION_RE.finditer(heard_text)})
    word_count = len(re.findall(r"\b[\w’'-]+\b", spoken))
    return {
        "audio_sha256": sha256(audio),
        "duration_seconds": round(duration, 3),
        "alignment_method": f"faster-whisper word timestamps ({model_name})",
        "narration_offset_seconds": NARRATION_OFFSET_SECONDS,
        "words": aligned["words"],
        "sentences": aligned["sentences"],
        "sentence_windows": [
            {"start": s["start"], "end": s["end"]} for s in aligned["sentences"]
        ],
        "pace": pace(aligned["words"], word_count),
        "transcript_check": {
            "word_error_rate": aligned["word_error_rate"],
            "differences": aligned["differences"],
            "vocalizations": vocalizations,
            "heard": heard_text,
            "passed": aligned["word_error_rate"] <= MAX_WORD_ERROR_RATE and not vocalizations,
        },
    }


def check_problems(report: dict) -> list[str]:
    check = report.get("transcript_check") or {}
    problems: list[str] = []
    rate = check.get("word_error_rate")
    if rate is not None and rate > MAX_WORD_ERROR_RATE:
        problems.append(
            f"narration differs from the transcript (word error rate {rate:.0%}); "
            "regenerate the take or fix narration.txt"
        )
    if check.get("vocalizations"):
        problems.append(
            "non-speech vocalization heard: " + ", ".join(check["vocalizations"])
        )
    return problems


def load_timing(project_dir: Path) -> dict | None:
    """The word-timed report, or None when missing or older than the WAV."""
    artifacts = project_dir / "artifacts"
    timing, audio = artifacts / "narration-timing.json", artifacts / "narration.wav"
    try:
        report = json.loads(timing.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict) or not report.get("words"):
        return None
    if not audio.is_file() or report.get("audio_sha256") != sha256(audio):
        return None
    return report


def find_phrase(words: list[dict], phrase: str, occurrence: int = 1) -> dict:
    """Start and end of the Nth spoken occurrence of `phrase`."""
    target = normalize_tokens(phrase)
    if not target:
        raise ValueError(f"Cue phrase has no words: {phrase!r}")
    tokens = [word["word"] for word in words]
    seen = 0
    for index in range(len(tokens) - len(target) + 1):
        if tokens[index:index + len(target)] == target:
            seen += 1
            if seen == occurrence:
                return {
                    "phrase": phrase,
                    "start": words[index]["start"],
                    "end": words[index + len(target) - 1]["end"],
                    "sentence": words[index]["sentence"],
                }
    found = f"only {seen} time(s)" if seen else "nowhere"
    raise ValueError(
        f"Cue phrase {phrase!r} (occurrence {occurrence}) is spoken {found} in the "
        "narration transcript; quote words exactly as they appear in Transcript:"
    )


def score_take(audio: Path, prompt: str, model_name: str = DEFAULT_MODEL) -> dict:
    """Objective take score; lower is better."""
    report = measure(audio, prompt, model_name)
    check, measured = report["transcript_check"], report["pace"]
    wpm = measured.get("words_per_minute") or TARGET_WPM
    longest = measured.get("longest_pause_seconds") or 0.0
    peak = peak_dbfs(audio)
    penalties = {
        "transcript": round(check["word_error_rate"] * 100, 2),
        "pace": round(max(0.0, abs(wpm - TARGET_WPM) - 10) * 0.3, 2),
        "long_pause": round(max(0.0, longest - 1.4) * 5, 2),
        "clipping": 10.0 if peak is not None and peak > -0.5 else 0.0,
        "vocalization": 25.0 * len(check["vocalizations"]),
    }
    return {
        "take": audio.name,
        "score": round(sum(penalties.values()), 2),
        "penalties": penalties,
        "word_error_rate": check["word_error_rate"],
        "differences": check["differences"],
        "vocalizations": check["vocalizations"],
        "words_per_minute": measured.get("words_per_minute"),
        "longest_pause_seconds": longest,
        "peak_dbfs": peak,
        "duration_seconds": report["duration_seconds"],
    }


def rank_takes(takes_dir: Path, prompt: str, model_name: str = DEFAULT_MODEL) -> dict:
    raw = sorted(
        path for path in takes_dir.glob("*.wav") if not path.stem.endswith("-matched")
    )
    if not raw:
        raise FileNotFoundError(f"No raw take WAVs in {takes_dir}")
    scored = sorted((score_take(path, prompt, model_name) for path in raw),
                    key=lambda item: item["score"])
    return {
        "method": "objective: transcript accuracy, pace, longest pause, peak, vocalizations",
        "recommended": scored[0]["take"],
        "takes": scored,
        "note": "Objective ranking; audition the top takes when listening is available.",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="faster-whisper model (default: %(default)s)")
    parser.add_argument("--takes", action="store_true",
                        help="Rank raw takes in artifacts/narration-takes/ instead")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = args.project_dir.resolve() / "artifacts"
    prompt = (artifacts / "narration.txt").read_text(encoding="utf-8")
    if args.takes:
        ranking = rank_takes(artifacts / "narration-takes", prompt, args.model)
        path = artifacts / "narration-takes" / "ranking.json"
        path.write_text(json.dumps(ranking, indent=2) + "\n", encoding="utf-8")
        for item in ranking["takes"]:
            print(f"{item['take']}: score {item['score']} (WER {item['word_error_rate']:.0%}, "
                  f"{item['words_per_minute']} WPM, longest pause "
                  f"{item['longest_pause_seconds']}s)")
        print(f"Recommended: {ranking['recommended']} — {path}")
        return 0
    audio = artifacts / "narration.wav"
    report = measure(audio, prompt, args.model)
    path = artifacts / "narration-timing.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    check = report["transcript_check"]
    print(f"Word timing: {path}")
    print(f"  word error rate {check['word_error_rate']:.0%}; "
          f"{report['pace'].get('words_per_minute')} WPM")
    for number, sentence in enumerate(report["sentences"], start=1):
        print(f"  {number}. {sentence['start']:6.2f}–{sentence['end']:6.2f}s  {sentence['text']}")
    for difference in check["differences"][:12]:
        print(f"  expected {difference['expected']!r}, heard {difference['heard']!r} "
              f"at {difference['at']}s")
    problems = check_problems(report)
    for problem in problems:
        print(f"ERROR: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
