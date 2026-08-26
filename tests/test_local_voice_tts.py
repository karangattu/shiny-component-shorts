#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_TTS = (
    ROOT
    / ".agents"
    / "skills"
    / "shiny-component-shorts"
    / "scripts"
    / "generate_local_voice.py"
)


class LocalVoiceTTSContractTest(unittest.TestCase):
    def test_adapter_turns_pause_tags_into_line_breaks_and_removes_other_tags(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            captured = root / "captured.json"
            fake_uv = bin_dir / "uv"
            fake_uv.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys, wave\n"
                "from pathlib import Path\n"
                "Path(os.environ['CAPTURED_ARGS']).write_text(json.dumps(sys.argv))\n"
                "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.parent.mkdir(parents=True, exist_ok=True)\n"
                "with wave.open(str(output), 'wb') as wav:\n"
                "    wav.setnchannels(1)\n"
                "    wav.setsampwidth(2)\n"
                "    wav.setframerate(24000)\n"
                "    wav.writeframes(b'\\x00\\x00' * 2400)\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)

            filler = " ".join(f"word{index}" for index in range(48))
            prompt = root / "narration.txt"
            prompt.write_text(
                "Audio profile:\nA clear developer voice.\n\n"
                "Scene:\nA demo changes on screen.\n\n"
                "Director's notes:\nRead only the transcript.\n\n"
                "Transcript:\n"
                "Start here [short pause]\n"
                "then continue [slightly firmer] with the proof [medium pause]\n"
                "and finish cleanly [long pause] right now\n"
                f"{filler}\n",
                encoding="utf-8",
            )
            reference = root / "speaker.wav"
            reference.write_bytes(b"reference")
            output = root / "narration.wav"
            usage = root / "narration.usage.json"
            engine = root / "local-voice-cloning"
            engine.mkdir()
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["CAPTURED_ARGS"] = str(captured)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(LOCAL_TTS),
                    "--input",
                    str(prompt),
                    "--output",
                    str(output),
                    "--usage-output",
                    str(usage),
                    "--engine-dir",
                    str(engine),
                    "--reference",
                    str(reference),
                    "--ref-text",
                    "Exact sample transcript.",
                    "--quality",
                    "high",
                    "--language",
                    "English",
                ],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            args = json.loads(captured.read_text(encoding="utf-8"))
            generated_text = args[args.index("--text") + 1]
            self.assertNotIn("[", generated_text)
            self.assertNotIn("slightly firmer", generated_text)
            self.assertIn("Start here\nthen continue with the proof\n", generated_text)
            self.assertIn("and finish cleanly\n\nright now word0", generated_text)
            self.assertTrue(output.is_file())
            report = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(report["provider"], "Local voice cloning")
            self.assertEqual(report["estimated_paid_tier_cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
