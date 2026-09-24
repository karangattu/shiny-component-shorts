# TTS and cost reporting

Read this reference only when narration audio, a finished video with audio, or cost reporting is requested.

Check for `GEMINI_API_KEY`/`GOOGLE_API_KEY` only after audio has been requested and only when Gemini TTS will actually be called. Never check for, mention, or ask the user for these keys on a silent-video workflow, local voice-cloning workflow, or when importing existing narration; a missing key is an error only on the Gemini path. In a silent video's cost report, list the Gemini TTS row as `not used / $0`.

## Narration prompt

Write `artifacts/narration.txt` in this form:

```text
Synthesize this as a natural, curious tech explainer for a 45-second Shiny component video.

Audio profile:
A clear developer voice. Natural, conversational, precise, warm, and not salesy. No non-speech vocalizations.

Scene:
[One sentence describing the visible demo.]

Director's notes:
Speak at a natural conversational pace. Allow normal pauses between thoughts and before reveals; do not rush to fit the video. Emphasize the surprising behavior. Do not laugh, giggle, or chuckle. Do not add sighs, gasps, coughs, filler sounds, or any other non-speech vocalization. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[95–130 spoken words with 3–6 intentional pacing or emphasis cues.]
```

Before synthesis, edit the transcript for spoken delivery: use contractions, short sentences, and one thought per sentence. Replace awkward spoken identifiers with their meaning while the code card shows the exact API spelling. For example, say “wait three seconds before showing thinking” instead of reading `show_thinking_after_s` aloud. Preserve the feature's actual behavior and match each sentence to the visible proof; do not add filler merely to meet the word count.

Use three aligned controls:

1. Put the overall persona, emotional register, and default pace in `Audio profile` and `Director's notes`.
2. Write transcript language that naturally supports that performance.
3. Use bracketed tags only for a localized change that matches a visible beat.

Useful inline cues are limited to pacing and restrained emphasis:

- Pacing: `[short pause]` (about 250 ms), `[medium pause]` (about 500 ms), or `[long pause]` (about one second or more).
- Local delivery changes: `[slightly firmer]` when they match a visible beat.
- Do not use reaction or non-speech tags. The validator rejects laugh, laughter, giggle, and chuckle variants.

For a developer short, prefer a restrained arc: conversational hook, a short or medium pause before the reveal, slightly firmer delivery for the decisive code line, and a warm payoff. Do not stack tags, repeat the same cue mechanically, or use shouting, panic, crying, coughing, character voices, or any non-verbal sound.

Treat tags as preview-model hints, not a closed vocabulary or timing guarantee. Prefer the documented named pause tags over invented exact-duration syntax such as `[pause=1.0]` unless that syntax has been tested with the current model. Emotional adjective tags such as `[curious]`, `[scared]`, or `[bored]` can occasionally be vocalized; express the overall emotion in the director's notes and verify any inline adjective tag before keeping it. Do not include timestamps or visual stage directions in the transcript.

For a narrated series, vary the performance direction as deliberately as the visual direction. For example, use one curious discovery, one calm diagnostic explanation, one measured comparison, one focused accessibility demonstration, and one conversational reference-style proof rather than giving every video the same excited delivery.

## Generate audio

For a narrated deliverable, generate the audio before recording the video: the WAV's measured word timing is what `actions.yaml` cues resolve against (see the recording contract's Timing section). Word-count estimates drift enough to push actions out of sync with the spoken sentences.

Do not call Gemini unless the user requested audio. Never print, persist, or ask for the API key value.

If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is available, run:

```bash
python .claude/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input generated/demo-name/artifacts/narration.txt \
  --output generated/demo-name/artifacts/narration.wav \
  --usage-output generated/demo-name/artifacts/narration.usage.json
```

The generator statically validates the prompt (envelope structure, 95–130 words, 3–6 tags, and absence of laughter cues) before calling the API to prevent wasted spend. It uses Gemini 3.8 Flash TTS and chooses from the curated Sulafat (warm), Achird (friendly), Callirrhoe (easy-going), and Zubenelgenubi (casual) voices unless `--voice` overrides it. Treat preview model names and prices as unstable.

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
  "language": "English"
}
```

The user can select another saved WAV name or reference recording, correct `reference_text`, or choose `high`/`fast` quality. List available voices from `<engine_dir>/voice_samples/*.wav`; the API does not offer a saved-voice listing endpoint. `engine` accepts `qwen` or `omnivoice`; OmniVoice must be installed separately in the sibling project. Quality changes model/compute settings, not voice identity.

`POST /synthesize` receives multipart fields `text`, `ref_text`, `quality`, `language`, `engine`, `speed`, `output_format=wav`, plus the uploaded `reference_audio`. `GET /info` reports supported engine settings. `POST /transcribe` can help inspect the sample transcript. Consult the running `/docs` and sibling `src/api.py` for the exact contract. Only loopback HTTP origins are accepted, with redirects and proxies disabled. Omitting `api_url` uses the CLI; API failures are surfaced without silently switching providers.

Keep narration at a natural speed with natural pauses. The adapter forwards `speaking_rate` (0.5–1.5, default 1.0) to the engine's `speed` control; when the local voice runs fast, calibrate it down (typically 0.85–0.95) instead of accepting a rushed take. Never raise the rate above 1.0 to fit a recording, and never use `atempo`, time stretching, or silence removal to fit one either. Global performance prose and emphasis tags do not steer the local model; pause tags, punctuation, and the engine rate set the delivery. If delivery still sounds rushed after a rate change, revise the script or reference and regenerate.

After any voice, reference, transcript, or engine change, rerun `--phase narration`, then rerun the recorder's `--dry-run`: `cue` actions re-resolve against the new word timing on their own, so check the printed cue times rather than hand-retiming waits. Then rerun `--phase finish --approve-timing`. The finish gate rejects stale local narration even when timing approval is requested. Approval includes narration inputs and reference audio hashes.

## Measure word timing

Every narration source — Gemini, local voice, or imported audio — is measured the same way. The batch narration phase runs this automatically; run it yourself after writing or replacing `artifacts/narration.wav` outside the batch:

```bash
python .claude/skills/shiny-component-shorts/scripts/align_narration.py \
  --project-dir generated/demo-name
```

It transcribes the WAV locally with faster-whisper word timestamps (no API call, $0), aligns the recognized words to the `Transcript:`, and writes `artifacts/narration-timing.json` with every word's start and end, one span per transcript sentence, and a `transcript_check`: the word error rate, each expected-versus-heard difference, and any non-speech sound the recognizer heard. It prints the sentence times and the differences, and exits non-zero when the audio says something else (word error rate above 25%) or contains a laugh, sigh, or similar vocalization. The report is tied to the WAV's hash, so a replaced WAV is never timed with stale words.

This replaces listening as the gate for timing and content. Read the differences: a digit heard as a word ("8" for "eight") is normal and already normalized, but a heard `card` for an expected `chart`, or a dropped code name, means the take mispronounced it — regenerate. The model is `base.en` by default; set `SHORTS_ALIGN_MODEL` to use another faster-whisper model. When you can listen, still watch the final video with sound; when you cannot, say so, and rely on the transcript check and cue timings rather than guessing from silence gaps.

Keep the normal prompt envelope and its 3–6 cues in `narration.txt` so concept review and validation stay consistent. Before local synthesis, the adapter extracts only `Transcript:`, strips performance tags, and turns each pause tag into a line break (closing the previous thought with sentence punctuation). The whole text is then synthesized in **one request** and the engine's audio is used byte-for-byte: the engine places its own short pause at line breaks, so planned breath points survive without any inserted, joined, or post-processed audio. Punctuation supplies phrasing inside each line.

The local adapter writes the same `narration.wav`, timing report, and usage report as the Gemini path. Its usage report records `$0` paid API cost plus the measured pace (`words_per_minute`, articulation rate, pause density) and the `pace_gate_max_wpm` setting; `synthesis_requests` is 1 and `audio_modified` is false because the engine's audio is never assembled or altered. Every take is measured against the pace gate (`--max-wpm`, default 160 WPM, `max_wpm` in `tts-settings.json`; `0` disables it): a take above the gate is rejected automatically, so slow the voice or add pauses instead of approving a rushed take. Check its transcript check and cue times, listen when you can, and approve its measured timing before the finish phase, exactly as with any other narration source.

### Choose a natural local take

For new local narration, generate three independent takes of the finalized transcript and let the batch processor compare them:

```bash
python .claude/skills/shiny-component-shorts/scripts/batch_process.py \
  --phase takes --dirs generated/demo-name --takes 3
```

Each take is one continuous single-request synthesis with the video's `tts-settings.json` (same reference voice, engine, language, quality, and `speaking_rate`), generated one after another on the local device. The phase keeps every raw take in `artifacts/narration-takes/`, writes a copy of each at one common integrated loudness with linear gain only (-14 LUFS, lowered for all takes when any would pass -1.5 dBTP; never compressed, denoised, gated, or tempo-changed), and ranks the raw takes in `ranking.json` by objective penalties: transcript accuracy (word error rate), pace away from about 150 WPM, pauses longer than 1.4 s, clipping, and vocalizations. The phase only runs local voice cloning, so it never multiplies paid-provider calls; imported narration needs no takes.

The ranking replaces "listen and pick" when listening is unavailable, and narrows the audition when it is available: play the top takes' matched copies at the same volume and prefer natural emphasis and rhythm when two scores are close. Pin the choice — the recommended take or a named one — without hand-editing settings:

```bash
python .claude/skills/shiny-component-shorts/scripts/batch_process.py \
  --phase takes --dirs generated/demo-name --select-take recommended
```

That rewrites `tts-settings.json` to `{"audio_source": "artifacts/narration-takes/take-2-matched.wav", "audio_processing": "preserve"}`; the generation settings stay in `narration-takes/settings.json`. Rerun `--phase narration` to import and time the chosen take; the import path reuses it on reruns instead of synthesizing another. Report which take was chosen, its score, and whether it was auditioned. Do not replace narration under an already recorded video without re-running preflight and the finish phase.

### Continuous background and speech transitions

When listening is available, check the reference sample, generated WAV, and merged AAC at normal playback speed. Listen through quiet word endings and sentence gaps for hiss or room tone switching on/off, pumping, clicks, and clipped consonants. Pause duration and background continuity are separate problems: shortening a gap does not repair a noise floor that drops to digital zero. Compare raw and merged audio to locate the change before processing it; loudness normalization is not noise removal.

For new local narration, synthesize the single-request transcript described above. The engine's audio is used as-is — no inserted bed, no joins, no trims — so if it has audible background noise, prefer a cleaner reference copy and regenerate before recording; preserve the saved original voice sample. Do not hand-edit gaps or apply a hard noise gate to make speech sound cleaner.

For an existing recording with this defect, preserve the original and make a separate cleanup preview. Try gentle noise reduction with smooth spectral gains, keeping quiet speech intact. An FFmpeg starting point to audition is `afftdn=nr=10:nf=-45:tn=0:tr=0:gs=12`; tune it to the recording and compare at matched loudness, rather than applying it to every voice. If residual room tone still switches into digital silence, a very quiet continuous background can soften the contrast. Use that only when needed, disclose that sound was added, and audition it; pink noise around -60 dBFS RMS is an example starting level, not a universal target. Do not mistake masking for removal of the underlying noise.

Keep cleanup duration and sample count unchanged so the existing video stays aligned. If the user explicitly requests shorter pauses in an existing video, remove the same intervals from both streams, preserve speech edges, and recheck the visible reactions. Do not shorten pauses just to meet a duration target. Record the processing settings and compare the merged output as well as the WAV. Noise-floor measurements and successful decoding support verification but cannot establish that it sounds natural; if listening is unavailable, label the result an unauditioned preview rather than a verified final.

## Use existing narration audio

When the user supplies existing narration — a WAV, MP3, or a previously narrated video whose audio track is the narration — do not call Gemini and do not check for any API key. Import it instead:

```bash
python .claude/skills/shiny-component-shorts/scripts/import_narration.py \
  --source path/to/narrated.mp4 \
  --output generated/demo-name/artifacts/narration.wav \
  --usage-output generated/demo-name/artifacts/narration.usage.json
```

The script verifies the source has an audio stream, converts it to the pipeline's mono 24 kHz PCM WAV, and writes a `$0` usage report marked `Imported audio`. From there the workflow is identical to generated narration: run `align_narration.py` (the batch narration phase does it for you) and anchor `actions.yaml` with cues. Keep the `narration.txt` envelope's transcript matched to what the imported audio actually says; the transcript check fails when they differ.

For batch processing, set `{"audio_source": "path/to/narrated.mp4"}` in the video's `tts-settings.json` (relative paths resolve against the video directory); the narration phase then imports instead of synthesizing and adds the source file to the cache key. `audio_source` cannot be combined with `voice` or `model`.

In the cost report, list the Gemini TTS row as `imported / $0`.

## Merge audio

After verifying the WAV is non-empty and the video is long enough, run the bundled merge script instead of a hand-written ffmpeg command:

```bash
python .claude/skills/shiny-component-shorts/scripts/merge_audio.py \
  --project-dir generated/demo-name
```

By default, the script measures narration through a 70 Hz high-pass and applies constant gain toward -14 LUFS, limited by -1.5 dBTP headroom. It accepts a quieter result rather than invoking loudnorm dynamic compression. Use `--preserve-audio` for an approved take that must retain its gain and processing; batch runs use `"audio_processing": "preserve"`. Both modes:

- start the narration 0.15 s into the video (`NARRATION_OFFSET_SECONDS`), so the first word never lands on frame zero; the recorder and validator already time every cue to that offset,
- fade only the silent tail after the last word over about 0.3 s, so room tone eases out instead of cutting to digital silence; no word edge is ever faded,
- encode 48 kHz 192 kbps AAC, copy the video stream, and pad the ending.

A very quiet music bed is optional: pass `--bed path/to/bed.wav` (or set `"music_bed"` in `tts-settings.json` for batch runs). The bed loops to the video's length at -38 LUFS integrated by default (`--bed-lufs`), about 24 LU under the voice, and fades in and out over 1.2 s. Use only music the user supplied and has rights to; never add a bed silently, and disclose it in the final response. Check the encoded result: AAC conversion can change true peaks slightly.

Listen to the final output when you can. Reject truncated narration, audible tag names, laughter, giggling, chuckling, any other unintended vocalization, awkward tag transitions, mispronounced code that changes meaning, or voiceover that describes a different state from the screen. If any laugh-like sound is present, regenerate after simplifying the inline direction; do not mask it with music or leave it in the final video.

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
