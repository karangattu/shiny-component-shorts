"""Widget showcases stay app-led, specific, and focused on one visible behavior."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [ROOT / folder / "skills/shiny-component-shorts" for folder in (".agents", ".claude")]
STARTER = "assets/widget-starter"
FILES = [
    "README.md",
    "app.py",
    "app.css",
    "setup.sh",
    "actions.yaml",
    "source-shots.yaml",
    "interaction-shot.yaml",
    "reel.yaml",
    "tts-settings.json",
    "narration.txt",
]
sys.path.insert(0, str(SKILLS[0] / "scripts"))
import check_narration_voice  # noqa: E402
import prepare_editorial  # noqa: E402
import validate_demo  # noqa: E402


class WidgetShowcaseContractTest(unittest.TestCase):
    def test_both_skill_copies_carry_the_same_runnable_starter(self) -> None:
        for name in FILES:
            with self.subTest(file=name):
                self.assertEqual(
                    (SKILLS[0] / STARTER / name).read_text(encoding="utf-8"),
                    (SKILLS[1] / STARTER / name).read_text(encoding="utf-8"),
                )

    def test_starter_proves_one_behavior_with_a_real_in_place_update(self) -> None:
        app = (SKILLS[0] / STARTER / "app.py").read_text(encoding="utf-8")
        self.assertIn("go.FigureWidget", app)
        self.assertIn("@reactive.effect", app)
        self.assertIn("trace.y = y", app)
        css = (SKILLS[0] / STARTER / "app.css").read_text(encoding="utf-8")
        self.assertIn(".js-plotly-plot .modebar", css)
        self.assertIn("display: none", css)
        self.assertNotIn("return go.Figure()", app)

        shots = yaml.safe_load((SKILLS[0] / STARTER / "source-shots.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(shots["shots"]), 2)
        self.assertEqual(shots["context"]["title"], "Update a chart in place")
        code_panels = [
            panel
            for shot in shots["shots"]
            for view in shot["views"].values()
            for panel in view["panels"]
            if panel["kind"] == "code" and panel.get("file") == "app.py"
        ]
        self.assertEqual(len({tuple(panel["lines"]) for panel in code_panels}), 1)
        panel = code_panels[0]
        self.assertEqual(panel["lines"], [50, 58])
        self.assertEqual(panel["highlight"], 58)
        lines = app.splitlines()
        self.assertEqual(lines[panel["highlight"] - 1].strip(), "trace.y = y")

    def test_every_cue_quotes_the_finished_transcript(self) -> None:
        narration = (SKILLS[0] / STARTER / "narration.txt").read_text(encoding="utf-8")
        transcript = check_narration_voice.transcript_of(narration)
        self.assertIsNotNone(transcript)
        spoken = " ".join((transcript or "").casefold().split())
        cues = []
        for name in ("actions.yaml", "source-shots.yaml", "interaction-shot.yaml"):
            config = yaml.safe_load((SKILLS[0] / STARTER / name).read_text(encoding="utf-8"))
            items = config["actions"] if name == "actions.yaml" else config["shots"]
            cues.extend(item["cue"] for item in items if item.get("cue"))
        self.assertGreaterEqual(len(cues), 6)
        for cue in cues:
            with self.subTest(cue=cue):
                self.assertIn(" ".join(cue.casefold().split()), spoken)

    def test_starter_stills_fit_both_orientations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for name in ("app.py", "app.css", "setup.sh", "source-shots.yaml"):
                shutil.copy2(SKILLS[0] / STARTER / name, project / name)
            sources = project / "sources"
            sources.mkdir()
            for name in ("result-vertical.png", "result-horizontal.png", "app-horizontal-code.png"):
                Image.new("RGB", (720, 900), "#FFFFFF").save(sources / name)
            result = prepare_editorial.prepare(project)
            self.assertEqual(len(result["shots"]), 2)
            for orientation in ("vertical", "horizontal"):
                for shot in result["shots"]:
                    self.assertGreater((project / shot["views"][orientation]["file"]).stat().st_size, 0)

    def test_narration_is_short_conversational_and_focused(self) -> None:
        path = SKILLS[0] / STARTER / "narration.txt"
        narration = path.read_text(encoding="utf-8")
        self.assertEqual(check_narration_voice.voice_problems(narration), [])
        words, tags, seconds = validate_demo.narration_metrics(path)
        self.assertGreaterEqual(words, 85)
        self.assertLessEqual(words, 115)
        self.assertGreaterEqual(tags, 3)
        self.assertLessEqual(tags, 4)
        self.assertGreaterEqual(seconds, 38)
        self.assertLessEqual(seconds, 55)
        transcript = check_narration_voice.transcript_of(narration) or ""
        for phrase in ("You need three packages", "the imports are short", "Each channel gets a bar trace"):
            self.assertNotIn(phrase, transcript)
        self.assertIn("update the existing figure", transcript)

    def test_actions_show_the_real_widget_response(self) -> None:
        config = yaml.safe_load((SKILLS[0] / STARTER / "actions.yaml").read_text(encoding="utf-8"))
        actions = config["actions"]
        self.assertEqual(sum("click" in action for action in actions), 2)
        self.assertEqual(sum("hover" in action for action in actions), 1)
        self.assertTrue(any("wait_stream" in action for action in actions))
        self.assertEqual(actions[-1]["screenshot"]["path"], "artifacts/final.png")
        for index, action in enumerate(actions):
            if any(key in action for key in ("click", "hover")):
                self.assertIn("cue", actions[index - 1])

    def test_end_card_and_cover_name_the_specific_result(self) -> None:
        reel = yaml.safe_load((SKILLS[0] / STARTER / "reel.yaml").read_text(encoding="utf-8"))
        self.assertEqual(reel["title"], "Update a Plotly chart in place")
        self.assertEqual(reel["outro"]["widget"], "Plotly")
        self.assertEqual(reel["outro"]["command"], "pip install shiny shinywidgets plotly")
        setup = (SKILLS[0] / STARTER / "setup.sh").read_text(encoding="utf-8")
        self.assertTrue(all(len(line) <= 32 for line in setup.splitlines()))
        shots = yaml.safe_load((SKILLS[0] / STARTER / "source-shots.yaml").read_text(encoding="utf-8"))
        self.assertEqual(shots["context"]["layout"], "showcase")
        self.assertNotEqual(shots["context"]["title"], "Plotly in Shiny")

    def test_guidance_requires_a_human_task_not_a_package_tour(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill):
                guide = (skill / "references/widget-showcases.md").read_text(encoding="utf-8")
                for phrase in (
                    "one hidden behavior",
                    "Open on the visible consequence",
                    "Keep the app moving",
                    "one short source excerpt",
                    "Listen to the finished take",
                ):
                    self.assertIn(phrase, guide)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("45-second narrated Plotly showcase", readme)
        self.assertNotIn("75-second narrated Plotly showcase", readme)


if __name__ == "__main__":
    unittest.main()
