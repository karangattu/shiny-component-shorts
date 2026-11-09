"""The closing end card gives one next step and never changes the narrated timeline."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/shiny-component-shorts/scripts"))
import end_card
import stitch_reel as reel
import thumbnail
import validate_editorial

REAL_RESOLVE = end_card.resolve
from test_editorial import segment  # noqa: E402,F401  (shared narrated fixture)


def probe(path: Path) -> dict:
    return json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout)


def resolved(outro: object, **options) -> dict:
    card = end_card.resolve(outro, **options)
    assert card is not None
    return card


def test_defaults_follow_the_release_and_language():
    assert resolved(None, release="1.9.0") == {
        "title": "Try Shiny 1.9 today", "command": "pip install shiny --upgrade",
        "link": "shiny.posit.co", "seconds": 4.0,
    }
    assert resolved(None, release="1.9.1")["title"] == "Try Shiny 1.9.1 today"
    # The upgrade command would not install an unreleased feature.
    unreleased = resolved(None, release="Unreleased")
    assert (unreleased["title"], unreleased["command"]) == ("Learn more about Shiny", "")
    assert resolved(True, language="r")["command"] == 'install.packages("shiny")'
    custom = resolved({"title": "Try shinywidgets", "command": "pip install shinywidgets", "link": ""})
    assert (custom["command"], custom["link"]) == ("pip install shinywidgets", "")
    assert end_card.resolve(False) is None


@pytest.mark.parametrize("outro", ["Try it", {"why": "typo"}, {"title": " "}, {"seconds": 30}, {"command": 3}])
def test_rejects_unreadable_or_unknown_settings(outro):
    with pytest.raises(ValueError, match="outro"):
        end_card.resolve(outro)


def test_card_fits_both_orientations_and_refuses_overflow(tmp_path):
    from playwright.sync_api import sync_playwright

    card = resolved(None, release="1.9.0")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for orientation in end_card.SIZES:
            assert end_card.render(browser, card, orientation, tmp_path / f"{orientation}.png", 1).stat().st_size
        with pytest.raises(ValueError, match="Shorten the outro"):
            end_card.render(browser, {**card, "title": "word " * 60}, "horizontal", tmp_path / "long.png", 1)
        browser.close()


def test_editorial_video_ends_on_the_card_after_the_narrated_timeline(segment, monkeypatch):  # noqa: F811
    monkeypatch.setattr(end_card, "resolve", REAL_RESOLVE)
    monkeypatch.setattr(reel, "SIZES", {"vertical": (144, 256), "horizontal": (256, 144)})
    config = {"style": "editorial", "title": "Evidence", "release": "1.9.0",
              "features": [{"title": "Evidence", "dir": "."}]}
    (segment / "reel.yaml").write_text(yaml.safe_dump(config))
    report = reel.build(segment, "vertical")
    narrated = 95 / 30
    assert report["end_card"]["title"] == "Try Shiny 1.9 today"
    assert report["duration_seconds"] == pytest.approx(narrated + 4, abs=0.05)
    assert [c["label"] for c in report["chapters"]] == ["Evidence"]
    assert report["shots"][-1]["label"] == "End card"
    assert report["shots"][-1]["start"] == pytest.approx(narrated, abs=0.001)
    assert (segment / "artifacts/end-card.png").is_file()
    assert validate_editorial.validate_report(report)["decode"] == "passed"

    (segment / "reel.yaml").write_text(yaml.safe_dump({**config, "outro": False}))
    report = reel.build(segment, "vertical")
    assert report["end_card"] is None
    assert report["duration_seconds"] == pytest.approx(narrated, abs=0.05)


def test_component_video_gets_the_card_only_when_actions_ask(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    video = artifacts / "final_with_audio.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=144x256:r=30:d=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", str(video)],
        check=True,
    )
    (tmp_path / "actions.yaml").write_text("title: A demo\nactions: []\n")
    assert end_card.for_project(tmp_path) is None
    (tmp_path / "actions.yaml").write_text("title: A demo\noutro: {seconds: 3}\nactions: []\n")
    card = end_card.for_project(tmp_path)
    assert card is not None
    assert card["title"] == "Try it yourself"
    end_card.append(video, card)
    data = probe(video)
    picture = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert (picture["width"], picture["height"], picture["r_frame_rate"]) == (144, 256, "30/1")
    assert float(data["format"]["duration"]) == pytest.approx(5, abs=0.1)
    # The cover image comes from the app, three seconds of card and one second before it.
    frame = tmp_path / "frame.png"
    thumbnail.payoff_frame(video, frame, card["seconds"])
    from PIL import Image

    pixel = Image.open(frame).convert("RGB").getpixel((72, 128))
    assert isinstance(pixel, tuple) and pixel[2] > 200 and pixel[0] < 40 and pixel[1] < 40
