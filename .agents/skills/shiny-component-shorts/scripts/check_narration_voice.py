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
# Sales and marketing language: a developer talking to a coworker never says these.
HYPE_WORD_RE = re.compile(
    r"\b(?:amazing|incredible|awesome|magic(?:al)?|instantly|effortless|beautiful(?:ly)?"
    r"|stunning|revolutionary|ultimate|insanely|mind-blowing|must-have|blazing|super easy"
    r"|simply|next level|level up|secret weapon|hack)\b",
    re.IGNORECASE,
)
AD_PHRASE_RE = re.compile(
    r"\b(?:here['’]s the thing|watch this|the best part|but wait|say goodbye to|no more"
    r"|imagine|what if i told you|trust me|you['’](?:re going to|ll) love"
    r"|that['’]s the (?:whole )?(?:trick|magic|secret)|it['’]s that (?:easy|simple)"
    r"|the good news)\b",
    re.IGNORECASE,
)
# An opener that asks the viewer about their pain is an ad's hook, not a person talking.
AD_HOOK_RE = re.compile(
    r"^\s*(?:still|tired|sick|ever|what if|want|wish|struggling|are you|do you|did you know"
    r"|why is your|stop)\b[^.!]*\?",
    re.IGNORECASE,
)
CALL_TO_ACTION_RE = re.compile(
    r"\b(?:try it|give it a (?:try|shot|go)|check it out|start using|go build|grab it"
    r"|upgrade (?:now|today)|don['’]t miss)\b",
    re.IGNORECASE,
)
NOT_JUST_RE = re.compile(r"\bnot just\b", re.IGNORECASE)
# "X, not Y" is a fine contrast once; every result stated that way is a pattern.
PLAIN_CONTRAST_RE = re.compile(r",\s*not\s+(?:the\s+|a\s+|an\s+)?\w+", re.IGNORECASE)
# Stock lead-ins and softeners that a template reaches for between beats.
TEMPLATE_PHRASE_RE = re.compile(
    r"\b(?:comes? for free|one thing to know|one condition|one more thing|here['’]s why|here['’]s the app"
    r"|here['’]s what that looks like|here['’]s the part)\b",
    re.IGNORECASE,
)
# "<Product> now does X" is release-note voice, not a person explaining.
RELEASE_NOTE_OPENER_RE = re.compile(
    r"^\s*(?:shiny(?: for python)?|shinychat|shinyreact|bslib|the (?:new )?(?:release|version))\b[^.!?]*\bnow\b",
    re.IGNORECASE,
)
# Bare imperatives read as tutorial steps; a developer says "I click" or "when you click".
IMPERATIVE_STEP_RE = re.compile(
    r"^\s*(?:click|press|type|select|open|run|choose|set|toggle|drag|scroll|refresh|enter)\b",
    re.IGNORECASE,
)
FIRST_PERSON_RE = re.compile(r"\b(?:I|I['’](?:ll|m|ve|d)|we|when you|if you)\b")
# The "Here's ..." hand-off and the closing caveat are fine once in a series, not in every video.
HANDOFF_RE = re.compile(r"\bhere['’]s\b", re.IGNORECASE)
CLOSING_CAVEAT_RE = re.compile(
    r"^\s*(?:one (?:thing|condition|caveat|catch|limit)|but|if you|note that|keep in mind"
    r"|one more|and|also|plus|there['’]s (?:a|one) (?:limit|catch|caveat|third|more))\b",
    re.IGNORECASE,
)
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
So this is a Shiny text area with three rows, and the scrollbar's already doing most of the work. [short pause] I always assumed the fix was CSS. It isn't. The height comes from the rows argument, and one row is roughly one line of text. I'll change rows to four. [medium pause] The box grows right away, and the scrollbar's gone. No custom CSS. I missed this for months and kept writing CSS to force the height, even though the docs mention it right there in the rows argument. [long pause] Set it back to three. It shrinks again, so that one argument really is what controls the height."""

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
        problems.append(
            "Tidy three-item list(s): " + "; ".join(lists)
            + " (fine when these are literal API values or column types)"
        )
    return problems + sales_problems(spoken) + template_problems(spoken)


def template_problems(spoken: str) -> list[str]:
    """Flag the shapes a script template leaves behind once the hype words are gone."""
    problems = []
    contrasts = PLAIN_CONTRAST_RE.findall(spoken)
    if len(contrasts) > 1:
        problems.append(
            f'"X, not Y" contrast used {len(contrasts)} times; keep one and state the other result plainly'
        )
    stock = sorted({match.group(0).casefold() for match in TEMPLATE_PHRASE_RE.finditer(spoken)})
    if stock:
        problems.append("Template lead-in(s): " + ", ".join(stock) + "; say the point without the hand-off")
    sentences = sentences_of(spoken)
    if sentences and RELEASE_NOTE_OPENER_RE.search(sentences[0]):
        problems.append(
            'The opener is release-note voice ("<Product> now ..."); start with what you ran or saw'
        )
    imperatives = sum(1 for sentence in sentences if IMPERATIVE_STEP_RE.match(sentence))
    if imperatives >= 2 and not FIRST_PERSON_RE.search(spoken):
        problems.append(
            f"{imperatives} sentences are bare imperative steps and nothing is said in the first person; "
            'say "I click" or "when you click", and say once what you expected against what happened'
        )
    return problems


def pause_tag_problems(transcript: str) -> list[str]:
    """A pause tag after every paragraph is a metronome, not phrasing."""
    paragraphs = [block for block in re.split(r"\n\s*\n", transcript.strip()) if WORD_RE.search(block)]
    if len(paragraphs) < 4:
        return []
    closers = [TAG_RE.findall(paragraph)[-1].casefold() if TAG_RE.findall(paragraph) else None for paragraph in paragraphs[:-1]]
    if all(closers) and len(set(closers)) == 1:
        return [
            f"Every paragraph ends with the same {closers[0]}; let pauses follow the thought instead of the paragraph"
        ]
    return []


def sales_problems(spoken: str) -> list[str]:
    """Flag pitch language; the narrator explains, the way you'd tell a coworker."""
    problems = []
    hype = sorted({match.group(0).casefold() for match in HYPE_WORD_RE.finditer(spoken)})
    if hype:
        problems.append("Sales hype word(s): " + ", ".join(hype) + "; say what happens instead")
    ads = sorted({match.group(0).casefold() for match in AD_PHRASE_RE.finditer(spoken)})
    if ads:
        problems.append("Ad phrase(s): " + ", ".join(ads) + "; talk it through plainly")
    if "!" in spoken:
        problems.append("Exclamation marks sound like an ad; use a full stop")
    sentences = sentences_of(spoken)
    if sentences and AD_HOOK_RE.search(sentences[0]):
        problems.append(
            "The opener is an ad-style question about the viewer's pain; start by saying "
            "what's on screen or what you ran into, as a plain statement"
        )
    if sentences and CALL_TO_ACTION_RE.search(sentences[-1]):
        problems.append(
            "The script ends on a call to action; end on what the viewer just saw"
        )
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
    adjacent = sorted({
        match.group(1).casefold()
        for match in re.finditer(r"(\[[^\]]+\])\s*\1", transcript, re.IGNORECASE)
    })
    for tag in adjacent:
        problems.append(f"Tag {tag} repeats back to back; vary or drop it")
    problems.extend(pause_tag_problems(transcript))
    spoken = TAG_RE.sub(" ", transcript)
    problems.extend(phrase_problems(spoken))
    problems.extend(sentence_problems(sentences_of(spoken)))
    return problems


def _opening_words(sentence: str, count: int = 2) -> str:
    return " ".join(WORD_RE.findall(sentence)[:count]).casefold()


def series_problems(scripts: dict[str, str]) -> list[str]:
    """Shapes shared across the sibling scripts of one series."""
    problems = []
    spoken_by_name = {}
    for name, prompt in scripts.items():
        transcript = transcript_of(prompt)
        if transcript is None:
            continue
        spoken_by_name[name] = TAG_RE.sub(" ", transcript)
    if len(spoken_by_name) < 2:
        return problems
    openers: dict[str, list[str]] = {}
    closers: dict[str, list[str]] = {}
    phrases: dict[str, list[str]] = {}
    contrast_users = []
    handoff_users = []
    caveat_closers = []
    for name, spoken in spoken_by_name.items():
        sentences = sentences_of(spoken)
        if not sentences:
            continue
        openers.setdefault(_opening_words(sentences[0]), []).append(name)
        closers.setdefault(_opening_words(sentences[-1]), []).append(name)
        if HANDOFF_RE.search(spoken):
            handoff_users.append(name)
        last_paragraph = [block for block in re.split(r"\n\s*\n", spoken.strip()) if WORD_RE.search(block)][-1]
        if CLOSING_CAVEAT_RE.match(last_paragraph):
            caveat_closers.append(name)
        for match in TEMPLATE_PHRASE_RE.finditer(spoken):
            phrases.setdefault(match.group(0).casefold(), [])
            if name not in phrases[match.group(0).casefold()]:
                phrases[match.group(0).casefold()].append(name)
        if PLAIN_CONTRAST_RE.search(spoken):
            contrast_users.append(name)
    for words, names in sorted(openers.items()):
        if len(names) > 1:
            problems.append(f'{len(names)} scripts open with "{words} ...": {", ".join(names)}; rotate the opening move')
    for words, names in sorted(closers.items()):
        if len(names) > 1:
            problems.append(f'{len(names)} scripts close with "{words} ...": {", ".join(names)}; vary the ending')
    for phrase, names in sorted(phrases.items()):
        if len(names) > 1:
            problems.append(f'"{phrase}" appears in {len(names)} scripts: {", ".join(names)}; keep it to one')
    if len(handoff_users) > 1:
        problems.append(
            f'"Here\'s ..." hands off a beat in {len(handoff_users)} scripts: {", ".join(handoff_users)}; '
            "keep that move to one video"
        )
    if len(caveat_closers) > 1:
        problems.append(
            f"{len(caveat_closers)} scripts close on a caveat or tacked-on afterthought: {', '.join(caveat_closers)}; "
            "end some on the result or the code instead"
        )
    if len(contrast_users) > len(spoken_by_name) // 2 and len(contrast_users) > 1:
        problems.append(
            f'"X, not Y" contrast carries the result in {len(contrast_users)} of {len(spoken_by_name)} scripts: '
            + ", ".join(contrast_users)
            + "; state most results plainly"
        )
    return problems


def series_scripts(series_dir: Path) -> dict[str, str]:
    scripts = {}
    for narration in sorted(series_dir.glob("*/artifacts/narration.txt")):
        if narration.parent.parent.name.startswith("."):
            continue
        scripts[narration.parent.parent.name] = narration.read_text(encoding="utf-8")
    return scripts


def voice_errors(prompt_text: str) -> list[str]:
    transcript = transcript_of(prompt_text)
    if transcript is None:
        return ["Narration prompt is missing the Transcript: section"]
    errors = []
    if not WORD_RE.search(TAG_RE.sub(" ", transcript)):
        errors.append("Transcript has no spoken text")
    if re.search(r"\[[^]]*\b(?:laugh\w*|giggl\w*|chuckl\w*|sigh\w*|gasp\w*|cough\w*)\b[^]]*\]", transcript, re.I):
        errors.append("Non-speech vocalization cues are not allowed")
    return errors


def voice_warnings(prompt_text: str) -> list[str]:
    return [message for message in voice_problems(prompt_text) if message not in voice_errors(prompt_text)]


SALESY_PROMPT = """Synthesize this as a natural, curious tech explainer for a 45-second Shiny component video.

Audio profile:
A clear developer voice.

Scene:
A demo.

Director's notes:
Read only the transcript below.

Transcript:
Still writing CSS just to size a text box? Here's the thing. Shiny makes it amazing, and it works instantly! Say goodbye to scrollbars, because the best part is you set one argument and you're done with it for good. Try it on your next app."""

TEMPLATED_PROMPT = """Synthesize this as a natural, curious tech explainer for a detailed Shiny feature video.

Audio profile:
A clear developer voice.

Scene:
A dashboard.

Director's notes:
Read only the transcript below.

Transcript:
Shiny for Python now runs async outputs concurrently. Here's a dashboard with three slow outputs. [pause 1s]

Click Refresh dashboard. All three are ready after one second, not three. [pause 1s]

Here's why. Each output starts as its own task, so the page takes about as long as the slowest output, not the sum. [pause 1s]

Click Reset. The busy state comes for free. [pause 1s]

One thing to know. The priority argument sets the order effects start, not the order they finish."""


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
    salesy = " ".join(voice_problems(SALESY_PROMPT))
    for marker in ("Sales hype", "Ad phrase", "Exclamation", "ad-style question", "call to action"):
        if marker not in salesy:
            failures.append(f"sales-pitch script was not flagged for {marker}")
    templated = " ".join(voice_problems(TEMPLATED_PROMPT))
    for marker in ("contrast used", "Template lead-in", "release-note voice", "bare imperative", "same [pause 1s]"):
        if marker not in templated:
            failures.append(f"templated script was not flagged for {marker}")
    siblings = series_problems({"01": TEMPLATED_PROMPT, "02": TEMPLATED_PROMPT, "03": GOOD_PROMPT})
    joined = " ".join(siblings)
    for marker in ("scripts open with", "scripts close with", "appears in 2 scripts", "hands off a beat", "close on a caveat"):
        if marker not in joined:
            failures.append(f"series check missed {marker}")
    if series_problems({"01": GOOD_PROMPT, "02": TEMPLATED_PROMPT}):
        failures.append("series check flagged two unrelated scripts")
    for failure in failures:
        print(f"- {failure}")
    print("self-test passed" if not failures else f"self-test failed ({len(failures)})")
    return 1 if failures else 0


def check_series(series_dir: Path) -> int:
    scripts = series_scripts(series_dir)
    if not scripts:
        print(f"{series_dir}: no */artifacts/narration.txt files found")
        return 1
    exit_code = 0
    for name, prompt in scripts.items():
        for warning in voice_warnings(prompt):
            print(f"WARNING {name}: {warning}")
        for problem in voice_errors(prompt):
            print(f"- {name}: {problem}")
            exit_code = 1
    shared = series_problems(scripts)
    for warning in shared:
        print(f"WARNING series: {warning}")
    if exit_code:
        print(f"{series_dir}: {len(scripts)} script(s), with blocking problems")
    else:
        print(
            f"{series_dir}: {len(scripts)} script(s) checked, "
            f"{len(shared)} shared-shape warning(s)"
        )
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="narration.txt to check")
    parser.add_argument("--project-dir", help="check <project-dir>/artifacts/narration.txt")
    parser.add_argument(
        "--series",
        help="check every <series>/*/artifacts/narration.txt and report shapes they share",
    )
    parser.add_argument("--self-test", action="store_true", help="run the built-in fixtures")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.series:
        return check_series(Path(args.series))
    if args.path:
        narration = Path(args.path)
    elif args.project_dir:
        narration = Path(args.project_dir) / "artifacts" / "narration.txt"
    else:
        parser.error("pass a narration.txt path, --project-dir, or --self-test")
    if not narration.is_file():
        print(f"{narration}: no such narration file")
        return 1
    prompt = narration.read_text(encoding="utf-8")
    problems = voice_errors(prompt)
    for warning in voice_warnings(prompt):
        print(f"WARNING: {warning}")
    if problems:
        for problem in problems:
            print(f"- {problem}")
        print(f"{narration}: does not sound spoken yet ({len(problems)} problem(s))")
        return 1
    print(f"{narration}: voice check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
