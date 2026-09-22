"""Synthesize a complete demo project so the validator can be tested anywhere.

Recorded demo folders are deliberately not committed — they are large MP4 and
WAV artifacts — so contract tests that pointed at them could only skip on CI.
These helpers build an equivalent project in a temp directory from real media:
a PCM narration track whose silences mark sentence boundaries, and an H.264
recording at the orientation under test. Every validator check therefore runs
in CI instead of being skipped.

Requires ffmpeg and ffprobe on PATH, which the validator needs anyway.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

APP_SOURCE = """from shiny.express import input, render, ui

ui.input_action_button("seven", "7 days")
ui.input_action_button("ninety", "90 days")
ui.input_action_button("thirty", "30 days")


@render.text
def window_label():
    return f"{input.seven()} / {input.ninety()} / {input.thirty()}"
"""

# Four sentences, 100 spoken words and 4 audio tags — inside the validator's
# 95–130 word and 3–6 tag windows.
NARRATION_SENTENCES = (
    "[steady] A dashboard number tells you where the total landed for the day, "
    "but it hides the shape of the week and the dips behind the headline on the "
    "card.",
    "[short pause] Switch the window to seven days and the card redraws its "
    "sparkline in place, while the value label and its caption keep the same "
    "spot on the card.",
    "[curious] Ninety days stretches the same line into a longer climb with "
    "roomier gaps between the markers, and thirty brings the working view back "
    "with room to spare.",
    "[calm] One argument does all of it, and the chart never leaves the card it "
    "started in, so the layout stays calm while the range moves.",
)

SPEECH_SECONDS = 1.6
GAP_SECONDS = 0.5
SAMPLE_RATE = 24_000
RESOLUTIONS = {"vertical": (1440, 2560), "horizontal": (2560, 1440)}


def narration_windows(count: int = len(NARRATION_SENTENCES)) -> list[dict]:
    """Where each sentence is spoken in the synthesized WAV."""
    step = SPEECH_SECONDS + GAP_SECONDS
    return [
        {"start": round(index * step, 2), "end": round(index * step + SPEECH_SECONDS, 2)}
        for index in range(count)
    ]


def narration_seconds(count: int = len(NARRATION_SENTENCES)) -> float:
    return count * SPEECH_SECONDS + (count - 1) * GAP_SECONDS


def _write_narration_wav(path: Path, count: int) -> None:
    """A tone per sentence separated by true silence, so silencedetect can
    recover the sentence windows exactly the way it does on real narration."""
    speech = [
        int(12_000 * math.sin(2 * math.pi * 190 * frame / SAMPLE_RATE))
        for frame in range(int(SPEECH_SECONDS * SAMPLE_RATE))
    ]
    silence = [0] * int(GAP_SECONDS * SAMPLE_RATE)

    frames: list[int] = []
    for index in range(count):
        if index:
            frames.extend(silence)
        frames.extend(speech)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(struct.pack(f"<{len(frames)}h", *frames))


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def _write_video(path: Path, width: int, height: int, seconds: float) -> None:
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x007BC2:s={width}x{height}:d={seconds:.2f}:r=8",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def _narration_text() -> str:
    return (
        "Audio profile:\nA clear developer voice, brisk and precise.\n\n"
        "Scene:\nA value box redraws its sparkline as the window changes.\n\n"
        "Director's notes:\nSmall pauses before reveals. No non-speech "
        "vocalization.\n\nTranscript:\n" + " ".join(NARRATION_SENTENCES)
    )


def _actions(orientation: str) -> str:
    orientation_line = "orientation: horizontal\n" if orientation == "horizontal" else ""
    return (
        orientation_line + "overlays:\n"
        '  hook: "One argument redraws the whole card"\n'
        "actions:\n"
        '  - wait_for: "#window_label"\n'
        "  - wait: 1200\n"
        '  - cue: "tells you where"\n'
        '  - click: "#seven"\n'
        "  - wait: 2500\n"
        '  - cue: "switch the window to seven days"\n'
        '  - click: "#ninety"\n'
        "  - wait: 2500\n"
        '  - cue: "ninety days"\n'
        '  - click: "#thirty"\n'
        '  - cue: "one argument"\n'
        "  - code:\n"
        '      title: "app.py"\n'
        "      start_line: 7\n"
        "      text: |\n"
        "        @render.text\n"
        "        def window_label():\n"
        "  - screenshot:\n"
        '      path: "artifacts/final.png"\n'
    )


NARRATION_OFFSET_SECONDS = 0.15  # mirrors align_narration.NARRATION_OFFSET_SECONDS
CUE_PHRASES = ("tells you where", "switch the window to seven days", "ninety days", "one argument")


def word_timing(count: int = len(NARRATION_SENTENCES)) -> list[dict]:
    """Every transcript word spread evenly across its sentence's spoken window."""
    from align_narration import normalize_tokens, spoken_transcript, transcript_sentences

    sentences = transcript_sentences(spoken_transcript(_narration_text()))
    words: list[dict] = []
    for index, (sentence, window) in enumerate(zip(sentences, narration_windows(count))):
        tokens = normalize_tokens(sentence)
        step = (window["end"] - window["start"]) / len(tokens)
        for position, token in enumerate(tokens):
            start = window["start"] + step * position
            words.append({"word": token, "sentence": index, "start": round(start, 3),
                          "end": round(start + step, 3), "matched": True})
    return words


def cue_targets(count: int = len(NARRATION_SENTENCES)) -> list[float]:
    """Video time each fixture cue phrase is spoken."""
    from align_narration import find_phrase

    words = word_timing(count)
    return [round(find_phrase(words, phrase)["start"] + NARRATION_OFFSET_SECONDS, 2)
            for phrase in CUE_PHRASES]


def default_timeline(count: int = len(NARRATION_SENTENCES)) -> list[dict]:
    """A timeline that lands each reaction on the phrase describing it."""
    windows = narration_windows(count)
    targets = cue_targets(count)
    names = ("click", "click", "click", "code")
    return [
        {
            "action": name,
            "start": round(target - 0.5, 2),
            "end": windows[index]["end"] + NARRATION_OFFSET_SECONDS,
            "reaction": target,
            "cue": {"phrase": CUE_PHRASES[index], "target": target},
        }
        for index, (name, target) in enumerate(zip(names, targets))
    ]


def _write_word_timing(artifacts: Path, count: int) -> None:
    from align_narration import transcript_sentences, spoken_transcript

    words = word_timing(count)
    sentences = transcript_sentences(spoken_transcript(_narration_text()))
    spans = [
        {"text": text, "start": window["start"], "end": window["end"]}
        for text, window in zip(sentences, narration_windows(count))
    ]
    digest = hashlib.sha256((artifacts / "narration.wav").read_bytes()).hexdigest()
    (artifacts / "narration-timing.json").write_text(
        json.dumps(
            {
                "audio_sha256": digest,
                "alignment_method": "fixture word timing",
                "words": words,
                "sentences": spans,
                "sentence_windows": [{"start": s["start"], "end": s["end"]} for s in spans],
                "transcript_check": {"word_error_rate": 0.0, "differences": [],
                                     "vocalizations": [], "passed": True},
            }
        ),
        encoding="utf-8",
    )


def build_demo_project(
    root: Path,
    *,
    orientation: str = "vertical",
    resolution: tuple[int, int] | None = None,
    video_pad_seconds: float = 2.0,
    timeline: list[dict] | None = None,
    with_audio: bool = True,
) -> SimpleNamespace:
    """Write a demo project under ``root`` and return its paths and timings."""
    project = root / "demo-shorts"
    artifacts = project / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    (project / "app.py").write_text(APP_SOURCE, encoding="utf-8")
    (project / "actions.yaml").write_text(_actions(orientation), encoding="utf-8")
    (artifacts / "narration.txt").write_text(_narration_text(), encoding="utf-8")

    count = len(NARRATION_SENTENCES)
    audio_seconds = narration_seconds(count)
    narration_wav = artifacts / "narration.wav"
    _write_narration_wav(narration_wav, count)
    _write_word_timing(artifacts, count)

    width, height = resolution or RESOLUTIONS[orientation]
    demo_mp4 = artifacts / "demo.mp4"
    _write_video(
        demo_mp4, width, height, audio_seconds + NARRATION_OFFSET_SECONDS + video_pad_seconds
    )
    _run(["ffmpeg", "-y", "-i", str(demo_mp4), "-frames:v", "1", str(artifacts / "final.png")])

    if with_audio:
        _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(demo_mp4),
                "-i",
                str(narration_wav),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(artifacts / "final_with_audio.mp4"),
            ]
        )
    else:
        narration_wav.unlink()

    if timeline is not None:
        (artifacts / "recording.json").write_text(
            json.dumps(
                {
                    "orientation": orientation,
                    "action_timeline": timeline,
                    "logo": {"source": "shiny-logo.png", "width": 96},
                }
            ),
            encoding="utf-8",
        )

    return SimpleNamespace(
        project=project,
        artifacts=artifacts,
        narration_seconds=audio_seconds,
        windows=narration_windows(count),
        resolution=(width, height),
    )
