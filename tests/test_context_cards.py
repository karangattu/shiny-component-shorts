"""Context posters keep titles readable and app evidence unobstructed."""
import sys
from pathlib import Path

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/skills/shiny-component-shorts/scripts"))
import context_cards
import prepare_editorial


def test_prepare_automatically_builds_posters_and_openings_without_narration(tmp_path):
    (tmp_path / "reel.yaml").write_text("title: Reactive Plotly charts\n")
    (tmp_path / "app.py").write_text("from shinywidgets import render_plotly\n")
    Image.new("RGB", (680, 900), "#007BC2").save(tmp_path / "app.png")
    (tmp_path / "source-shots.yaml").write_text("""context:
  summary: A Shiny input updates the chart.
shots:
- cue: The input updates the chart
  panels:
  - {kind: image, file: app.png}
""")
    result = prepare_editorial.prepare(tmp_path)
    assert result["context"]["label"] == "Shiny for Python · shinywidgets"
    assert result["context"]["captures"] == {"vertical": "app.png", "horizontal": "app.png"}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for orientation, size in context_cards.SIZES.items():
            folder = tmp_path / "artifacts/context"
            with Image.open(folder / f"poster-{orientation}.jpg") as image:
                assert image.size == tuple(v*2 for v in size)
            with Image.open(folder / f"overlay-{orientation}.png") as image:
                pixel = image.getpixel((image.width//2, image.height-20))
                assert isinstance(pixel, tuple)
                assert pixel[3] == 0
            page = browser.new_page(viewport={"width": size[0], "height": size[1]})
            page.goto((folder / f"opening-{orientation}.html").as_uri())
            assert page.locator("h1").inner_text() == "Reactive Plotly charts"
            assert not page.locator(".summary").is_visible()
            header = page.locator("header").bounding_box()
            app = page.locator(".evidence").bounding_box()
            assert header and app
            assert header["y"]+header["height"] <= app["y"] or header["x"]+header["width"] <= app["x"]
            assert page.locator("img").evaluate("img => img.naturalWidth") == 680
            page.close()
        browser.close()


def test_context_uses_release_and_escapes_prose_without_inventing_a_claim(tmp_path):
    (tmp_path / "reel.yaml").write_text('release: Shiny 1.9\ntitle: "Inputs < outputs"\n')
    spec = context_cards.resolve(tmp_path, {"shots": [{}]})
    assert spec["label"] == "Shiny 1.9"
    assert spec["summary"] == ""
    Image.new("RGB", (300, 200), "white").save(tmp_path / "app.png")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        result = context_cards.render(browser, tmp_path, spec, "horizontal", tmp_path / "app.png")
        assert "Inputs &lt; outputs" in result["poster"].with_suffix(".html").read_text()
        spec["title"] = "A long title " * 100
        with pytest.raises(ValueError, match="overlaps"):
            context_cards.render(browser, tmp_path, spec, "horizontal", tmp_path / "app.png")
        browser.close()


def test_series_children_inherit_their_own_feature_title_and_release(tmp_path):
    (tmp_path / "reel.yaml").write_text("""release: Shiny 1.9
features:
- {title: Update the chart, dir: chart, why: A Shiny input changes the plotted metric.}
- {title: Filter the table, dir: table}
""")
    child = tmp_path / "chart"
    child.mkdir()
    spec = context_cards.resolve(child, {"shots": [{}]})
    assert spec["title"] == "Update the chart"
    assert spec["label"] == "Shiny 1.9"
    assert spec["summary"] == "A Shiny input changes the plotted metric."


@pytest.mark.parametrize("context", [False, {"title": ""}, {"summary": 42}, {"captures": {"diagonal": "app.png"}}])
def test_invalid_context_is_rejected(tmp_path, context):
    with pytest.raises(ValueError, match="context"):
        context_cards.resolve(tmp_path, {"context": context, "shots": [{}]})


def test_showcase_poster_has_no_opening_overlay(tmp_path):
    spec = context_cards.resolve(tmp_path, {
        "context": {"layout": "showcase", "title": "Power through the peak"},
        "shots": [{}],
    })
    Image.new("RGB", (640, 800), "#007BC2").save(tmp_path / "app.png")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        files = context_cards.render(browser, tmp_path, spec, "vertical", tmp_path / "app.png")
        assert set(files) == {"poster"}
        page = browser.new_page(viewport={"width": 720, "height": 1280})
        page.goto(files["poster"].with_suffix(".html").as_uri())
        assert page.locator("h1").inner_text() == "Power through the peak"
        evidence = page.locator("img").bounding_box()
        assert evidence and evidence["width"] >= 600
        browser.close()
