#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the modules to test
import sys
ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / ".agents" / "skills" / "shiny-component-shorts" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_cache
import batch_process


class BuildCacheTest(unittest.TestCase):
    def test_calculate_hash_nonexistent(self):
        self.assertEqual(build_cache.calculate_hash(Path("nonexistent_file")), "")

    def test_calculate_hash_and_manifest_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            
            # Create mock inputs and outputs
            infile = project_dir / "app.py"
            infile.write_text("print('hello')", encoding="utf-8")
            
            outfile = project_dir / "demo.mp4"
            outfile.write_text("mock mp4 content", encoding="utf-8")
            
            # Initially, check_cache should be False because manifest does not exist
            self.assertFalse(build_cache.check_cache(project_dir, "recording", [infile], [outfile]))
            
            # Update cache
            build_cache.update_cache(project_dir, "recording", [infile])
            
            # Now check_cache should be True
            self.assertTrue(build_cache.check_cache(project_dir, "recording", [infile], [outfile]))
            
            # Modify input file
            infile.write_text("print('hello modified')", encoding="utf-8")
            
            # Now check_cache should be False because hash changed
            self.assertFalse(build_cache.check_cache(project_dir, "recording", [infile], [outfile]))

    def test_project_inputs_include_nested_sources_and_exclude_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            project_dir.mkdir()
            css = project_dir / "assets" / "styles.css"
            css.parent.mkdir()
            css.write_text("body {}", encoding="utf-8")
            helper = project_dir / "helpers" / "data.py"
            helper.parent.mkdir()
            helper.write_text("VALUE = 1", encoding="utf-8")
            artifact = project_dir / "artifacts" / "demo.mp4"
            artifact.parent.mkdir()
            artifact.write_text("video", encoding="utf-8")
            recorder = Path(temp_dir) / "record_demo.py"
            recorder.write_text("# recorder", encoding="utf-8")

            inputs = build_cache.collect_project_inputs(project_dir, [recorder])

            self.assertIn(css, inputs)
            self.assertIn(helper, inputs)
            self.assertIn(recorder, inputs)
            self.assertNotIn(artifact, inputs)

            build_cache.update_cache(project_dir, "recording", inputs)
            self.assertTrue(
                build_cache.check_cache(project_dir, "recording", inputs, [artifact])
            )
            recorder.write_text("# updated recorder", encoding="utf-8")
            self.assertFalse(
                build_cache.check_cache(project_dir, "recording", inputs, [artifact])
            )
            build_cache.update_cache(project_dir, "recording", inputs)
            artifact.write_text("new video", encoding="utf-8")
            self.assertTrue(
                build_cache.check_cache(project_dir, "recording", inputs, [artifact])
            )
            css.write_text("body { color: blue; }", encoding="utf-8")
            self.assertFalse(
                build_cache.check_cache(project_dir, "recording", inputs, [artifact])
            )


class BatchProcessTest(unittest.TestCase):
    def test_discover_projects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            
            # Create a mock project directory structure
            proj1 = base / "proj1"
            proj1.mkdir()
            (proj1 / "app.py").write_text("# app", encoding="utf-8")
            (proj1 / "actions.yaml").write_text("actions: []", encoding="utf-8")
            
            proj2 = base / "proj2"
            proj2.mkdir()
            (proj2 / "app.R").write_text("# app R", encoding="utf-8")
            (proj2 / "actions.yaml").write_text("actions: []", encoding="utf-8")
            
            # A folder missing app.py/app.R
            proj3 = base / "proj3"
            proj3.mkdir()
            (proj3 / "actions.yaml").write_text("actions: []", encoding="utf-8")
            
            discovered = batch_process.discover_projects(base)
            
            # Should discover proj1 and proj2, but not proj3
            self.assertEqual(len(discovered), 2)
            self.assertIn(proj1, discovered)
            self.assertIn(proj2, discovered)
            self.assertNotIn(proj3, discovered)

    @patch("subprocess.run")
    def test_process_project_cached_and_success_flow(self, mock_run):
        # Setup mock run responses
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            
            # Setup project files
            (project_dir / "app.py").write_text("# app", encoding="utf-8")
            (project_dir / "actions.yaml").write_text("actions: []", encoding="utf-8")
            
            # Create outputs so cache checks can succeed if hashes match
            artifacts_dir = project_dir / "artifacts"
            artifacts_dir.mkdir()
            (artifacts_dir / "demo.mp4").write_text("mp4", encoding="utf-8")
            (artifacts_dir / "recording.json").write_text("{}", encoding="utf-8")
            (artifacts_dir / "final.png").write_text("png", encoding="utf-8")
            
            # 1. Run without cache (first run)
            # Make sure build_cache check_cache returns False
            res = batch_process.process_project(
                project_dir=project_dir,
                start_port=8100,
                tts_enabled=False,
                merge_enabled=False,
                force=True
            )
            
            self.assertEqual(res["record"], "SUCCESS")
            self.assertEqual(res["validate"], "PASSED")
            
            # Verify subprocess.run was called for record_demo.py and validate_demo.py
            self.assertEqual(mock_run.call_count, 2)
            self.assertIn("--port", mock_run.call_args_list[0].args[0])
            self.assertIn("8100", mock_run.call_args_list[0].args[0])
            
            # 2. Run with cache enabled (second run)
            mock_run.reset_mock()
            res = batch_process.process_project(
                project_dir=project_dir,
                start_port=8100,
                tts_enabled=False,
                merge_enabled=False,
                force=False
            )
            
            # Record should be CACHED, and no subprocess call for record_demo.py should be made
            self.assertEqual(res["record"], "CACHED")
            # validate_demo is still run to confirm final integrity
            self.assertEqual(mock_run.call_count, 1)

    @patch("subprocess.run")
    def test_failed_tts_blocks_merge_even_when_stale_audio_exists(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="recorded", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="tts failed"),
            MagicMock(returncode=0, stdout="validated", stderr=""),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "app.py").write_text("# app", encoding="utf-8")
            (project_dir / "actions.yaml").write_text("actions: []", encoding="utf-8")
            artifacts = project_dir / "artifacts"
            artifacts.mkdir()
            for name, content in (
                ("demo.mp4", "video"),
                ("recording.json", "{}"),
                ("final.png", "png"),
                ("narration.txt", "prompt"),
                ("narration.wav", "stale audio"),
                ("final_with_audio.mp4", "stale merge"),
            ):
                (artifacts / name).write_text(content, encoding="utf-8")

            result = batch_process.process_project(
                project_dir=project_dir,
                start_port=8200,
                tts_enabled=True,
                merge_enabled=True,
                force=True,
            )

        self.assertEqual(result["tts"], "FAILED")
        self.assertEqual(result["merge"], "BLOCKED")
        self.assertTrue(batch_process.has_failures([result]))
        self.assertFalse(any(call.args[0][0] == "ffmpeg" for call in mock_run.call_args_list))

    def test_port_ranges_are_distinct_and_bounded(self):
        self.assertEqual(batch_process.start_port_for(0), 8000)
        self.assertEqual(batch_process.start_port_for(1), 8100)
        with self.assertRaises(ValueError):
            batch_process.start_port_for(1000)

    @patch("subprocess.run")
    def test_requested_steps_fail_when_inputs_are_missing(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "app.py").write_text("# app", encoding="utf-8")
            (project_dir / "actions.yaml").write_text("actions: []", encoding="utf-8")
            artifacts = project_dir / "artifacts"
            artifacts.mkdir()
            for name in ("demo.mp4", "recording.json", "final.png"):
                (artifacts / name).write_text("output", encoding="utf-8")

            tts_result = batch_process.process_project(
                project_dir, 8300, tts_enabled=True, merge_enabled=False, force=True
            )
            merge_result = batch_process.process_project(
                project_dir, 8400, tts_enabled=False, merge_enabled=True, force=True
            )

        self.assertEqual(tts_result["tts"], "FAILED")
        self.assertTrue(any("narration.txt" in error for error in tts_result["errors"]))
        self.assertEqual(merge_result["merge"], "FAILED")
        self.assertTrue(any("narration.wav" in error for error in merge_result["errors"]))
        self.assertTrue(batch_process.has_failures([tts_result, merge_result]))


if __name__ == "__main__":
    unittest.main()
