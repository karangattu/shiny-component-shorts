# TTS and cost reporting

Read this reference only when narration audio, a finished video with audio, or cost reporting is requested.

Check for `GEMINI_API_KEY`/`GOOGLE_API_KEY` only after audio has been requested and only when Gemini TTS will actually be called. Never check for, mention, or ask the user for these keys on a silent-video workflow, local voice-cloning workflow, or when importing existing narration; a missing key is an error only on the Gemini path. In a silent video's cost report, list the Gemini TTS row as `not used / $0`.

## Narration prompt

Write `artifacts/narration.txt` in this form:

```text
Synthesize this as a natural, curious tech explainer for a 30-second Shiny component video.

Audio profile:
A clear developer voice. Brisk, precise, warm, and not salesy. No non-speech vocalizations.

Scene:
[One sentence describing the visible demo.]

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not laugh, giggle, or chuckle. Do not add sighs, gasps, coughs, filler sounds, or any other non-speech vocalization. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[60–85 spoken words with 3–6 intentional pacing or emphasis cues.]
```

Use three aligned controls:

1. Put the overall persona, emotional register, and default pace in `Audio profile` and `Director's notes`.
2. Write transcript language that naturally supports that performance.
3. Use bracketed tags only for a localized change that matches a visible beat.

Useful inline cues are limited to pacing and restrained emphasis:

- Pacing: `[short pause]` (about 250 ms), `[medium pause]` (about 500 ms), or `[long pause]` (about one second or more).
- Local delivery changes: `[slightly firmer]`, `[slower]`, or `[quickly]` when they match a visible beat.
- Do not use reaction or non-speech tags. The validator rejects laugh, laughter, giggle, and chuckle variants.

For a developer short, prefer a restrained arc: conversational hook, a short or medium pause before the reveal, slightly firmer delivery for the decisive code line, and a warm payoff. Do not stack tags, repeat the same cue mechanically, or use shouting, panic, crying, coughing, character voices, or any non-verbal sound.

Treat tags as preview-model hints, not a closed vocabulary or timing guarantee. Prefer the documented named pause tags over invented exact-duration syntax such as `[pause=1.0]` unless that syntax has been tested with the current model. Emotional adjective tags such as `[curious]`, `[scared]`, or `[bored]` can occasionally be vocalized; express the overall emotion in the director's notes and verify any inline adjective tag before keeping it. Do not include timestamps or visual stage directions in the transcript.

For a narrated series, vary the performance direction as deliberately as the visual direction. For example, use one curious discovery, one calm diagnostic explanation, one measured comparison, one focused accessibility demonstration, and one brisk reference-style proof rather than giving every video the same excited delivery.

## Generate audio

For a narrated deliverable, generate the audio before recording the video: the WAV's measured duration and silence gaps are what `actions.yaml` timing must follow (see the recording contract's Timing section). Word-count estimates drift enough to push actions out of sync with the spoken sentences.

Do not call Gemini unless the user requested audio. Never print, persist, or ask for the API key value.

If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is available, run:

```bash
python .claude/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input generated/demo-name/artifacts/narration.txt \
  --output generated/demo-name/artifacts/narration.wav \
  --usage-output generated/demo-name/artifacts/narration.usage.json
```

The generator statically validates the prompt (envelope structure, 60–85 words, 3–6 tags, and absence of laughter cues) before calling the API to prevent wasted spend. It uses Gemini 3.1 Flash TTS Preview and chooses from the curated Kore, Erinome, Charon, and Achird voices unless `--voice` overrides it. Treat preview model names and prices as unstable.

If both key variables exist and authentication fails, note that the Google SDK may prioritize `GOOGLE_API_KEY`; do not reveal either value.

## Use local voice cloning

Use local voice cloning by default for new agent-generated narrated videos in this workspace, unless the user selects another provider or supplies existing narration. Write `tts-settings.json` explicitly; older projects without it retain their Gemini behavior. The adapter supports the sibling project’s REST API or its CLI through `uv`, and does not check for a Gemini API key.

For a saved voice, put its name in `tts-settings.json`:

```json
{
  "provider": "local-voice-cloning",
  "saved_voice": "karan",
  "quality": "high",
  "language": "English"
}
```

The batch processor resolves this to `<engine-dir>/voice_samples/karan.wav`. A saved voice is a name, not a path. For an arbitrary reference recording, use:

```json
{
  "provider": "local-voice-cloning",
  "reference_voice": "/path/to/speaker.wav",
  "reference_text": "The exact words spoken in the first 12 seconds.",
  "quality": "high",
  "language": "English"
}
```

Omit both voice selectors to use the default saved voice `karan`, or choose one of `saved_voice` and `reference_voice`. Never choose both. A missing saved WAV is an error; do not silently switch speakers. `reference_text` is optional; when omitted, the local engine transcribes the first 12 seconds. An exact transcript avoids loading transcription and usually improves fidelity. Relative `reference_voice` paths resolve against the video directory.

By default, the adapter looks for `local-voice-cloning` beside this repository. Set `LOCAL_VOICE_CLONING_DIR` or the per-video `engine_dir` setting when it lives elsewhere. `quality` defaults to `high`; `language` defaults to `auto`.

### REST API and voice adjustments

Start the sibling service in a managed terminal and wait for `GET /health` to return `status: ok`:

```bash
cd ../local-voice-cloning
uv run uvicorn src.api:app --host 127.0.0.1 --port 8001
```

For new narrated videos, write this per-video `tts-settings.json`:

```json
{
  "provider": "local-voice-cloning",
  "api_url": "http://127.0.0.1:8001",
  "saved_voice": "karan",
  "engine": "qwen",
  "quality": "high",
  "language": "English",
  "speaking_rate": 1.0
}
```

The user can select another saved WAV name or reference recording, correct `reference_text`, choose `high`/`fast` quality, or adjust `speaking_rate` between 0.5 and 2.0 (above 1 is faster). List available voices from `<engine_dir>/voice_samples/*.wav`; the API does not offer a saved-voice listing endpoint. `engine` accepts `qwen` or `omnivoice`; OmniVoice must be installed separately in the sibling project. Quality changes model/compute settings, not voice identity.

`POST /synthesize` receives multipart fields `text`, `ref_text`, `quality`, `language`, `engine`, `output_format=wav`, plus the uploaded `reference_audio`. `GET /info` reports supported engine settings. `POST /transcribe` can help inspect the sample transcript. Consult the running `/docs` and sibling `src/api.py` for the exact contract. Only loopback HTTP origins are accepted, with redirects and proxies disabled. Omitting `api_url` uses the CLI; API failures are surfaced without silently switching providers.

The API's `speed` parameter is a compatibility option, so the adapter applies `speaking_rate` with FFmpeg's pitch-preserving `atempo` after synthesis. It measures the adjusted WAV. Global performance prose and emphasis tags do not steer the local model; use punctuation, explicit pauses, and rate, then review a generated sample before recording.

After any voice, reference, transcript, engine, or rate change, rerun `--phase narration`, review the new audio and measured timing, retime `actions.yaml`, and rerun `--phase finish --approve-timing`. The finish gate rejects stale local narration even when timing approval is requested. Approval includes narration inputs and reference audio hashes.

Sentence windows come from silence detection, **not word-level forced alignment**. Rate changes can shorten gaps enough to merge spoken sentences into one detected span. Do not treat an action landing in a detected span as proof that the matching words describe its visible state. Listen while viewing the final video and check each reaction and the code reveal; keep the final payoff 1–3 seconds beyond the actual WAV. A timing mismatch requires retiming and recording again.

Keep the normal prompt envelope and its 3–6 cues in `narration.txt` so concept review and validation stay consistent. Before local synthesis, the adapter extracts only `Transcript:`, collapses formatting whitespace, turns `[short pause]` and `[medium pause]` into one line break, turns `[long pause]` into two line breaks, and removes every other bracketed delivery tag. This matters because the local engine does not honor narration tags and inserts about 0.4 seconds of silence for each line break. Use pause tags only where a real pause belongs; ordinary source formatting must not add pauses.

The local adapter writes the same `narration.wav`, timing report, and usage report as the Gemini path. Its usage report records `$0` paid API cost. Listen to the result and approve its measured timing before the finish phase, exactly as with any other narration source.

## Use existing narration audio

When the user supplies existing narration — a WAV, MP3, or a previously narrated video whose audio track is the narration — do not call Gemini and do not check for any API key. Import it instead:

```bash
python .claude/skills/shiny-component-shorts/scripts/import_narration.py \
  --source path/to/narrated.mp4 \
  --output generated/demo-name/artifacts/narration.wav \
  --usage-output generated/demo-name/artifacts/narration.usage.json
```

The script verifies the source has an audio stream, converts it to the pipeline's mono 24 kHz PCM WAV, and writes a `$0` usage report marked `Imported audio`. From there the workflow is identical to generated narration: listen to the WAV, measure its duration and sentence gaps, and time `actions.yaml` against it. Keep the `narration.txt` envelope's transcript matched to what the imported audio actually says, since the validator compares action timing against its sentence windows.

For batch processing, set `{"audio_source": "path/to/narrated.mp4"}` in the video's `tts-settings.json` (relative paths resolve against the video directory); the narration phase then imports instead of synthesizing and adds the source file to the cache key. `audio_source` cannot be combined with `voice` or `model`.

In the cost report, list the Gemini TTS row as `imported / $0`.

## Merge audio

After verifying the WAV is non-empty and the video is long enough, run the bundled merge script instead of a hand-written ffmpeg command:

```bash
python .claude/skills/shiny-component-shorts/scripts/merge_audio.py \
  --project-dir generated/demo-name
```

The script measures the narration first, then applies loudnorm in linear two-pass mode so the -14 LUFS short-form target is hit accurately regardless of TTS voice. It also applies a 70 Hz high-pass and 150–250 ms edge fades to remove rumble and abrupt starts, encodes 48 kHz 192 kbps AAC, copies the video stream unchanged, and pads the audio so the clean recording keeps its final payoff when narration ends first.

Listen to the final output. Reject truncated narration, audible tag names, laughter, giggling, chuckling, any other unintended vocalization, awkward tag transitions, mispronounced code that changes meaning, or voiceover that describes a different state from the screen. If any laugh-like sound is present, regenerate after simplifying the inline direction; do not mask it with music or leave it in the final video.

## Cost reporting

Read exact Gemini usage and its estimate from `narration.usage.json`. Label calculated dollars as a paid-tier list-price estimate unless provider billing confirms an actual charge.

For Codex, use only usage or credits surfaced by the current harness or Codex Usage panel. If unavailable, report `Unavailable from this harness`; do not estimate hidden reasoning, cached input, or tool tokens from visible text.

Use this compact table:

| Service | Usage | Cost | Status |
| --- | ---: | ---: | --- |
| Gemini TTS | Exact tokens and duration | Provider value or estimate | Actual or paid-tier list-price estimate |
| Local voice cloning | Voice and duration | $0 API cost | Local MLX compute not priced |
| Codex | Harness-reported usage | Known value or unavailable | Subscription, credits, or unavailable |
| Local tools | FFmpeg, Playwright, Shiny | $0 API cost | Local compute not priced |

State the pricing date and currency. A known API subtotal must exclude unavailable Codex value. Never present an estimate as an invoice.
