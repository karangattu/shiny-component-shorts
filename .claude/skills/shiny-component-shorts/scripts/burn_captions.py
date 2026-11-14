#!/usr/bin/env python3
"""Burn readable captions into a vertical (9:16) social video.

Captions come from the narration's measured word timing (narration-timing.json),
never from retyped text, so they stay in sync with the audio. The script writes an
editable SRT sidecar and an ASS file, then burns the ASS into a re-encoded copy.
The clean export is never overwritten.

Styles are presets; a video should use one, and a series should rotate through
them (see references/social-captions.md). Captions sit in the lower band of the
frame, above the bottom 20% that social apps cover with their own UI.

Usage:
  burn_captions.py --video reel.mp4 --timing narration-timing.json \
      --style karaoke --out-video reel-captioned.mp4 --out-srt reel.srt
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ASS colours are &HAABBGGRR. Alpha 00 is opaque, FF is transparent.
WHITE = "&H00FFFFFF"
INK = "&H001D1F21"        # Shiny text colour on light surfaces
SHINY_BLUE = "&H00C27B00"  # #007BC2
BLACK_TRANS = "&H66000000"
YELLOW = "&H0040C9FF"      # #FFC940, karaoke highlight
WHITE_CARD = "&HFFFFFFFF"

FONT = "Avenir Next"

# Each style: ASS style fields. BorderStyle 1 = outline + shadow, 3 = opaque box.
STYLES = {
    "clean": dict(
        desc="White text on a translucent black box",
        size=60, bold=-1, primary=WHITE, secondary=YELLOW, outline=WHITE_CARD,
        back=BLACK_TRANS, border_style=3, outline_w=14, shadow=0, karaoke=False,
    ),
    "pill": dict(
        desc="White text on a Shiny-blue pill",
        size=60, bold=-1, primary=WHITE, secondary=YELLOW, outline=SHINY_BLUE,
        back=SHINY_BLUE, border_style=3, outline_w=22, shadow=0, karaoke=False,
    ),
    "karaoke": dict(
        desc="Outlined text; each spoken word fills yellow as it is said",
        size=64, bold=-1, primary=WHITE, secondary=YELLOW, outline="&H00000000",
        back="&H00000000", border_style=1, outline_w=7, shadow=0, karaoke=True,
    ),
    "outline": dict(
        desc="Heavy white text with a black outline, no box",
        size=66, bold=-1, primary=WHITE, secondary=YELLOW, outline="&H00000000",
        back="&H00000000", border_style=1, outline_w=8, shadow=2, karaoke=False,
    ),
    "card": dict(
        desc="Dark text on a white card",
        size=58, bold=-1, primary=INK, secondary=INK, outline=WHITE_CARD,
        back=WHITE_CARD, border_style=3, outline_w=16, shadow=0, karaoke=False,
    ),
    "bar": dict(
        desc="Two-line caption bar across the lower frame",
        size=54, bold=0, primary=WHITE, secondary=YELLOW, outline=BLACK_TRANS,
        back=BLACK_TRANS, border_style=3, outline_w=34, shadow=0, karaoke=False,
    ),
}

PLAY_W, PLAY_H = 1440, 2560
MARGIN_LR = 90
MARGIN_V = 470          # from the bottom edge, in frame pixels (about 18% of the height)
MAX_WORDS = 7
MAX_CHARS = 38
MIN_HOLD = 0.7          # seconds a phrase stays on screen at minimum
GAP_BREAK = 0.6         # a pause this long always starts a new caption


def transcript_tokens(script: Path) -> list[str]:
    """Spoken tokens from the Transcript section, with pause tags removed."""
    text = script.read_text(encoding="utf-8").split("Transcript:", 1)[-1]
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return text.split()


DIGIT_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
               "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}


def _norm(token: str) -> str:
    return re.sub(r"[^a-z0-9]", "", token.lower())


def load_words(timing: Path) -> tuple[list[dict], float]:
    """Timed words for display. Casing and punctuation come from the transcript where they line up."""
    from difflib import SequenceMatcher

    data = json.loads(timing.read_text(encoding="utf-8"))
    offset = float(data.get("narration_offset_seconds", 0.15))
    words = [w for w in data["words"] if w.get("end", 0) > w.get("start", 0)]
    if not words:
        raise SystemExit(f"{timing}: no timed words")
    script = timing.parent / "narration.txt"
    if not script.is_file():
        return words, offset
    tokens = transcript_tokens(script)
    # The recognizer spells digits as words ("k3d" is heard as "k three d"), so match on the spoken pieces.
    spoken, origin, first = [], [], []
    for index, token in enumerate(tokens):
        pieces: list[str] = []
        for piece in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+", token):
            if piece.isdigit():
                pieces += [DIGIT_WORDS[digit] if digit in DIGIT_WORDS else digit for digit in piece]
            else:
                pieces.append(piece)
        for position, piece in enumerate(pieces):
            spoken.append(_norm(piece))
            origin.append(index)
            first.append(position == 0)
    if not spoken:
        spoken = [_norm(t) for t in tokens]
        origin = list(range(len(tokens)))
        first = [True] * len(tokens)
    heard = [_norm(w["word"]) for w in words]
    display = [w["word"] for w in words]
    matcher = SequenceMatcher(a=heard, b=spoken, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "replace") and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                token_index = origin[j1 + k]
                display[i1 + k] = tokens[token_index] if first[j1 + k] else ""
    # Words the aligner split or merged keep their heard form, with sentence-start capitals restored.
    last_sentence = None
    for index, word in enumerate(words):
        text = display[index]
        if word.get("sentence") != last_sentence:
            text = text[:1].upper() + text[1:]
            last_sentence = word.get("sentence")
        if text.lower() == "i":
            text = "I"
        display[index] = text
    kept: list[dict] = []
    for word, text in zip(words, display):
        if text == "" and kept:
            kept[-1]["end"] = max(kept[-1]["end"], word["end"])
            continue
        word["word"] = text
        kept.append(word)
    return kept, offset


def group_phrases(words: list[dict]) -> list[list[dict]]:
    """Group words into readable phrases: break at punctuation, long pauses, or length."""
    phrases: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            chars = sum(len(w["word"]) + 1 for w in current) + len(word["word"])
            if gap > GAP_BREAK or len(current) >= MAX_WORDS or chars > MAX_CHARS:
                phrases.append(current)
                current = []
        current.append(word)
        text = word["word"].rstrip('"\')')
        ends_clause = bool(re.search(r"[.!?;:,]$", text)) and len(current) >= 3
        if ends_clause or word is words[-1]:
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)
    # Fold one-word phrases into their neighbour when the combined caption still fits.
    index = 1
    while index < len(phrases):
        if len(phrases[index]) == 1:
            merged = phrases[index - 1] + phrases[index]
            if len(merged) <= MAX_WORDS and sum(len(w["word"]) + 1 for w in merged) <= MAX_CHARS + 8:
                phrases[index - 1:index + 1] = [merged]
                continue
        index += 1
    return phrases


def display_word(word: dict) -> str:
    return re.sub(r"\s+", " ", word["word"]).strip()


def phrase_text(words: list[dict], karaoke: bool) -> str:
    """ASS text for one phrase. Karaoke tags use centiseconds per word."""
    parts = []
    for word in words:
        text = display_word(word)
        if karaoke:
            duration = max(1, round((word["end"] - word["start"]) * 100))
            parts.append(f"{{\\k{duration}}}{text}")
        else:
            parts.append(text)
    joined = " ".join(parts)
    # Keep long phrases to two balanced lines: break near the middle word.
    plain = " ".join(display_word(w) for w in words)
    if len(plain) > 30 and len(words) > 2:
        half = len(words) // 2
        head = " ".join(parts[:half])
        tail = " ".join(parts[half:])
        joined = head + r"\N" + tail
    return joined


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def srt_time(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_ass(phrases: list[list[dict]], offset: float, style: dict, path: Path) -> list[tuple[float, float, str]]:
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_W}",
        f"PlayResY: {PLAY_H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Caption,{FONT},{style['size']},{style['primary']},{style['secondary']},"
            f"{style['outline']},{style['back']},{style['bold']},0,0,0,100,100,0,0,"
            f"{style['border_style']},{style['outline_w']},{style['shadow']},2,"
            f"{MARGIN_LR},{MARGIN_LR},{MARGIN_V},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    cues: list[tuple[float, float, str]] = []
    for index, words in enumerate(phrases):
        start = words[0]["start"] + offset
        end = words[-1]["end"] + offset
        nxt = phrases[index + 1][0]["start"] + offset if index + 1 < len(phrases) else None
        end = max(end + 0.25, start + MIN_HOLD)
        if nxt is not None:
            end = min(end, nxt - 0.02)
        text = phrase_text(words, style["karaoke"])
        plain = " ".join(display_word(w) for w in words)
        cues.append((start, end, plain))
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cues


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    blocks = []
    for number, (start, end, text) in enumerate(cues, start=1):
        blocks.append(f"{number}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def probe_size(video: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    width, height = (int(v) for v in out.split(","))
    return width, height


def burn(video: Path, ass: Path, out_video: Path) -> None:
    # The subtitles filter reads a path; quote it for libass and keep the working directory simple.
    escaped = str(ass).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
    command = [
        "ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
        "-vf", f"subtitles=filename='{escaped}'",
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(out_video),
    ]
    subprocess.run(command, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--timing", required=True, type=Path, help="narration-timing.json")
    parser.add_argument("--style", required=True, choices=sorted(STYLES))
    parser.add_argument("--out-video", required=True, type=Path)
    parser.add_argument("--out-srt", type=Path, help="SRT sidecar path (default: beside the output)")
    parser.add_argument("--out-ass", type=Path, help="ASS path (default: beside the output)")
    args = parser.parse_args(argv)

    width, height = probe_size(args.video)
    if (width, height) != (1440, 2560):
        print(f"expected a 1440x2560 vertical video, got {width}x{height}", file=sys.stderr)
        return 2

    words, offset = load_words(args.timing)
    phrases = group_phrases(words)
    style = STYLES[args.style]
    out_dir = args.out_video.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    ass_path = args.out_ass or out_dir / f"{args.out_video.stem}.ass"
    srt_path = args.out_srt or out_dir / f"{args.out_video.stem}.srt"
    cues = write_ass(phrases, offset, style, ass_path)
    write_srt(cues, srt_path)
    burn(args.video, ass_path, args.out_video)
    print(f"style={args.style} ({style['desc']})")
    print(f"captions={len(cues)} from {len(words)} timed words; offset={offset}s")
    print(f"video={args.out_video}")
    print(f"srt={srt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
