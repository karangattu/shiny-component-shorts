"""Editing polish: leading cuts, moving stills, readable wrapped code, and varied pauses."""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/shiny-component-shorts/scripts"))
import check_narration_voice
import end_card
import prepare_editorial
import stitch_reel as reel
import validate_editorial

from test_editorial import change, segment  # noqa: E402,F401  (shared narrated fixture)

REEL = {"style": "editorial", "title": "Evidence", "features": [{"title": "Evidence", "dir": "."}]}


def frame_at(video: str, seconds: float, output: Path) -> Image.Image:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{seconds:.3f}", "-i", video, "-frames:v", "1", str(output)],
        check=True,
    )
    return Image.open(output).convert("RGB")


def test_cut_leads_its_phrase_and_the_validator_accepts_it(segment, monkeypatch):  # noqa: F811
    monkeypatch.setattr(reel, "CUT_LEAD_SECONDS", 0.2)
    monkeypatch.setattr(reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)})
    # "second" is spoken at 1.15 s in the video; the picture changes six frames before it.
    assert reel.editorial_plan(segment, "vertical")["shots"][1]["start"] == 29 / 30
    change(segment, lambda c: c["shots"][1].update(cue={"phrase": "second", "lead": 0}))
    assert reel.editorial_plan(segment, "vertical")["shots"][1]["start"] == 35 / 30
    change(segment, lambda c: c["shots"][1].update(cue={"phrase": "second", "lead": 2}))
    with pytest.raises(ValueError, match="lead"):
        reel.editorial_plan(segment, "vertical")
    change(segment, lambda c: c["shots"][1].update(cue="second"))
    (segment / "reel.yaml").write_text(yaml.safe_dump(REEL))
    report = reel.build(segment, "vertical")
    assert report["shots"][1]["start"] == 29 / 30
    assert validate_editorial.validate_report(report)["decode"] == "passed"
    report["shots"][1]["cue_time"] += 1
    with pytest.raises(ValueError, match="out of sync"):
        validate_editorial.validate_report(report)


def test_stills_push_in_toward_the_highlight_and_can_stay_fixed(segment, monkeypatch):  # noqa: F811
    monkeypatch.setattr(reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)})
    monkeypatch.setattr(reel, "PUSH_IN", 0.2)  # exaggerated so a small test frame shows it
    monkeypatch.setattr(reel, "PUSH_IN_SETTLE_SECONDS", 0.3)
    image = Image.new("RGB", (288, 512), "white")
    ImageDraw.Draw(image).rectangle((40, 60, 120, 140), fill="black")
    image.save(segment / "first.png")
    (segment / "reel.yaml").write_text(yaml.safe_dump(REEL))
    video = reel.build(segment, "vertical")["reel"]
    early, late = frame_at(video, 0.4, segment / "a.png"), frame_at(video, 1.0, segment / "b.png")
    assert ImageChops.difference(early, late).getbbox() is not None
    change(segment, lambda c: [v.update(motion="none") for v in c["shots"][0]["views"].values()])
    video = reel.build(segment, "vertical")["reel"]
    early, late = frame_at(video, 0.4, segment / "a.png"), frame_at(video, 1.0, segment / "b.png")
    difference = ImageChops.difference(early, late).convert("L").point(lambda value: 255 if value > 24 else 0)
    assert difference.getbbox() is None
    change(segment, lambda c: c["shots"][0]["views"]["vertical"].update(motion="spin"))
    with pytest.raises(ValueError, match="motion"):
        reel.editorial_plan(segment, "vertical")


def test_warns_when_a_highlight_outline_crosses_text(segment, monkeypatch):  # noqa: F811
    monkeypatch.setattr(reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)})
    image = Image.new("RGB", (288, 512), "white")
    ImageDraw.Draw(image).rectangle((40, 200, 240, 230), fill="black")  # one "line" of text
    image.save(segment / "first.png")
    around, through = [0.1, 0.36, 0.8, 0.12], [0.1, 0.36, 0.8, 0.06]
    change(segment, lambda c: c["shots"][0]["views"]["vertical"].update(highlight=around))
    assert reel.highlight_warnings(reel.editorial_plan(segment, "vertical"), "vertical") == []
    change(segment, lambda c: c["shots"][0]["views"]["vertical"].update(highlight=through))
    warnings = reel.highlight_warnings(reel.editorial_plan(segment, "vertical"), "vertical")
    assert len(warnings) == 1 and "crosses content" in warnings[0]


def test_wrapped_code_keeps_a_hanging_indent_and_a_highlight_around_all_of_it(tmp_path):
    long_line = "    await asyncio.sleep(2)  # simulated query that takes two whole seconds to finish"
    (tmp_path / "app.py").write_text("async def sales():\n" + long_line + "\n    return 1\n")
    (tmp_path / "reel.yaml").write_text("title: Wrapped code\n")
    (tmp_path / "source-shots.yaml").write_text("""shots:
- cue: The code
  panels:
  - {kind: code, file: app.py, lines: [1, 3], highlight: 2}
""")
    result = prepare_editorial.prepare(tmp_path)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 720, "height": 1280})
        page.set_content((tmp_path / "artifacts/editorial-sources/shot-001-vertical.html").read_text())
        measured = page.evaluate("""() => {
 const node = document.querySelector('[data-highlight] .text');
 const range = document.createRange(); range.selectNodeContents(node);
 const rects = [...range.getClientRects()];
 const lines = [...new Set(rects.map(r => Math.round(r.top)))].sort((a, b) => a - b);
 const left = top => Math.min(...rects.filter(r => Math.round(r.top) === top && r.width > 0).map(r => r.left));
 const all = range.getBoundingClientRect();
 return {lines: lines.length, first: left(lines[0]), next: left(lines[1]),
         box: [all.left, all.top, all.right, all.bottom]};
}""")
        browser.close()
    assert measured["lines"] >= 2
    # The wrapped part starts to the right of the line's own first character.
    assert measured["next"] > measured["first"] + 20
    x, y, w, h = result["shots"][0]["views"]["vertical"]["highlight"]
    left, top, right, bottom = measured["box"]
    assert x * 720 < left and y * 1280 < top and (x + w) * 720 > right and (y + h) * 1280 > bottom


def test_end_card_dissolves_in_without_changing_its_length(tmp_path):
    Image.new("RGB", (144, 256), "red").save(tmp_path / "previous.png")
    Image.new("RGB", (144, 256), "blue").save(tmp_path / "card.png")
    video = end_card.clip(tmp_path / "card.png", 2, tmp_path / "card.mp4", (144, 256), "30",
                          tmp_path / "previous.png")
    first = frame_at(str(video), 0.0, tmp_path / "first.png").getpixel((72, 128))
    held = frame_at(str(video), 1.0, tmp_path / "held.png").getpixel((72, 128))
    assert isinstance(first, tuple) and isinstance(held, tuple)
    assert first[0] > 180 and held[2] > 180 and held[0] < 60
    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout)
    assert duration == pytest.approx(2, abs=0.05)


def test_pause_after_most_sentences_or_on_two_lengths_is_reported():
    metronome = "Transcript:\n" + " ".join(
        f"I change value {number} and the page updates. [pause {'0.5' if number % 2 else '0.7'}s]"
        for number in range(8)
    )
    problems = check_narration_voice.pause_rhythm_problems(check_narration_voice.transcript_of(metronome) or "")
    assert any("sentence breaks" in problem for problem in problems)
    assert any("[pause 0.5s] or [pause 0.7s]" in problem for problem in problems)
    varied = (
        "I open the page and click Refresh. Both tables load. [pause 0.4s] The first one took two seconds. "
        "So did the second. I expected four. [pause 1.2s] The code has an await in each function. "
        "That is the whole difference. It lets the event loop move on. [pause 0.7s] Nothing else changed. "
        "The inputs still wait. [short pause] The outputs still arrive together. [pause 0.9s] "
        "A blocking call still blocks. [pause 0.3s] So keep the await."
    )
    assert check_narration_voice.pause_rhythm_problems(varied) == []
    assert check_narration_voice.voice_problems(check_narration_voice.GOOD_PROMPT) == []
