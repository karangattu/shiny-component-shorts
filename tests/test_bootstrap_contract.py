"""Production tools use a verified release once, then keep that version."""

import hashlib
import importlib.util
import io
import json
import tempfile
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/shiny-component-shorts/scripts/bootstrap_skill.py"


def archive(extra=None, variant="codex"):
    files = {
        "SKILL.md": b"Pinned instructions",
        "scripts/record_demo.py": b'print("pinned")\n',
        "release.json": json.dumps(
            {
                "tag": "v0.2.0",
                "version": "0.2.0",
                "commit": "a" * 40,
                "variant": variant,
            }
        ).encode(),
        "VERSION": b"0.2.0\n",
    }
    for script in ["prepare_editorial.py", "stitch_reel.py", "batch_process.py"]:
        files["scripts/" + script] = b'print("pinned")\n'
    files["skill-manifest.json"] = json.dumps(
        {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    ).encode()
    files.update(extra or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as dest:
        for name, data in files.items():
            dest.writestr("shiny-component-shorts/" + name, data)
    return stream.getvalue()


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("bootstrap_skill", SCRIPT)
        assert spec and spec.loader
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "installed"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("Local instructions")
        (self.source / "scripts").mkdir()
        (self.source / "scripts/record_demo.py").write_text('print("local")\n')
        self.project = self.root / "video"
        self.variant = "codex"
        self.data = archive()

    def fetch(self, url):
        name = f"shiny-component-shorts-v0.2.0-{self.variant}.zip"
        if url.endswith("/releases/latest"):
            base = "https://github.com/karangattu/shiny-component-shorts/releases/download/v0.2.0/"
            return json.dumps(
                {
                    "tag_name": "v0.2.0",
                    "draft": False,
                    "prerelease": False,
                    "assets": [
                        {"name": item, "browser_download_url": base + item}
                        for item in [name, "SHA256SUMS"]
                    ],
                }
            ).encode()
        if url.endswith("SHA256SUMS"):
            return (hashlib.sha256(self.data).hexdigest() + "  " + name + "\n").encode()
        return self.data

    def pin(self, **kwargs):
        return self.module.ensure_pin(
            self.project, self.source, variant="codex", **kwargs
        )

    def test_latest_once_then_reuse_for_children_without_network(self):
        with patch.object(self.module, "fetch", side_effect=self.fetch) as fetch:
            pinned = self.pin()
            self.assertEqual(fetch.call_count, 3)
        self.assertEqual((pinned / "SKILL.md").read_text(), "Pinned instructions")
        lock = json.loads((self.project / "skill-lock.json").read_text())
        self.assertEqual(lock["tag"], "v0.2.0")
        self.assertEqual(lock["archive_sha256"], hashlib.sha256(self.data).hexdigest())
        with patch.object(
            self.module,
            "fetch",
            side_effect=AssertionError("rerender must stay offline"),
        ):
            self.assertEqual(self.pin(), pinned)
            self.assertEqual(
                self.module.ensure_pin(
                    self.project / "feature", self.source, variant="codex"
                ),
                pinned,
            )
        self.assertEqual((self.source / "SKILL.md").read_text(), "Local instructions")

    def test_checksum_failure_network_failure_and_untrusted_assets_leave_no_pin(self):
        for failure in ["checksum", "offline", "origin"]:

            def bad_fetch(url):
                if failure == "offline":
                    raise OSError("offline")
                result = self.fetch(url)
                if failure == "checksum" and url.endswith("SHA256SUMS"):
                    return result.replace(
                        hashlib.sha256(self.data).hexdigest().encode(), b"0" * 64
                    )
                if failure == "origin" and url.endswith("/releases/latest"):
                    return result.replace(
                        b"https://github.com/", b"https://evil.invalid/"
                    )
                return result

            with self.subTest(failure=failure), patch.object(
                self.module, "fetch", side_effect=bad_fetch
            ):
                with self.assertRaises((ValueError, OSError)):
                    self.pin()
                self.assertFalse((self.project / "skill-lock.json").exists())
                self.assertFalse((self.project / ".video-skill").exists())

    def test_unsafe_or_inconsistent_archive_rejected(self):
        for extra in [
            {"../escape": b"bad"},
            {"unexpected.py": b"bad"},
            {"release.json": b"{}"},
        ]:
            self.data = archive(extra)
            with self.subTest(extra=extra), patch.object(
                self.module, "fetch", side_effect=self.fetch
            ):
                with self.assertRaises(ValueError):
                    self.pin()
            self.assertFalse((self.root / "escape").exists())

    def test_pin_tampering_and_variant_mismatch_block(self):
        with patch.object(self.module, "fetch", side_effect=self.fetch):
            pinned = self.pin()
        with self.assertRaises(ValueError):
            self.module.ensure_pin(self.project, self.source, variant="claude")
        (pinned / "SKILL.md").write_text("changed")
        with self.assertRaises(ValueError):
            self.pin()

    def test_local_override_and_legacy_adoption_do_not_fetch_or_overwrite(self):
        self.project.mkdir()
        (self.project / "artifacts").mkdir()
        (self.project / "artifacts/narration.wav").write_bytes(b"existing audio")
        with patch.object(
            self.module, "fetch", side_effect=AssertionError("existing production")
        ):
            pinned = self.pin()
        self.assertEqual((pinned / "SKILL.md").read_text(), "Local instructions")
        lock = json.loads((self.project / "skill-lock.json").read_text())
        self.assertEqual(lock["channel"], "legacy-local")
        other = self.root / "local-video"
        with patch.object(
            self.module, "fetch", side_effect=AssertionError("explicit local")
        ):
            self.module.ensure_pin(other, self.source, variant="codex", local=True)
        (self.source / "SKILL.md").write_text("customized")
        self.assertEqual((pinned / "SKILL.md").read_text(), "Local instructions")

    def test_occupied_destination_and_busy_bootstrap_preserved(self):
        self.project.mkdir()
        (self.project / ".video-skill").mkdir()
        with self.assertRaises((ValueError, FileExistsError)):
            self.pin(local=True)
        self.assertTrue((self.project / ".video-skill").is_dir())

    def test_runtime_dispatches_pinned_script_with_same_arguments(self):
        with patch.object(self.module, "fetch", side_effect=self.fetch):
            pinned = self.pin()
        with patch.object(self.module.os, "execv") as execute:
            self.module.guard(
                self.project,
                self.source / "scripts/record_demo.py",
                ["--project-dir", str(self.project), "--dry-run"],
            )
        self.assertEqual(
            Path(execute.call_args.args[1][1]), pinned / "scripts/record_demo.py"
        )
        self.assertEqual(execute.call_args.args[1][-1], "--dry-run")

    def test_real_cli_entrypoints_dispatch_both_variants_before_production(self):
        for folder, variant in [(".agents", "codex"), (".claude", "claude")]:
            self.data = archive(variant=variant)
            self.variant = variant
            project = self.root / variant
            with patch.object(self.module, "fetch", side_effect=self.fetch):
                self.module.ensure_pin(project, self.source, variant=variant)
            (project / "app.py").write_text("")
            (project / "actions.yaml").write_text("actions: []")
            for script, args in [
                ("record_demo.py", ["--project-dir", str(project), "--dry-run"]),
                ("prepare_editorial.py", ["--project-dir", str(project)]),
                ("stitch_reel.py", ["--reel-dir", str(project)]),
                ("batch_process.py", ["--phase", "narration", "--dirs", str(project)]),
            ]:
                with self.subTest(variant=variant, script=script):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(
                                ROOT
                                / folder
                                / "skills/shiny-component-shorts/scripts"
                                / script
                            ),
                            *args,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("pinned", result.stdout)

    def test_batch_groups_versions_and_preserves_options(self):
        with patch.object(self.module, "fetch", side_effect=self.fetch):
            self.pin()
        other = self.root / "other"
        self.module.ensure_pin(other, self.source, variant="codex", local=True)
        with patch.object(self.module.subprocess, "run") as run:
            run.return_value.returncode = 0
            with self.assertRaises(SystemExit) as result:
                self.module.guard_batch(
                    [self.project, other],
                    self.source / "scripts/batch_process.py",
                    ["--phase", "finish", "--dirs", "*", "--force"],
                )
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(run.call_count, 2)
        self.assertNotIn("*", run.call_args.args[0])
        self.assertIn("--force", run.call_args.args[0])
        self.assertIn("--phase", run.call_args.args[0])

    def test_local_snapshot_cannot_recurse_into_its_source(self):
        with self.assertRaises(ValueError):
            self.module.ensure_pin(
                self.source / "nested-production", self.source, local=True
            )
        self.assertFalse((self.source / "nested-production").exists())

    def test_busy_bootstrap_is_not_removed_by_another_process(self):
        self.project.mkdir()
        busy = self.project / ".skill-bootstrap.lock"
        busy.write_text("owned elsewhere")
        with self.assertRaises(ValueError):
            self.pin(local=True)
        self.assertEqual(busy.read_text(), "owned elsewhere")


if __name__ == "__main__":
    unittest.main()
