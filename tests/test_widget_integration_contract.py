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
                               ('episodes.yaml', 'source-shots.yaml', 'capture.yaml', 'capture.py', 'assemble.py', 'reel.yaml')]
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


if __name__ == '__main__':
    unittest.main()
