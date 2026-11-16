"""Gallery integration episodes: the catalog and the guidance stay usable in both skill copies."""

import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [ROOT / '.claude/skills/shiny-component-shorts', ROOT / '.agents/skills/shiny-component-shorts']
STARTER = 'assets/integration-episode-starter'
REFERENCE = 'references/widget-integration-episodes.md'
KEYS = {'id', 'gallery', 'example', 'integration', 'label', 'title', 'renderers', 'accessor',
        'install', 'hook', 'demo', 'payoff', 'audience', 'complexity'}


def load_look():
    """look.py lives in the starter, outside the type checker's search path, so load it by file."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('look', SKILLS[0] / STARTER / 'look.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WidgetIntegrationContractTest(unittest.TestCase):
    def test_both_copies_carry_the_same_episode_files(self) -> None:
        names = [REFERENCE] + [f'{STARTER}/{n}' for n in
                               ('episodes.yaml', 'source-shots.yaml', 'capture.yaml', 'capture.py', 'assemble.py', 'look.py', 'reel.yaml',
                                'make_episode.py')]
        for name in names:
            with self.subTest(file=name):
                self.assertEqual((SKILLS[0] / name).read_text(encoding='utf-8'),
                                 (SKILLS[1] / name).read_text(encoding='utf-8'))

    def test_every_episode_is_complete(self) -> None:
        catalog = yaml.safe_load((SKILLS[0] / STARTER / 'episodes.yaml').read_text(encoding='utf-8'))
        episodes = catalog['episodes']
        self.assertEqual(len({e['id'] for e in episodes}), len(episodes))
        self.assertEqual([e['id'] for e in episodes[:3]], ['plotly-lasso', 'lonboard-city-map', 'k3d-terrain'])
        for episode in episodes:
            with self.subTest(episode=episode.get('id')):
                self.assertFalse(KEYS - set(episode))
                self.assertRegex(episode['gallery'], r'^(templates|showcases)/[a-z0-9-]+$')
                self.assertRegex(episode['accessor'], r'^[a-z_]+\.[a-z_]+\(.*\)$')
                self.assertTrue(episode['install'].startswith("pip install 'shinywidgets["))
                self.assertLessEqual(max(map(len, episode['install'].split())), 32)
                self.assertFalse(episode['title'].endswith('?'))
                self.assertLessEqual(len(episode['title']), 32)
                self.assertTrue(episode['demo'])

    def test_starter_opens_on_footage_and_shows_one_highlighted_line(self) -> None:
        stills = yaml.safe_load((SKILLS[0] / STARTER / 'source-shots.yaml').read_text(encoding='utf-8'))
        self.assertEqual(stills['context']['layout'], 'showcase')
        self.assertEqual(len(stills['shots']), 1)
        for view in stills['shots'][0]['views'].values():
            self.assertIn('highlight', view['panels'][0])
        self.assertFalse(stills['shots'][0]['views']['vertical']['code_wrap'])
        clips = yaml.safe_load((SKILLS[0] / STARTER / 'capture.yaml').read_text(encoding='utf-8'))
        self.assertEqual([c['name'] for c in clips['clips']], ['hook', 'demo', 'integration', 'result'])
        self.assertLessEqual(clips['clips'][0]['actions'][0]['at'], 2)
        self.assertEqual(set(clips['points']), {'vertical', 'horizontal'})
        catalog = yaml.safe_load((SKILLS[0] / STARTER / 'episodes.yaml').read_text(encoding='utf-8'))
        outro = yaml.safe_load((SKILLS[0] / STARTER / 'reel.yaml').read_text(encoding='utf-8'))['outro']
        self.assertIn('py-shinywidgets', outro['link'])
        self.assertTrue(catalog['closing_line'].startswith(outro['spoken']))
        if not catalog['released']:
            self.assertEqual(outro['command'], '')

    def test_skills_route_gallery_requests_to_the_episode_guide(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill.parent.parent.name):
                text = (skill / 'SKILL.md').read_text(encoding='utf-8')
                self.assertIn(REFERENCE, text)
                self.assertIn(STARTER, text)
                guide = (skill / REFERENCE).read_text(encoding='utf-8')
                for phrase in ('The hook is footage', 'Show one accessor', 'Never call a real LLM',
                               'never asks a pitch question', 'speak the closing line', '--stop-at'):
                    self.assertIn(phrase, guide)

    def test_every_episode_has_a_planned_look_unlike_its_neighbours(self) -> None:
        import copy, sys
        look = load_look()
        catalog = yaml.safe_load((SKILLS[0] / STARTER / 'episodes.yaml').read_text(encoding='utf-8'))
        episodes = catalog['episodes']
        self.assertEqual(look.problems(episodes), [])
        # The stored looks are what the seed draws, so the catalog can be rebuilt.
        self.assertEqual(look.assign(episodes, catalog['look_seed']), [e['look'] for e in episodes])
        for key in ('captions', 'code_theme', 'order', 'code_side'):
            self.assertEqual({e['look'][key] for e in episodes}, set(look.OPTIONS[key]))
        # A new episode draws a look that fits, and the older looks stay.
        more = copy.deepcopy(episodes) + [{'id': f'extra-{n}'} for n in range(17)]
        looks = look.assign(more, catalog['look_seed'])
        self.assertEqual(looks[:len(episodes)], [e['look'] for e in episodes])
        self.assertEqual(look.problems([{'id': str(n), 'look': one} for n, one in enumerate(looks)]), [])
        twin = copy.deepcopy(episodes)
        twin[1]['look'] = dict(twin[0]['look'])
        self.assertTrue(look.problems(twin))

    def test_a_look_is_applied_to_the_production_files(self) -> None:
        import shutil, sys, tempfile
        look = load_look()
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('source-shots.yaml', 'reel.yaml'):
                shutil.copy(SKILLS[0] / STARTER / name, tmp)
            wanted = {'captions': 'bar', 'code_theme': 'light', 'order': 'code-integration',
                      'code_side': 'right'}
            look.apply(Path(tmp), {'id': 'x', 'look': wanted, 'integration': ['K3D', 'NumPy']})
            views = yaml.safe_load((Path(tmp) / 'source-shots.yaml').read_text())['shots'][0]['views']
            self.assertEqual({v['code_theme'] for v in views.values()}, {'light'})
            self.assertEqual([p['kind'] for p in views['horizontal']['panels']], ['image', 'code'])
            self.assertEqual(yaml.safe_load((Path(tmp) / 'reel.yaml').read_text())['outro']['widget'], 'K3D')
            self.assertEqual(yaml.safe_load((Path(tmp) / 'look.yaml').read_text())['order'], 'code-integration')


class SpokenEndCardTest(unittest.TestCase):
    def test_captions_stop_before_the_closing_line_and_keep_short_words(self) -> None:
        import sys
        sys.path.insert(0, str(SKILLS[0] / 'scripts'))
        import burn_captions
        words = [{'word': w} for w in 'I draw a box. To try this integration, go'.split()]
        kept = burn_captions.words_before(words, 'To try this')
        self.assertEqual([w['word'] for w in kept], ['I', 'draw', 'a', 'box.'])
        with self.assertRaises(SystemExit):
            burn_captions.words_before(words, 'not spoken')

    def test_the_last_caption_stops_on_the_first_word_of_the_closing_line(self) -> None:
        import sys, tempfile
        sys.path.insert(0, str(SKILLS[0] / 'scripts'))
        import burn_captions
        words = [{'word': 'I', 'start': 0.0, 'end': 0.2},
                 {'word': 'draw', 'start': 0.2, 'end': 0.9},
                 {'word': 'To', 'start': 1.0, 'end': 1.2},
                 {'word': 'try', 'start': 1.2, 'end': 1.4}]
        stop = burn_captions.phrase_index(words, 'To try')
        self.assertEqual(stop, 2)
        phrases = burn_captions.group_phrases(words[:stop])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'captions.ass'
            cues = burn_captions.write_ass(
                phrases, 0.0, burn_captions.STYLES['clean'], path, float(words[stop]['start']))
            self.assertEqual(cues[-1][1], 1.0)
            self.assertIn('0:00:01.00', path.read_text(encoding='utf-8'))

    def test_a_second_pointer_arrow_stops_the_recording(self) -> None:
        import sys
        sys.path.insert(0, str(SKILLS[0] / 'scripts'))
        import record_demo

        class Frame:
            def __init__(self, shown): self.shown = shown
            def evaluate(self, _):
                if self.shown is None:
                    raise RuntimeError('detached')
                return self.shown

        class Page:
            def __init__(self, *shown): self.frames = [Frame(s) for s in shown]

        record_demo.assert_one_cursor(Page(True, False, None))
        with self.assertRaises(RuntimeError):
            record_demo.assert_one_cursor(Page(True, True))
        # The overlay hides its arrow while the pointer is over another document.
        self.assertIn("addEventListener('mouseleave', hide)", record_demo.CURSOR_OVERLAY_JS)
        self.assertIn("framed(event) ? '0' : '1'", record_demo.CURSOR_OVERLAY_JS)
        for skill in SKILLS:
            capture = (skill / STARTER / 'capture.py').read_text(encoding='utf-8')
            self.assertGreaterEqual(capture.count('assert_one_cursor'), 2)
            self.assertIn('assert_one_cursor', (skill / 'scripts/record_demo.py').read_text(encoding='utf-8'))

    def test_every_boxed_caption_style_draws_its_box(self) -> None:
        import sys
        sys.path.insert(0, str(SKILLS[0] / 'scripts'))
        import burn_captions
        for name, style in burn_captions.STYLES.items():
            if style['border_style'] == 3:
                with self.subTest(style=name):
                    # &HAABBGGRR: alpha FF is transparent, and white text then has nothing behind it.
                    self.assertLess(int(style['outline'][2:4], 16), 0x80)
                    self.assertNotEqual(style['outline'][4:], style['primary'][4:])


class CaptureStarterTest(unittest.TestCase):
    """Episode capture opts into browser flags and warns about idle footage."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "episode_capture", SKILLS[0] / STARTER / "capture.py")
        assert spec and spec.loader
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_browser_args_are_forwarded_to_chromium(self):
        source = (SKILLS[0] / STARTER / "capture.py").read_text(encoding='utf-8')
        self.assertIn('*config.get("browser_args", [])', source)

    def test_webgpu_check_reports_a_blank_canvas(self):
        class Page:
            def __init__(self, result):
                self.result = result

            def evaluate(self, _):
                return self.result

        config = {"browser_args": ["--enable-unsafe-webgpu", "--use-angle=metal"]}
        with self.assertRaisesRegex(ValueError, "WebGPU"):
            self.module.check_webgpu(Page({"adapter": False, "notice": False}), config)
        with self.assertRaisesRegex(ValueError, "WebGPU"):
            self.module.check_webgpu(Page({"adapter": True, "notice": True}), config)
        self.module.check_webgpu(Page({"adapter": True, "notice": False}), config)
        self.module.check_webgpu(Page({"adapter": False, "notice": False}), {})

    def test_long_hold_warnings_skip_result_shots(self):
        config = {"clips": [
            {"name": "hook", "cue": "I box", "end": "Every dot", "actions": [{"at": 1.0}]},
            {"name": "result", "cue": "This app", "actions": []},
        ]}
        spoken = {"I box": 0.0, "Every dot": 12.0, "This app": 20.0}
        warnings = self.module.long_hold_warnings(config, spoken, 30.0)
        self.assertTrue(any("hook" in warning and "after the last action" in warning for warning in warnings))
        self.assertFalse(any("result" in warning for warning in warnings))
        spoken = {"I box": 0.0, "Every dot": 4.0, "This app": 20.0}
        self.assertEqual(self.module.long_hold_warnings(config, spoken, 30.0), [])


class MakeEpisodeTest(unittest.TestCase):
    """The py-shiny scaffolder drafts from a gallery clone but never guesses from a link."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_episode", SKILLS[0] / STARTER / "make_episode.py")
        assert spec and spec.loader
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "py-shinywidgets"
        example = self.repo / "website/gallery/templates/fake-example"
        example.mkdir(parents=True)
        (example / "app.py").write_text(
            "from shiny.express import render\n\n"
            "@render_embedding_atlas\n"
            "def atlas():\n"
            "    return EmbeddingAtlasWidget(df, x=X, y=Y)\n\n"
            "@render.text\n"
            "def stat():\n"
            "    where = atlas.predicate()\n"
            "    return f'{where} and a long enough line to need smart wrapping in a narrow card'\n"
        )
        (example / "index.md").write_text(
            "---\ntitle: Fake explorer\nwidgets: [embedding-atlas]\n"
            "summary: Brush the map and the table keeps those rows.\n"
            "pattern: brush -> table\n---\n\n# Fake\n"
        )
        (example / "requirements.txt").write_text("shinywidgets[embedding_atlas]\nduckdb\n")
        widget = self.repo / "website/widgets/embedding-atlas"
        widget.mkdir(parents=True)
        (widget / "index.md").write_text("---\ntitle: Embedding Atlas\n---\n")

    def test_gallery_front_matter_produces_a_reviewable_draft(self):
        project = self.root / "episode"
        self.assertEqual(self.module.main([
            "--project-dir", str(project),
            "--gallery", "templates/fake-example",
            "--repo", str(self.repo),
            "--url", "https://posit-dev.github.io/py-shinywidgets/gallery/templates/fake-example/",
        ]), 0)
        for name in ("app.py", "requirements.txt", "capture.yaml", "reel.yaml",
                     "capture.py", "assemble.py", "look.py", "tts-settings.json",
                     "episode.yaml", "episodes.yaml", "source-shots.yaml", "PRODUCTION.md"):
            with self.subTest(file=name):
                self.assertTrue((project / name).is_file())
        entry = yaml.safe_load((project / "episode.yaml").read_text())
        self.assertEqual(entry["id"], "fake-example")
        self.assertEqual(entry["title"], "Fake explorer")
        self.assertEqual(entry["accessor"], "atlas.predicate()")
        self.assertEqual(entry["renderers"], ["render_embedding_atlas", "render_text"])
        self.assertIn("duckdb", entry["install"])
        self.assertIn("index.md", entry["notes"])
        outro = yaml.safe_load((project / "reel.yaml").read_text())["outro"]
        self.assertEqual(outro["widget"], "Embedding Atlas")
        views = yaml.safe_load((project / "source-shots.yaml").read_text())["shots"][0]["views"]
        panel = views["vertical"]["panels"][0]
        self.assertEqual(panel["highlight"], 9)
        self.assertEqual(panel["lines"], [8, 10])
        self.assertEqual(views["vertical"]["code_wrap"], "smart")
        catalog = yaml.safe_load((project / "episodes.yaml").read_text())
        self.assertEqual(len(catalog["episodes"]), 1)
        look = load_look()
        assigned = look.assign(catalog["episodes"], catalog["look_seed"])
        self.assertEqual(len(assigned), 1)
        self.assertEqual(look.problems([{"id": "fake-example", "look": assigned[0]}]), [])

    def test_component_or_link_input_does_not_invent_metadata(self):
        project = self.root / "linked"
        self.assertEqual(self.module.main([
            "--project-dir", str(project),
            "--url", "https://posit-dev.github.io/py-shinywidgets/widgets/plotly/",
            "--title", "Plotly in Shiny",
        ]), 0)
        entry = yaml.safe_load((project / "episode.yaml").read_text())
        self.assertTrue(entry["gallery"].startswith("TODO"))
        self.assertTrue(entry["accessor"].startswith("TODO"))
        self.assertIn("component", entry["notes"])
        self.assertFalse((project / "app.py").exists())
        self.assertIn("TODO", (project / "PRODUCTION.md").read_text())

    def test_existing_production_is_preserved_without_force(self):
        project = self.root / "kept"
        project.mkdir()
        (project / "notes.txt").write_text("my work")
        with self.assertRaisesRegex(SystemExit, "not empty"):
            self.module.main(["--project-dir", str(project), "--gallery", "templates/fake-example",
                              "--repo", str(self.repo)])
        self.assertEqual((project / "notes.txt").read_text(), "my work")


if __name__ == '__main__':
    unittest.main()
