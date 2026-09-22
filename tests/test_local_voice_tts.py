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
    def test_speaking_rate_range_and_defaults(self):
        required = ["--input", "prompt.txt", "--output", "out.wav", "--usage-output",
                    "usage.json", "--engine-dir", ".", "--reference", "ref.wav"]
        for rate in ("0.5", "0.85", "1.0", "1.25", "1.5"):
            with self.subTest(rate=rate):
                self.assertEqual(
                    generate_local_voice.parse_args(required + ["--speaking-rate", rate]).speaking_rate,
                    float(rate),
                )
        for rate in ("0.4", "0.49", "1.51", "2.0", "fast"):
            with self.subTest(rate=rate), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    generate_local_voice.parse_args(required + ["--speaking-rate", rate])
        defaults = generate_local_voice.parse_args(required)
        self.assertEqual(defaults.speaking_rate, 1.0)
        self.assertEqual(defaults.max_wpm, 160.0)

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
                    language="English", engine="qwen", speaking_rate=0.9,
                    output=root / "result.wav")
                generate_local_voice.synthesize_api(args, "Read this script")
                self.assertAlmostEqual(generate_local_voice.wave_duration(args.output), 0.1)
                self.assertEqual(requests[0][0], "/synthesize")
                for value in (b'name="reference_audio"', b"saved-voice-sample", b"Reference words", b"Read this script", b"qwen", b"fast"):
                    self.assertIn(value, requests[0][1])
                self.assertIn(b'name="speed"\r\n\r\n0.9\r\n', requests[0][1])
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

    def test_pause_tags_become_line_breaks_in_one_request(self) -> None:
        script = generate_local_voice.local_voice_script(
            "Audio profile:\nVoice.\n\nScene:\nScene.\n\nDirector's notes:\nNotes.\n\n"
            "Transcript:\n"
            "Start here [short pause] then continue [slightly firmer] with the proof [medium pause]\n"
            "and finish cleanly right now [long pause] trailing words"
        )
        self.assertEqual(
            script,
            "Start here.\nthen continue with the proof.\nand finish cleanly right now.\ntrailing words",
        )

    def test_adjacent_and_leading_pauses_merge_or_drop(self) -> None:
        envelope = (
            "Audio profile:\nVoice.\n\nScene:\nScene.\n\nDirector's notes:\nNotes.\n\nTranscript:\n"
        )
        self.assertEqual(
            generate_local_voice.local_voice_script(envelope + "One [short pause] [medium pause] two ends."),
            "One.\ntwo ends.",
        )
        self.assertEqual(
            generate_local_voice.local_voice_script(envelope + "[long pause] Start here"),
            "Start here",
        )
        self.assertEqual(
            generate_local_voice.local_voice_script(envelope + "Already ends. [medium pause] Next thought"),
            "Already ends.\nNext thought",
        )
        with self.assertRaises(ValueError):
            generate_local_voice.local_voice_script("No transcript section here")

    def _fake_uv(self, root: Path) -> tuple[Path, dict]:
        bin_dir = root / "bin"
        bin_dir.mkdir()
        captured = root / "captured.jsonl"
        fake_uv = bin_dir / "uv"
        fake_uv.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys, wave\n"
            "from pathlib import Path\n"
            "with open(os.environ['CAPTURED_ARGS'], 'a') as handle:\n"
            "    handle.write(json.dumps(sys.argv) + chr(10))\n"
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
        env = os.environ.copy()
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        env["CAPTURED_ARGS"] = str(captured)
        return captured, env

    def _run_adapter(self, root: Path, prompt: str, env: dict, extra_args: list[str]):
        prompt_path = root / "narration.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        reference = root / "speaker.wav"
        reference.write_bytes(b"reference")
        output = root / "narration.wav"
        usage = root / "narration.usage.json"
        engine = root / "local-voice-cloning"
        engine.mkdir(exist_ok=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(LOCAL_TTS),
                "--input", prompt_path.name,
                "--output", output.name,
                "--usage-output", usage.name,
                "--engine-dir", engine.name,
                "--reference", reference.name,
                "--ref-text", "Exact sample transcript.",
                "--quality", "high",
                "--language", "English",
                *extra_args,
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=root,
        )
        return completed, output, usage

    def test_single_request_forwards_speed_and_measures_pace(self) -> None:
        filler = " ".join(f"word{index}" for index in range(58))
        prompt = (
            "Audio profile:\nA clear developer voice.\n\n"
            "Scene:\nA demo changes on screen.\n\n"
            "Director's notes:\nRead only the transcript.\n\n"
            "Transcript:\n"
            "Begin with the filter card showing three uneven order totals [curious] "
            "then switch the window to seven days and watch the value box redraw "
            "[slightly firmer] without any jump in layout. Clearing the search returns "
            f"the card to its starting size [warm] with no leftover state [confident] {filler}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            captured, env = self._fake_uv(root)
            completed, output, usage = self._run_adapter(
                root, prompt, env, ["--speaking-rate", "0.9", "--max-wpm", "0"]
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            calls = [json.loads(line) for line in captured.read_text(encoding="utf-8").splitlines()]
            # One synthesis request for the whole transcript, no assembly.
            self.assertEqual(len(calls), 1)
            generated_text = calls[0][calls[0].index("--text") + 1]
            self.assertNotIn("[", generated_text)
            self.assertNotIn("slightly firmer", generated_text)
            self.assertEqual(calls[0][calls[0].index("--speed") + 1], "0.9")
            self.assertTrue(output.is_file())
            report = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(report["provider"], "Local voice cloning")
            self.assertEqual(report["speaking_rate"], 0.9)
            self.assertEqual(report["synthesis_requests"], 1)
            self.assertFalse(report["audio_modified"])
            self.assertEqual(report["words"], len(generated_text.split()))
            self.assertGreater(report["words_per_minute"], 0)
            self.assertEqual(report["estimated_paid_tier_cost_usd"], 0)

    def test_pace_gate_rejects_rushed_takes_and_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tone = root / "tone.wav"
            with wave.open(str(tone), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b"\xff\x7f" * 24000)  # 1 s of full-scale tone
            with self.assertRaises(generate_local_voice.PaceRejected):
                generate_local_voice.check_pace(tone, 10, 160.0)
            pace = generate_local_voice.check_pace(tone, 10, 0)
            self.assertEqual(pace["words"], 10)
            self.assertEqual(pace["words_per_minute"], 600.0)


if __name__ == "__main__":
    unittest.main()
