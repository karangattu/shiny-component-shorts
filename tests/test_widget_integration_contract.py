"""Gallery integration episodes: the catalog and the guidance stay usable in both skill copies."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = [ROOT / '.claude/skills/shiny-component-shorts', ROOT / '.agents/skills/shiny-component-shorts']
STARTER = 'assets/integration-episode-starter'
REFERENCE = 'references/widget-integration-episodes.md'
KEYS = {'id', 'gallery', 'example', 'integration', 'label', 'title', 'renderers', 'accessor',
        'install', 'hook', 'demo', 'payoff', 'audience', 'complexity'}


class WidgetIntegrationContractTest(unittest.TestCase):
    def test_both_copies_carry_the_same_episode_files(self) -> None:
        names = [REFERENCE] + [f'{STARTER}/{n}' for n in
                               ('episodes.yaml', 'source-shots.yaml', 'capture.yaml', 'capture.py', 'assemble.py', 'look.py', 'reel.yaml')]
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
        sys.path.insert(0, str(SKILLS[0] / STARTER))
        import look
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
        sys.path.insert(0, str(SKILLS[0] / STARTER))
        import look
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('source-shots.yaml', 'reel.yaml'):
                shutil.copy(SKILLS[0] / STARTER / name, tmp)
            wanted = {'captions': 'bar', 'code_theme': 'light', 'order': 'code-integration',
                      'code_side': 'right', 'card_title': 'Run this app yourself'}
            look.apply(Path(tmp), {'id': 'x', 'look': wanted})
            views = yaml.safe_load((Path(tmp) / 'source-shots.yaml').read_text())['shots'][0]['views']
            self.assertEqual({v['code_theme'] for v in views.values()}, {'light'})
            self.assertEqual([p['kind'] for p in views['horizontal']['panels']], ['image', 'code'])
            self.assertEqual(yaml.safe_load((Path(tmp) / 'reel.yaml').read_text())['outro']['title'], 'Run this app yourself')
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


if __name__ == '__main__':
    unittest.main()
