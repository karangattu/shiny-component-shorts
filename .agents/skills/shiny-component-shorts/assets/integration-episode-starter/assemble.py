"""Place recorded clips around the code still or attach the floating code card to live footage.

Rerun after prepare_editorial.py. With `outro.spoken` in reel.yaml, renders the end card and adds
it as the last shot cued on that phrase.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
import yaml

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in (HERE, *HERE.parents) if (p / ".video-skill/scripts").is_dir()), HERE)
sys.path.insert(0, str(ROOT / ".video-skill/scripts"))
import end_card  # noqa: E402
from context_cards import orientations  # noqa: E402

arg = Path(sys.argv[1])
project = arg if arg.is_absolute() or (arg / "editorial.yaml").is_file() else ROOT / sys.argv[1]
path = project / "editorial.yaml"
editorial = yaml.safe_load(path.read_text())
assert editorial.pop("generated_by") == "prepare_editorial.py"
(still,) = editorial["shots"]
capture_cfg = yaml.safe_load((project / "capture.yaml").read_text())
clips = capture_cfg["clips"]
if project.name != "lonboard-city-map" and any(c.get("chapter") == "World city explorer" for c in clips):
    raise ValueError("Replace starter 'World city explorer' chapter title with this app's example name")

views = orientations(editorial)
look_path = project / "look.yaml"
look_data = yaml.safe_load(look_path.read_text()) if look_path.is_file() else {}
order = look_data.get("order", "integration-code")
accent = look_data.get("accent", "#03C7E8")
default_code_pos = capture_cfg.get("code_position", "bottom")

shots = []
has_code_clip = False
for clip in clips:
    is_code_clip = bool(clip.get("code_overlay") or clip["name"] == "code")
    has_code_clip |= is_code_clip
    shot_views = {}
    for view in views:
        v = {"file": f'sources/{clip["name"]}-{view}.mp4', "in": 0, "fit": "contain"}
        if is_code_clip:
            still_view = still["views"][view]
            if view == "vertical" and still_view.get("card_file"):
                v["code_overlay"] = still_view["card_file"]
                v["code_position"] = clip.get("code_position", default_code_pos)
            else:
                v = still_view
        shot_views[view] = v
    shots.append({"cue": clip["cue"], "chapter": clip["chapter"], "views": shot_views})

if has_code_clip:
    editorial["shots"] = shots
else:
    at = [clip["name"] for clip in clips].index("integration") if order == "code-integration" else len(shots) - 1
    editorial["shots"] = shots[:at] + [still] + shots[at:]

ctx = editorial.setdefault("context", {})
if ctx.get("hook_badge") is False:
    ctx.pop("hook_badge", None)
elif isinstance(ctx.get("hook_badge"), dict):
    ctx["hook_badge"].setdefault("accent", accent)
else:
    short_label = str(ctx.get("label", "Shiny")).replace("Shiny for Python · ", "Shiny · ")
    ctx["hook_badge"] = {"label": short_label, "title": str(ctx.get("title", "")), "accent": accent, "seconds": 2.8}

card = end_card.resolve(yaml.safe_load((project / "reel.yaml").read_text()).get("outro"))
if card and card["spoken"]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for view in views:
            end_card.render(browser, card, view, project / "sources" / f"end-card-{view}.png", 2)
        browser.close()
    editorial["shots"].append({"cue": card["spoken"], "chapter": card["title"], "views": {
        view: {"file": f"sources/end-card-{view}.png", "fit": "contain"} for view in views}})

ends = {id(shot): clip.get("end") for shot, clip in zip(shots, clips)}
for shot, after in zip(editorial["shots"], editorial["shots"][1:]):
    cue = after["cue"]["phrase"] if isinstance(after["cue"], dict) else after["cue"]
    end = ends.get(id(shot)) or cue
    assert cue.startswith(end) or end.startswith(cue), f'A clip ends on "{end}" but the next shot starts on "{cue}"'
path.write_text(yaml.safe_dump(editorial, sort_keys=False, allow_unicode=True))
