"""Plan each episode's look, so a long series stays cohesive without repeating one video.

A look is planned, not random at render time: it is stored in episodes.yaml, so a rerender gives
the same video. Episodes that already have a look keep it.

    python look.py assign                       # give every episode without a look one
    python look.py check                        # report neighbours that look alike
    python look.py apply <project> <episode>    # write the look into a production's files

Delete an episode's `look:` line and run `assign` to draw that look again.
"""
import argparse
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OPTIONS = {
    "captions": ["series"],
    "accent": ["#03C7E8", "#00BF7F", "#F9B928", "#66B2FF", "#F45100", "#E879F9"],
    "hook_style": ["outcome-first", "scale-lead", "two-way", "direct-action"],
    "code_theme": ["dark", "light"],
    "order": ["integration-code", "code-integration"],
    "code_side": ["left", "right"],
}


def catalog_path() -> Path:
    beside = HERE / "episodes.yaml"
    return beside if beside.is_file() else HERE / ".video-skill/assets/integration-episode-starter/episodes.yaml"


def clash(looks: list, index: int, look: dict) -> str | None:
    """Why `look` is too close to an episode near `index`, or None."""
    for distance in (1, 2):
        for other in (index - distance, index + distance):
            near = looks[other] if 0 <= other < len(looks) else None
            if not near:
                continue
            if len(OPTIONS["captions"]) > 1 and near["captions"] == look["captions"]:
                return f"caption style {look['captions']} repeats within two episodes"
            if near.get("accent") == look.get("accent"):
                return f"accent {look['accent']} repeats within two episodes"
            if distance == 1 and near.get("hook_style") == look.get("hook_style"):
                return f"hook style {look['hook_style']} repeats on adjacent episodes"
            if distance == 1 and (near["order"], near["code_theme"]) == (look["order"], look["code_theme"]):
                return "the order and the code theme both repeat"
    return None


def problems(episodes: list) -> list[str]:
    looks = [episode.get("look") for episode in episodes]
    found = []
    for index, (episode, look) in enumerate(zip(episodes, looks)):
        if not look:
            found.append(f"{episode['id']}: no look. Run look.py assign.")
        elif set(look) != set(OPTIONS) or any(look[key] not in OPTIONS[key] for key in OPTIONS):
            found.append(f"{episode['id']}: the look needs one listed value for each of {', '.join(OPTIONS)}")
        elif all(looks) and (reason := clash(looks, index, look)):
            found.append(f"{episode['id']}: {reason}")
    return found


def assign(episodes: list, seed) -> list:
    looks = [dict(episode["look"]) if episode.get("look") else None for episode in episodes]
    for index, episode in enumerate(episodes):
        if looks[index]:
            continue
        rng = random.Random(f"{seed}:{episode['id']}")
        used = {key: Counter(look[key] for look in looks if look and key in look) for key in OPTIONS}
        for attempt in range(400):
            look = {}
            for key, values in OPTIONS.items():
                low = min(used[key][value] for value in values)
                look[key] = rng.choice([v for v in values if attempt >= 200 or used[key][v] == low])
            if not clash(looks, index, look):
                break
        else:
            raise SystemExit(f"No free look for {episode['id']}: add options or change look_seed")
        looks[index] = look
    return looks


def write(path: Path, looks: dict) -> None:
    """Put one `look:` line under each episode's title. The rest of the file keeps its comments."""
    out, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("  - id: "):
            current = line.split(": ", 1)[1].strip()
        if line.startswith("    look:"):
            continue
        out.append(line)
        if line.startswith("    title:") and current in looks:
            out.append("    look: " + yaml.safe_dump(looks[current], default_flow_style=True, sort_keys=False, width=1000).strip())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def rewrite(path: Path, change) -> None:
    text = path.read_text(encoding="utf-8")
    head = "".join(line for line in text.splitlines(True) if line.startswith("#"))
    data = yaml.safe_load(text)
    change(data)
    path.write_text(head + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")


def apply(project: Path, episode: dict) -> None:
    look = episode["look"]
    accent = look.get("accent", "#03C7E8")

    def stills(data):
        for shot in data["shots"]:
            for name, view in shot["views"].items():
                view["code_theme"] = look["code_theme"]
                view["accent"] = accent
                if name == "vertical":
                    view["overlay_card"] = True
                if name == "horizontal" and len(view.get("panels", [])) == 2:
                    view["panels"].sort(key=lambda panel: (panel["kind"] == "code") != (look["code_side"] == "left"))

    rewrite(project / "source-shots.yaml", stills)
    rewrite(
        project / "reel.yaml",
        lambda data: (
            data.update(bed="default"),
            data["outro"].update(widget=episode["integration"][0]),
        ),
    )
    (project / "look.yaml").write_text(
        "# Written by look.py apply. assemble.py reads `order` and `accent`; burn captions with --style <captions>.\n"
        + yaml.safe_dump({"episode": episode["id"], **look}, sort_keys=False), encoding="utf-8")
    print(yaml.safe_dump(look, sort_keys=False).strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("assign", "check", "apply"))
    parser.add_argument("project", nargs="?")
    parser.add_argument("episode", nargs="?")
    args = parser.parse_args()
    path = catalog_path()
    catalog = yaml.safe_load(path.read_text(encoding="utf-8"))
    episodes = catalog["episodes"]
    if args.mode == "assign":
        looks = assign(episodes, catalog["look_seed"])
        write(path, {episode["id"]: look for episode, look in zip(episodes, looks)})
        episodes = yaml.safe_load(path.read_text(encoding="utf-8"))["episodes"]
    if args.mode == "apply":
        if not args.project or not args.episode:
            parser.error("apply needs a project directory and an episode id")
        (entry,) = [episode for episode in episodes if episode["id"] == args.episode]
        apply(HERE / args.project, entry)
        return
    found = problems(episodes)
    print("\n".join(found) if found else f"{len(episodes)} looks, no two neighbours alike")
    sys.exit(bool(found))


if __name__ == "__main__":
    main()
