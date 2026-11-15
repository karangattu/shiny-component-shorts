"""Place the recorded clips around the built code still. Rerun after prepare_editorial.py.

With `outro.spoken` in reel.yaml, this also renders the end card and adds it as the last shot,
cued on that phrase, so the narration speaks over it.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".video-skill/scripts"))
import end_card

project = ROOT / sys.argv[1]
path = project / "editorial.yaml"
editorial = yaml.safe_load(path.read_text())
assert editorial.pop("generated_by") == "prepare_editorial.py"
(still,) = editorial["shots"]
clips = yaml.safe_load((project / "capture.yaml").read_text())["clips"]
views = ("vertical", "horizontal")
shots = [{"cue": clip["cue"], "chapter": clip["chapter"], "views": {
    view: {"file": f'sources/{clip["name"]}-{view}.mp4', "in": 0, "fit": "contain"}
    for view in views}} for clip in clips]
# The code still sits before the last clip, so the video returns to the app.
editorial["shots"] = shots[:-1] + [still] + shots[-1:]

card = end_card.resolve(yaml.safe_load((project / "reel.yaml").read_text()).get("outro"))
if card and card["spoken"]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for view in views:
            end_card.render(browser, card, view, project / "sources" / f"end-card-{view}.png", 2)
        browser.close()
    editorial["shots"].append({"cue": card["spoken"], "chapter": card["title"], "views": {
        view: {"file": f"sources/end-card-{view}.png", "fit": "contain"} for view in views}})
path.write_text(yaml.safe_dump(editorial, sort_keys=False, allow_unicode=True))
