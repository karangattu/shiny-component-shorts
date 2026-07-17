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
                worker_id=1,
                tts_enabled=False,
                merge_enabled=False,
                force=True
            )
            
            self.assertEqual(res["record"], "SUCCESS")
            self.assertEqual(res["validate"], "PASSED")
            
            # Verify subprocess.run was called for record_demo.py and validate_demo.py
            self.assertEqual(mock_run.call_count, 2)
            
            # 2. Run with cache enabled (second run)
            mock_run.reset_mock()
            res = batch_process.process_project(
                project_dir=project_dir,
                worker_id=1,
                tts_enabled=False,
                merge_enabled=False,
                force=False
            )
            
            # Record should be CACHED, and no subprocess call for record_demo.py should be made
            self.assertEqual(res["record"], "CACHED")
            # validate_demo is still run to confirm final integrity
            self.assertEqual(mock_run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
