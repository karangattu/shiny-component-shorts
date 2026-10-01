#!/usr/bin/env python3
"""Static voice lint for narration scripts.

`simple-english` makes a transcript clear; this gate checks it also sounds
spoken. Run it on `artifacts/narration.txt` before any synthesis spend.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TAG_RE = re.compile(r"\[[^\]]+\]")
WORD_RE = re.compile(r"\b[\w’'-]+\b")
CONTRACTION_RE = re.compile(r"\b\w+(?:’|')\w+\b")
EM_DASH_RE = re.compile(r"[—–]")
LONG_PAUSE_TAG_RE = re.compile(r"\[long pause\]", re.IGNORECASE)
BANNED_PHRASE_RE = re.compile(
    r"\b(?:game-changer|seamless|powerful|unlock|elevate|dive in"
    r"|let['’]s explore|effortlessly|supercharge)\b",
    re.IGNORECASE,
)
NOT_JUST_RE = re.compile(r"\bnot just\b", re.IGNORECASE)
IN_THEN_OUT_RE = re.compile(r"\bin,\s*[^.!?]*\bout\b", re.IGNORECASE)
SHORT_LIST_RE = re.compile(r"\b\w+,\s\w+,\s+and\s+\w+\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

FRAGMENT_MAX_WORDS = 5
LONG_SENTENCE_MIN_WORDS = 12
UNIFORM_LENGTH_DELTA = 4

GOOD_PROMPT = """Synthesize this as a natural, curious tech explainer for a 45-second Shiny component video.

Audio profile:
A clear developer voice. Natural, conversational, precise, warm, and not salesy. No non-speech vocalizations.

Scene:
A text input grows when its rows argument changes.

Director's notes:
Speak at a natural conversational pace. Allow normal pauses between thoughts and before reveals; do not rush to fit the video. Emphasize the surprising behavior. Do not laugh, giggle, or chuckle. Do not add sighs, gasps, coughs, filler sounds, or any other non-speech vocalization. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
Why is your Shiny text box three lines tall, with a scrollbar doing all the work? [long pause] It isn't the text box at all. The rows are what do it. Rows on the input is what sets the height, and one row is about one line of text. So change rows to four and watch the box grow right away. No scrollbar, no custom CSS. [short pause] I missed this for months and kept writing CSS to force the height. The docs say it in the rows argument. [medium pause] That's the whole trick, and you write one line to get it."""

WRITTEN_SOUNDING_PROMPT = """Synthesize this as a natural, curious tech explainer for a 45-second Shiny component video.

Audio profile:
A clear developer voice.

Scene:
A demo.

Director's notes:
Read only the transcript below.

Transcript:
Watch the panel update when the state value changes. [long pause] [long pause] Watch the table fill in, and the results out. Watch the card show it is fast, simple, clear, and powerful. Watch the fix work; not just fast — it is clear."""


def transcript_of(prompt_text: str) -> str | None:
    if "Transcript:" not in prompt_text:
        return None
    return prompt_text.split("Transcript:", 1)[1]


def sentences_of(spoken: str) -> list[str]:
    return [
        sentence
        for sentence in SENTENCE_SPLIT_RE.split(spoken.strip())
        if WORD_RE.search(sentence)
    ]


def word_count(sentence: str) -> int:
    return len(WORD_RE.findall(sentence))


def phrase_problems(spoken: str) -> list[str]:
    problems = []
    banned = sorted({match.group(0).casefold() for match in BANNED_PHRASE_RE.finditer(spoken)})
    if banned:
        problems.append("Banned stock phrase(s): " + ", ".join(banned))
    if NOT_JUST_RE.search(spoken):
        problems.append('"not just X, it is Y" reads as written; make the claim plainly')
    if IN_THEN_OUT_RE.search(spoken):
        problems.append('"in, ... out" is a parallel cadence; say it as a plain sentence')
    dashes = len(EM_DASH_RE.findall(spoken))
    if dashes:
        problems.append(
            f"Em dashes read as written prose (found {dashes}); use a full stop or a pause tag"
        )
    lists = sorted({match.group(0) for match in SHORT_LIST_RE.finditer(spoken)})
    if lists:
        problems.append("Tidy three-item list(s): " + "; ".join(lists))
    return problems


def sentence_problems(sentences: list[str]) -> list[str]:
    problems = []
    if not sentences:
        return ["Transcript has no spoken sentences"]
    lengths = [word_count(sentence) for sentence in sentences]
    openers = []
    for sentence in sentences:
        match = WORD_RE.search(sentence)
        openers.append(match.group(0).casefold() if match else "")
    for index in range(len(lengths) - 2):
        window = lengths[index : index + 3]
        if all(abs(a - b) <= UNIFORM_LENGTH_DELTA for a, b in zip(window, window[1:])):
            problems.append(
                "Three consecutive sentences are within "
                f"{UNIFORM_LENGTH_DELTA} words of each other ({window[0]}/{window[1]}/{window[2]}); "
                "vary the rhythm"
            )
            break
    for index in range(len(openers) - 2):
        window = openers[index : index + 3]
        if window[0] == window[1] == window[2] and window[0]:
            problems.append(
                f'Three consecutive sentences start with "{window[0]}"; change the openers'
            )
            break
    if len(sentences) >= 2:
        if not CONTRACTION_RE.search(" ".join(sentences)):
            problems.append("No contraction anywhere; this reads as written English, not speech")
        if not any(length <= FRAGMENT_MAX_WORDS for length in lengths):
            problems.append(
                f"No sentence fragment (a sentence of {FRAGMENT_MAX_WORDS} words or fewer)"
            )
        if not any(length >= LONG_SENTENCE_MIN_WORDS for length in lengths):
            problems.append(
                f"No long sentence (at least {LONG_SENTENCE_MIN_WORDS} words) to break the rhythm"
            )
    return problems


def voice_problems(prompt_text: str) -> list[str]:
    """Every reason the script reads as written rather than spoken."""
    transcript = transcript_of(prompt_text)
    if transcript is None:
        return ["Narration prompt is missing the Transcript: section"]
    problems = []
    long_pauses = LONG_PAUSE_TAG_RE.findall(transcript)
    if len(long_pauses) > 1:
        problems.append(
            f"Use at most one [long pause]; found {len(long_pauses)} "
            "(let punctuation and thought boundaries carry the other pauses)"
        )
    tags = [tag.casefold() for tag in TAG_RE.findall(transcript)]
    for previous, current in zip(tags, tags[1:]):
        if previous == current:
            problems.append(f"Tag {current} repeats back to back; vary or drop it")
    spoken = TAG_RE.sub(" ", transcript)
    problems.extend(phrase_problems(spoken))
    problems.extend(sentence_problems(sentences_of(spoken)))
    return problems


def self_test() -> int:
    failures = []
    if voice_problems(GOOD_PROMPT):
        failures.append("good script was flagged: " + "; ".join(voice_problems(GOOD_PROMPT)))
    expected = (
        "[long pause]",
        "repeats back to back",
        "Banned stock phrase",
        "not just",
        "parallel cadence",
        "Em dashes",
        "three-item list",
        "within 4 words",
        'start with "watch"',
        "contraction",
        "fragment",
        "long sentence",
    )
    flagged = " ".join(voice_problems(WRITTEN_SOUNDING_PROMPT))
    for marker in expected:
        if marker not in flagged:
            failures.append(f"written-sounding script was not flagged for {marker}")
    for failure in failures:
        print(f"- {failure}")
    print("self-test passed" if not failures else f"self-test failed ({len(failures)})")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="narration.txt to check")
    parser.add_argument("--project-dir", help="check <project-dir>/artifacts/narration.txt")
    parser.add_argument("--self-test", action="store_true", help="run the built-in fixtures")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.path:
        narration = Path(args.path)
    elif args.project_dir:
        narration = Path(args.project_dir) / "artifacts" / "narration.txt"
    else:
        parser.error("pass a narration.txt path, --project-dir, or --self-test")
    if not narration.is_file():
        print(f"{narration}: no such narration file")
        return 1
    problems = voice_problems(narration.read_text(encoding="utf-8"))
    if problems:
        for problem in problems:
            print(f"- {problem}")
        print(f"{narration}: does not sound spoken yet ({len(problems)} problem(s))")
        return 1
    print(f"{narration}: voice check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
