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
                               ('episodes.yaml', 'source-shots.yaml', 'interaction-shot.yaml', 'reel.yaml')]
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
                self.assertTrue(episode['demo'])

    def test_starter_opens_on_footage_and_shows_one_highlighted_line(self) -> None:
        stills = yaml.safe_load((SKILLS[0] / STARTER / 'source-shots.yaml').read_text(encoding='utf-8'))
        self.assertEqual(stills['context']['layout'], 'showcase')
        self.assertEqual(len(stills['shots']), 1)
        for view in stills['shots'][0]['views'].values():
            self.assertIn('highlight', view['panels'][0])
        clips = yaml.safe_load((SKILLS[0] / STARTER / 'interaction-shot.yaml').read_text(encoding='utf-8'))
        self.assertEqual([s['chapter'] for s in clips['shots']],
                         ['The hook', 'The demo', 'The integration', 'The result'])
        outro = yaml.safe_load((SKILLS[0] / STARTER / 'reel.yaml').read_text(encoding='utf-8'))['outro']
        self.assertIn('py-shinywidgets/gallery', outro['link'])

    def test_skills_route_gallery_requests_to_the_episode_guide(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill.parent.parent.name):
                text = (skill / 'SKILL.md').read_text(encoding='utf-8')
                self.assertIn(REFERENCE, text)
                self.assertIn(STARTER, text)
                guide = (skill / REFERENCE).read_text(encoding='utf-8')
                for phrase in ('The hook is footage', 'Show one accessor', 'Never call a real LLM',
                               'never asks a pitch question'):
                    self.assertIn(phrase, guide)


if __name__ == '__main__':
    unittest.main()
