# TTS and cost reporting

Read this reference only when narration audio, a finished video with audio, or cost reporting is requested.

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
python .agents/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input demo-name/artifacts/narration.txt \
  --output demo-name/artifacts/narration.wav \
  --usage-output demo-name/artifacts/narration.usage.json
```

The generator uses Gemini 3.1 Flash TTS Preview and chooses from the curated Kore, Erinome, Charon, and Achird voices unless `--voice` overrides it. Treat preview model names and prices as unstable.

If both key variables exist and authentication fails, note that the Google SDK may prioritize `GOOGLE_API_KEY`; do not reveal either value.

## Merge audio

After verifying the WAV is non-empty and the video is long enough, run the bundled merge script instead of a hand-written ffmpeg command:

```bash
python .agents/skills/shiny-component-shorts/scripts/merge_audio.py \
  --project-dir demo-name
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
| Codex | Harness-reported usage | Known value or unavailable | Subscription, credits, or unavailable |
| Local tools | FFmpeg, Playwright, Shiny | $0 API cost | Local compute not priced |

State the pricing date and currency. A known API subtotal must exclude unavailable Codex value. Never present an estimate as an invoice.
