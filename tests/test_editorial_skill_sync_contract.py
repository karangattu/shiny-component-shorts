"""Shared editorial instructions must stay aligned across skill variants."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / '.agents/skills/shiny-component-shorts'
CLAUDE = ROOT / '.claude/skills/shiny-component-shorts'


def normalized(path: Path) -> str:
    return path.read_text(encoding='utf-8').replace('.claude/skills/', '.agents/skills/')


class EditorialSkillSyncTest(unittest.TestCase):
    def test_shared_editorial_references_match(self) -> None:
        for name in ('changelog-reel.md', 'editorial-production.md', 'short-form-pacing.md'):
            with self.subTest(reference=name):
                self.assertEqual(normalized(AGENTS / 'references' / name), normalized(CLAUDE / 'references' / name))

    def test_core_editorial_guidance_matches(self) -> None:
        start = 'Prefer genuine recorded app interactions'
        end = 'The three-action quota'
        for name in ('SKILL.md',):
            agent = normalized(AGENTS / name)
            claude = normalized(CLAUDE / name)
            self.assertEqual(agent[agent.index(start):agent.index(end)], claude[claude.index(start):claude.index(end)])

    def test_recording_editorial_contract_matches(self) -> None:
        start = 'New release/changelog/blog videos'
        end = 'Capture any app behavior'
        agent = normalized(AGENTS / 'references/recording-contract.md')
        claude = normalized(CLAUDE / 'references/recording-contract.md')
        self.assertEqual(agent[agent.index(start):agent.index(end)], claude[claude.index(start):claude.index(end)])
