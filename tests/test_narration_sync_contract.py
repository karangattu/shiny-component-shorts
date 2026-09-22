"""Word timing, phrase cues, capture, and take scoring stay in sync across both skill copies."""

from __future__ import annotations

import importlib.util
import random
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COPIES = {
    "claude": ROOT / ".claude/skills/shiny-component-shorts/scripts",
    "agents": ROOT / ".agents/skills/shiny-component-shorts/scripts",
}


def load(copy: str, name: str) -> Any:
    """Load one copy's script with its own sibling modules on the path."""
    scripts = COPIES[copy]
    sys.path.insert(0, str(scripts))
    try:
        for sibling in ("align_narration", "validate_demo", "merge_audio"):
            sys.modules.pop(sibling, None)
        spec = importlib.util.spec_from_file_location(f"{copy}_{name}", scripts / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def heard(*words: tuple[str, float, float]) -> list[dict]:
    return [{"word": word, "start": start, "end": end} for word, start, end in words]


class NarrationAlignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.copies = {copy: load(copy, "align_narration") for copy in COPIES}

    def test_both_copies_share_one_alignment_module(self) -> None:
        self.assertEqual(
            (COPIES["claude"] / "align_narration.py").read_text(encoding="utf-8"),
            (COPIES["agents"] / "align_narration.py").read_text(encoding="utf-8"),
        )

    def test_spoken_numbers_and_symbols_compare_fairly(self) -> None:
        align = self.copies["claude"]
        self.assertEqual(align.normalize_tokens("Region 8 of 8 into 92%?"),
                         ["region", "eight", "of", "eight", "into", "ninety", "two", "percent"])
        self.assertEqual(align.normalize_tokens("ninety-two percent"), ["ninety", "two", "percent"])
        self.assertEqual(align.normalize_tokens("Shiny's ui.Progress 1.5"),
                         ["shinys", "ui", "progress", "one", "point", "five"])
        self.assertEqual(align.number_words(1250), ["one", "thousand", "two", "hundred", "fifty"])

    def test_alignment_times_every_word_and_reports_differences(self) -> None:
        align = self.copies["claude"]
        spoken = "Switch to seven days. The chart redraws."
        result = align.align(
            spoken,
            heard(("Switch", 0.2, 0.5), ("to", 0.5, 0.6), ("7", 0.6, 0.9), ("days.", 0.9, 1.3),
                  ("The", 2.0, 2.1), ("card", 2.1, 2.4), ("redraws.", 2.4, 3.0)),
            duration=3.5,
        )
        words = {word["word"]: word for word in result["words"]}
        self.assertEqual(words["seven"]["start"], 0.6)
        self.assertTrue(words["seven"]["matched"])
        self.assertFalse(words["chart"]["matched"])  # heard "card"
        self.assertEqual(words["chart"]["start"], 2.1)
        self.assertAlmostEqual(result["word_error_rate"], round(1 / 7, 3))
        self.assertEqual(result["differences"], [{"expected": "chart", "heard": "card", "at": 2.1}])
        self.assertEqual([s["start"] for s in result["sentences"]], [0.2, 2.0])
        self.assertEqual(result["sentences"][1]["end"], 3.0)

    def test_unheard_words_are_interpolated_between_neighbours(self) -> None:
        align = self.copies["claude"]
        result = align.align("one two three four", heard(("one", 0.0, 0.4), ("four", 1.6, 2.0)), 2.0)
        starts = [word["start"] for word in result["words"]]
        self.assertEqual(starts, [0.0, 0.4, 1.0, 1.6])
        self.assertAlmostEqual(result["word_error_rate"], 0.5)

    def test_phrase_lookup_supports_repeats_and_explains_misses(self) -> None:
        align = self.copies["claude"]
        words = align.align("Run it. Run it again.", heard(
            ("Run", 0.0, 0.3), ("it.", 0.3, 0.5), ("Run", 1.0, 1.3), ("it", 1.3, 1.5), ("again.", 1.5, 2.0)
        ), 2.0)["words"]
        self.assertEqual(align.find_phrase(words, "run it")["start"], 0.0)
        self.assertEqual(align.find_phrase(words, "Run it,", occurrence=2)["start"], 1.0)
        with self.assertRaisesRegex(ValueError, "only 2 time"):
            align.find_phrase(words, "run it", occurrence=3)
        with self.assertRaisesRegex(ValueError, "nowhere"):
            align.find_phrase(words, "seven days")

    def test_stale_or_silence_only_timing_is_not_trusted(self) -> None:
        align = self.copies["claude"]
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            artifacts = project / "artifacts"
            artifacts.mkdir()
            (artifacts / "narration.wav").write_bytes(b"take one")
            timing = artifacts / "narration-timing.json"
            timing.write_text('{"sentence_windows": []}', encoding="utf-8")
            self.assertIsNone(align.load_timing(project))
            digest = align.sha256(artifacts / "narration.wav")
            timing.write_text(f'{{"audio_sha256": "{digest}", "words": [{{"word": "x"}}]}}',
                              encoding="utf-8")
            self.assertIsNotNone(align.load_timing(project))
            (artifacts / "narration.wav").write_bytes(b"take two")
            self.assertIsNone(align.load_timing(project))

    def test_transcript_check_blocks_wrong_or_vocalized_takes(self) -> None:
        align = self.copies["claude"]
        clean = {"transcript_check": {"word_error_rate": 0.05, "vocalizations": []}}
        self.assertEqual(align.check_problems(clean), [])
        wrong = {"transcript_check": {"word_error_rate": 0.4, "vocalizations": ["(laughs)"]}}
        problems = align.check_problems(wrong)
        self.assertEqual(len(problems), 2)
        self.assertIn("40%", problems[0])
        self.assertTrue(align.VOCALIZATION_RE.search("that is great (laughs) okay"))
        self.assertIsNone(align.VOCALIZATION_RE.search("Shiny redraws the chart"))


class CueContractTest(unittest.TestCase):
    def test_cues_must_directly_precede_a_visible_action(self) -> None:
        for copy in COPIES:
            validator = load(copy, "validate_demo")
            ok = [{"cue": "seven days"}, {"click": "#seven"}, {"cue": {"at": 4.0}}, {"code": {"text": "x"}}]
            self.assertEqual(validator.cue_problems(ok), [], copy)
            bad = [{"cue": "seven days"}, {"wait": 500}, {"click": "#seven"}, {"cue": ""}]
            problems = validator.cue_problems(bad)
            self.assertEqual(len(problems), 2, copy)
            self.assertIn("followed directly", problems[0])

    def test_cue_times_resolve_to_video_time_and_need_word_timing(self) -> None:
        validator = load("claude", "validate_demo")
        timing = {"words": [{"word": "seven", "start": 3.0, "end": 3.3, "sentence": 0},
                            {"word": "days", "start": 3.3, "end": 3.7, "sentence": 0}]}
        actions = [{"cue": "Seven days"}, {"click": "#s"}, {"cue": {"at": 9.5}}, {"code": {}}]
        cues = validator.resolve_cue_times(actions, timing)
        self.assertEqual(cues[0]["target"], 3.15)
        self.assertEqual(cues[2]["target"], 9.65)
        with self.assertRaisesRegex(ValueError, "align_narration"):
            validator.resolve_cue_times(actions, None)

    def test_cued_reactions_are_held_to_their_phrase(self) -> None:
        validator = load("claude", "validate_demo")
        actions = [{"cue": "a"}, {"click": "#a"}, {"cue": "b"}, {"click": "#b"},
                   {"cue": "c"}, {"hover": "#c"}, {"cue": "d"}, {"code": {}}]
        timeline = [
            {"action": "click", "start": 1.0, "reaction": 2.0, "cue": {"phrase": "a", "target": 2.1}},
            {"action": "click", "start": 3.0, "reaction": 5.9, "cue": {"phrase": "b", "target": 5.0}},
            {"action": "hover", "start": 6.0, "reaction": 6.4, "cue": {"phrase": "c", "target": 8.0}},
            {"action": "code", "start": 9.0, "reaction": 9.0, "cue": {"phrase": "d", "target": 9.0}},
        ]
        errors = validator.cue_timing_errors(timeline, actions, require_cues=True)
        self.assertEqual(len(errors), 2)
        self.assertIn("+0.90s", errors[0])
        self.assertIn("-1.60s", errors[1])
        unanchored = [{"click": "#a"}, {"click": "#b"}, {"click": "#c"}, {"code": {}}]
        errors = validator.cue_timing_errors([], unanchored, require_cues=True)
        self.assertTrue(any("at least 3" in error for error in errors))
        self.assertTrue(any("code action" in error for error in errors))

    def test_simulated_cues_hold_actions_until_their_phrase(self) -> None:
        validator = load("claude", "validate_demo")
        actions = [{"wait": 500}, {"cue": "x"}, {"click": "#a"}, {"cue": "y"}, {"code": {"text": "x"}}]
        cues = {1: {"phrase": "x", "target": 6.0}, 3: {"phrase": "y", "target": 12.0}}
        timeline = validator.project_simulated_timeline(actions, cues)
        click = next(entry for entry in timeline if entry["action"] == "click")
        code = next(entry for entry in timeline if entry["action"] == "code")
        self.assertEqual((click["start"], click["reaction"]), (5.4, 6.0))
        self.assertEqual((code["start"], code["reaction"]), (12.0, 12.0))


class RecorderMotionAndCaptureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.recorders = {copy: load(copy, "record_demo") for copy in COPIES}

    def test_travel_time_grows_with_distance_and_caps(self) -> None:
        recorder = self.recorders["claude"]
        self.assertLess(recorder.glide_duration_ms(50), recorder.glide_duration_ms(400))
        self.assertEqual(recorder.glide_duration_ms(5000), 950.0)

    def test_typing_rhythm_varies_but_keeps_its_average_pace(self) -> None:
        recorder = self.recorders["claude"]
        random.seed(7)
        text = "Standup notes: demo the resize, then ship it." * 4
        pauses = [recorder.typing_pause_ms(char, 45) for char in text]
        self.assertGreater(max(pauses) - min(pauses), 45)
        self.assertAlmostEqual(sum(pauses) / len(pauses), 45, delta=45 * 0.2)
        self.assertGreater(recorder.typing_pause_ms(".", 45), 0)

    def test_screencast_manifest_holds_each_frame_until_the_next(self) -> None:
        for copy, recorder in self.recorders.items():
            frames = [(100.0, Path("/f/0.jpg")), (104.5, Path("/f/1.jpg")),
                      (105.0, Path("/f/2.jpg")), (111.0, Path("/f/3.jpg"))]
            manifest = recorder.screencast_manifest(frames, start=104.0, end=106.0).splitlines()
            self.assertEqual(manifest, [
                "ffconcat version 1.0",
                "file '/f/0.jpg'", "duration 0.500000",   # already on screen at start
                "file '/f/1.jpg'", "duration 0.500000",
                "file '/f/2.jpg'", "duration 1.000000",   # held to the cut
                "file '/f/2.jpg'",
            ], copy)
            with self.assertRaises(RuntimeError):
                recorder.screencast_manifest([], 0.0, 1.0)

    def test_code_card_fades_in_and_out_instead_of_popping(self) -> None:
        for copy, recorder in self.recorders.items():
            self.assertIn("__code_hidden__", recorder.CODE_OVERLAY_JS, copy)
            self.assertIn("transition:opacity", recorder.CODE_OVERLAY_JS, copy)
            self.assertIn("__code_hidden__", recorder.CODE_OVERLAY_REMOVE_JS, copy)
            self.assertIn("__demo_code_anim__", recorder.CODE_OVERLAY_JS, copy)


class TakeMatchingTest(unittest.TestCase):
    def test_takes_share_one_loudness_every_take_can_reach(self) -> None:
        batch = load("claude", "batch_process")
        common, gains = batch.matched_gains([
            {"input_i": "-20", "input_tp": "-6"},   # could reach -5.5, fine at -14
            {"input_i": "-18", "input_tp": "-2"},   # peak limits it to -17.5
        ])
        self.assertEqual(common, -17.5)
        self.assertEqual(gains, [2.5, 0.5])

    def test_selecting_a_take_pins_its_matched_copy(self) -> None:
        batch = load("claude", "batch_process")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            takes = project / "artifacts" / "narration-takes"
            takes.mkdir(parents=True)
            (takes / "take-2-matched.wav").write_bytes(b"RIFF")
            (takes / "ranking.json").write_text('{"recommended": "take-2.wav"}', encoding="utf-8")
            chosen = batch.select_take(project, "recommended")
            self.assertEqual(chosen.name, "take-2-matched.wav")
            settings = batch.load_tts_settings(project)
            self.assertEqual(settings, {
                "audio_source": "artifacts/narration-takes/take-2-matched.wav",
                "audio_processing": "preserve",
            })


if __name__ == "__main__":
    unittest.main()
