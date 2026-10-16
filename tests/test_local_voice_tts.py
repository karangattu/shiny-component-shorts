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
import unittest.mock
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

    def test_exact_pause_tags_split_the_transcript_into_segments(self) -> None:
        envelope = (
            "Audio profile:\nVoice.\n\nScene:\nScene.\n\nDirector's notes:\nNotes.\n\nTranscript:\n"
        )
        parts = generate_local_voice.local_voice_parts(
            envelope + "Hello! If you're hearing this, [pause 2s] it means it worked [pause 0.5s] . "
            "Every word ran here. [pause 0.5s] Pretty wild, right?"
        )
        self.assertEqual(
            parts,
            ["Hello! If you're hearing this.", 2.0, "it means it worked.", 0.5,
             "Every word ran here.", 0.5, "Pretty wild, right?"],
        )
        with self.assertRaises(ValueError):
            generate_local_voice.local_voice_parts(envelope + "Wait [pause 30s] done")

    def test_join_with_silence_inserts_exact_digital_silence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tone = root / "tone.wav"
            with wave.open(str(tone), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b"\x01\x01" * 12000)
            out = root / "out.wav"
            generate_local_voice.join_with_silence([tone, 2.0, tone], out)
            with wave.open(str(out), "rb") as wav:
                self.assertEqual(wav.getnframes(), 12000 + 48000 + 12000)

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
                # A real service on the default port must not take over the fake CLI.
                "--transport", "cli",
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
                root, prompt, env,
                ["--engine", "omnivoice", "--speaking-rate", "0.9", "--max-wpm", "0"],
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

    def test_exact_pauses_synthesize_segments_and_join_with_silence(self) -> None:
        filler = " ".join(f"word{index}" for index in range(100))
        prompt = (
            "Audio profile:\nA clear developer voice.\n\nScene:\nA demo.\n\n"
            "Director's notes:\nRead only the transcript.\n\nTranscript:\n"
            f"Hello there, [pause 2s] it worked [warm] {filler} [curious] done [firm]\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            captured, env = self._fake_uv(root)
            completed, output, usage = self._run_adapter(root, prompt, env, ["--max-wpm", "0"])
            self.assertEqual(completed.returncode, 0, completed.stderr)
            calls = [json.loads(line) for line in captured.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][calls[0].index("--text") + 1], "Hello there.")
            report = json.loads(usage.read_text(encoding="utf-8"))
            self.assertEqual(report["synthesis_requests"], 2)
            self.assertEqual(report["exact_pause_seconds"], 2.0)
            self.assertTrue(report["audio_modified"])

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


class LocalVoiceTransportTest(unittest.TestCase):
    """Real reference names, sidecar transcripts, API autodetect, and the speed rule."""

    def serve(self, responses: dict, requests: list):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._reply(self.path)

            def do_POST(self):
                requests.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
                self._reply(self.path)

            def _reply(self, path):
                body = responses.get(path, b"")
                self.send_response(200 if path in responses else 404)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def test_upload_keeps_the_voice_name_and_sends_its_sidecar_transcript(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(b"\0\0" * 2400)
        requests: list = []
        url = self.serve({"/synthesize": buffer.getvalue()}, requests)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "karan.wav"
            reference.write_bytes(b"voice")
            (root / "karan.json").write_text(json.dumps({"transcript": "Corrected sample words."}))
            args = argparse.Namespace(api_url=url, reference=reference, ref_text="", quality="high",
                language="auto", engine="qwen", speaking_rate=1.0, output=root / "out.wav",
                engine_dir=root)
            generate_local_voice.synthesize_api(args, "Say this")
            body = requests[0][1]
            self.assertIn(b'filename="karan.wav"', body)
            self.assertIn(b'name="ref_text"\r\n\r\nCorrected sample words.\r\n', body)
            # An explicit transcript still wins over the sidecar.
            args.ref_text = "Given words."
            generate_local_voice.synthesize_api(args, "Say this")
            self.assertIn(b"Given words.", requests[1][1])
            command = generate_local_voice.build_cli_command("uv", args, "Say this", root / "o.wav")
            self.assertEqual(command[command.index("--ref-text") + 1], "Given words.")

    def test_auto_transport_prefers_a_running_api(self):
        url = self.serve({"/health": b'{"status": "ok"}'}, [])
        self.assertTrue(generate_local_voice.api_is_up(url))
        self.assertFalse(generate_local_voice.api_is_up("http://127.0.0.1:9"))
        with unittest.mock.patch.object(generate_local_voice, "DEFAULT_API_URL", url):
            self.assertEqual(generate_local_voice.resolve_api_url(None), url)
            self.assertIsNone(generate_local_voice.resolve_api_url(None, "cli"))
        with unittest.mock.patch.object(generate_local_voice, "DEFAULT_API_URL", "http://127.0.0.1:9"):
            self.assertIsNone(generate_local_voice.resolve_api_url(None))
            self.assertEqual(generate_local_voice.resolve_api_url(None, "api"), "http://127.0.0.1:9")

    def test_warm_up_posts_engine_and_quality(self):
        requests: list = []
        url = self.serve({"/warmup": b'{"status": "ok", "load_seconds": 1.5}'}, requests)
        report = generate_local_voice.warm_up(url, "qwen", "fast")
        self.assertEqual(report["load_seconds"], 1.5)
        self.assertEqual(requests[0], ("/warmup", b"engine=qwen&quality=fast"))

    def test_qwen_must_stay_at_speed_one(self):
        self.assertIsNone(generate_local_voice.speed_problem("qwen", 1.0))
        self.assertIsNone(generate_local_voice.speed_problem("omnivoice", 0.8))
        self.assertIn("add pause tags", generate_local_voice.speed_problem("qwen", 0.9) or "")
