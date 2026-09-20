#!/usr/bin/env python3
import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
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


sys.path.insert(0, str(LOCAL_TTS.parent))
import generate_local_voice  # noqa: E402


class LocalVoiceTTSContractTest(unittest.TestCase):
    def test_adapter_rejects_time_stretching_before_generation(self):
        required = ["--input", "prompt.txt", "--output", "out.wav", "--usage-output",
                    "usage.json", "--engine-dir", ".", "--reference", "ref.wav"]
        for rate in ("0.9", "1.1", "1.2", "2.0"):
            with self.subTest(rate=rate), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    generate_local_voice.parse_args(required + ["--speaking-rate", rate])
        self.assertEqual(generate_local_voice.parse_args(required).speaking_rate, 1.0)

    def test_real_http_multipart_contract_and_invalid_audio(self):
        wav = io.BytesIO()
        with wave.open(wav, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\x00\x00" * 2400)
        requests = []
        response = [wav.getvalue()]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(response[0])
            def log_message(self, format: str, *args: object) -> None:
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reference = root / "speaker.wav"
                reference.write_bytes(b"saved-voice-sample")
                args = argparse.Namespace(api_url=f"http://127.0.0.1:{server.server_port}",
                    reference=reference, ref_text="Reference words", quality="fast",
                    language="English", engine="qwen", output=root / "result.wav")
                generate_local_voice.synthesize_api(args, "Read this script")
                self.assertAlmostEqual(generate_local_voice.wave_duration(args.output), 0.1)
                self.assertEqual(requests[0][0], "/synthesize")
                for value in (b'name="reference_audio"', b"saved-voice-sample", b"Reference words", b"Read this script", b"qwen", b"fast"):
                    self.assertIn(value, requests[0][1])
                response[0] = b'not audio'
                with self.assertRaises((wave.Error, EOFError)):
                    generate_local_voice.synthesize_api(args, "Read this script")
                self.assertAlmostEqual(generate_local_voice.wave_duration(args.output), 0.1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_api_rejects_nonlocal_destinations(self):
        for url in ("https://example.com", "http://127.0.0.1.evil.com", "http://user@localhost:8001", "http://localhost:8001/other"):
            with self.assertRaises(ValueError):
                generate_local_voice.validate_api_url(url)

    def test_adapter_removes_forced_pauses_and_other_tags(
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

            filler = " ".join(f"word{index}" for index in range(90))
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
                    prompt.name,
                    "--output",
                    output.name,
                    "--usage-output",
                    usage.name,
                    "--engine-dir",
                    engine.name,
                    "--reference",
                    reference.name,
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
                cwd=root,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            args = json.loads(captured.read_text(encoding="utf-8"))
            generated_text = args[args.index("--text") + 1]
            self.assertNotIn("[", generated_text)
            self.assertNotIn("slightly firmer", generated_text)
            self.assertIn("Start here then continue with the proof ", generated_text)
            self.assertNotIn("\n", generated_text)
            self.assertIn("and finish cleanly right now word0", generated_text)
            self.assertTrue(output.is_file())
            report = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(report["provider"], "Local voice cloning")
            self.assertEqual(report["speaking_rate"], 1.0)
            self.assertAlmostEqual(generate_local_voice.wave_duration(output), 0.1)
            self.assertEqual(report["estimated_paid_tier_cost_usd"], 0)


if __name__ == "__main__":
    unittest.main()
