"""Release packages must exclude local files and record the exact source revision."""

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTest(unittest.TestCase):
    def test_packages_only_tracked_skill_files_with_version_and_checksums(self):
        spec = importlib.util.spec_from_file_location(
            "package_release", ROOT / "scripts/package_release.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for variant in [".agents", ".claude"]:
                skill = repo / variant / "skills/shiny-component-shorts"
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("A tracked skill\n")
                (skill / "requirements.txt").write_text("PyYAML\n")
            subprocess.run(
                ["git", "-C", str(repo), "add", ".agents", ".claude"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            (repo / ".agents/skills/shiny-component-shorts/private.wav").write_bytes(
                b"private"
            )
            module.package(repo, "v0.1.0", repo / "dist")
            sums = (repo / "dist/SHA256SUMS").read_text()
            for path in (repo / "dist").glob("*.zip"):
                with zipfile.ZipFile(path) as archive:
                    self.assertIn("shiny-component-shorts/SKILL.md", archive.namelist())
                    self.assertFalse(
                        any("private" in name for name in archive.namelist())
                    )
                    self.assertEqual(
                        archive.read("shiny-component-shorts/VERSION"), b"0.1.0\n"
                    )
                    meta = json.loads(
                        archive.read("shiny-component-shorts/release.json")
                    )
                    self.assertEqual(
                        meta["commit"],
                        subprocess.check_output(
                            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
                        ).strip(),
                    )
                    self.assertEqual(meta["tag"], "v0.1.0")
                self.assertIn(
                    hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name,
                    sums,
                )
            with self.assertRaises(ValueError):
                module.package(repo, "not-a-version", repo / "dist")

    def test_release_publish_waits_for_checks_and_limits_write_permission(self):
        config = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        self.assertEqual(
            config["jobs"]["checks"]["uses"], "./.github/workflows/contract-tests.yml"
        )
        self.assertEqual(config["jobs"]["publish"]["needs"], "checks")
        self.assertEqual(config["permissions"]["contents"], "read")
        self.assertEqual(config["jobs"]["publish"]["permissions"]["contents"], "write")
        self.assertIn("v*", config["on"]["push"]["tags"])
