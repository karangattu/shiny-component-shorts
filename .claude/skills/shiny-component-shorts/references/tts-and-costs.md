# TTS and cost reporting

Read this reference only when narration audio, a finished video with audio, or cost reporting is requested.

## Narration prompt

Write `artifacts/narration.txt` in this form:

```text
Synthesize this as a natural, curious tech explainer for a 30-second vertical video.

Audio profile:
A clear developer voice. Brisk, precise, lightly amused, and not salesy.

Scene:
[One sentence describing the visible demo.]

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[60–85 spoken words with 3–6 light delivery tags.]
```

Prefer `[curious]`, `[amazed]`, `[serious]`, `[whispers]`, `[laughs]`, `[very fast]`, and `[very slow]`. Tags are hints, not guaranteed controls. Do not include timestamps or visual stage directions in the transcript.

## Generate audio

Do not call Gemini unless the user requested audio. Never print, persist, or ask for the API key value.

If `GEMINI_API_KEY` or `GOOGLE_API_KEY` is available, run:

```bash
python .claude/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input demo-name/artifacts/narration.txt \
  --output demo-name/artifacts/narration.wav \
  --usage-output demo-name/artifacts/narration.usage.json
```

The generator uses Gemini 3.1 Flash TTS Preview and chooses from the curated Kore, Erinome, Charon, and Achird voices unless `--voice` overrides it. Treat preview model names and prices as unstable.

If both key variables exist and authentication fails, note that the Google SDK may prioritize `GOOGLE_API_KEY`; do not reveal either value.

## Merge audio

After verifying the WAV is non-empty and the video is long enough:

```bash
ffmpeg -y \
  -i demo-name/artifacts/demo.mp4 \
  -i demo-name/artifacts/narration.wav \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" \
  -c:v copy -c:a aac -shortest \
  demo-name/artifacts/final_with_audio.mp4
```

The `loudnorm` filter normalizes the narration to -14 LUFS, the loudness target short-form platforms use, so videos in a series play at consistent volume regardless of TTS voice.

Listen to the final output. Reject truncated narration, mispronounced code that changes meaning, or voiceover that describes a different state from the screen.

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
