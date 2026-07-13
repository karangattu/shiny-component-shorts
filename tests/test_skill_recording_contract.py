from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CODEX_SKILL = ROOT / ".agents/skills/shiny-component-shorts/SKILL.md"
CLAUDE_SKILL = ROOT / ".claude/skills/shiny-component-shorts/SKILL.md"


class RecordingContractTest(unittest.TestCase):
    def test_claude_and_codex_require_a_human_style_cursor(self) -> None:
        codex = CODEX_SKILL.read_text(encoding="utf-8")
        claude = CLAUDE_SKILL.read_text(encoding="utf-8")

        self.assertEqual(codex, claude)
        for marker in (
            "### Show a human-style cursor",
            "CURSOR_OVERLAY_JS",
            "def move_cursor_to",
            "def human_click",
            "context.add_init_script(CURSOR_OVERLAY_JS)",
            'human_click(page, action["click"])',
            'move_cursor_to(page, sel["selector"])',
        ):
            self.assertIn(marker, codex)


if __name__ == "__main__":
    unittest.main()
