---
name: shiny-component-shorts
description: Create interactive Shiny Python or R mini-apps, 30-second "Did you know?" video concepts, Gemini 3.1 TTS narration and audio, storyboards, recording automation, and editing notes. Use when the user provides a Shiny component name, docs URL, or existing Shiny app path, or asks for a short demo or video around a Shiny UI feature.
---

# Shiny Component Shorts (Claude Code)

Create one-screen Shiny demos that make one hidden component behavior obvious in about 30 seconds.

## Core contract

- One video = one trick, not a component tutorial.
- Prove the trick on screen through a direct comparison or a two-way proof.
- Use at least three meaningful actions and three visible state changes in recordings.
- Prefer Python Shiny Express unless the user requests R or R is materially clearer.
- Default to a true 9:16 vertical composition (1440×2560). Use landscape only on explicit request.
- Keep the app small, realistic, and understandable without narration.
- Reserve the top 20% and bottom 20% of every frame for later branding; make the app fill the available horizontal space in the middle 60% height band.
- Use only the Shiny preset palette, led by `#007BC2`, with `#1D1F21` text on light surfaces and `#FFFFFF` text on dark surfaces.
- Use official Shiny documentation as the source of truth.
- Run the bundled shared scripts; never generate a demo-specific recorder or validator.

Read [references/creative-playbook.md](references/creative-playbook.md) before choosing the feature or writing the app. For recordings or editing, also read [references/short-form-pacing.md](references/short-form-pacing.md) and [references/recording-contract.md](references/recording-contract.md). For narration audio or cost reporting, read [references/tts-and-costs.md](references/tts-and-costs.md).

## Choose the workflow

Create only what the user requested.

### Idea only

Return:

1. Component and language
2. Best video angle
3. Problem-led hook
4. Mini-app concept
5. Three to five variations
6. A 30-second storyboard
7. An exact action → visible reaction plan with at least three planning beats

Do not create files, recording automation, audio, or cost reports.

### Multi-video series

Use this workflow when the user asks for multiple videos about one component. Create no more than five videos for that component, even if the user requests more.

1. Research the component once, then identify up to five genuinely distinct visual behaviors.
2. Score every behavior with the creative playbook's feature questions. Omit weak ideas rather than padding the series to the requested count.
3. Give each video its own complete idea-only deliverables: angle, problem-led hook, mini-app concept, variations, 30-second storyboard, and action → visible reaction plan.
4. Keep one video focused on one hidden behavior. Changes to labels, data, colors, narration, or setting alone do not make a distinct video.
5. Make the videos independently producible and order them strongest first.
6. Before implementation, assign each video a one-line visual direction covering backdrop mode, palette, typography, composition, and setting. For series of three or more, include both light and dark or color-led treatments, and do not let one backdrop treatment dominate more than about half the series unless the user requests a fixed brand system or the component behavior requires it.
7. When audio is requested, assign each video a one-line performance direction covering persona, emotional arc, pace, and one or two purposeful inline cues. Vary the delivery across the series without turning every short into a character voice.

If the user requests runnable apps, recordings, or finished videos, apply the corresponding workflow separately to each selected idea. Use one directory per video and verify every requested output independently.

### Runnable app

Create the idea deliverables plus a minimal `app.py` or `app.R`. Run the app and verify the chosen behavior. Do not create recording or narration files unless requested.

### Existing app

Use this workflow when the user provides a local path to an existing R Shiny or Shiny for Python app and wants one fascinating behavior other developers should know about.

1. Resolve the path. If it points to `app.R` or `app.py`, use its parent as the app directory. Inspect the entry point, modules, dependency manifests, and local run instructions before starting the app. Detect the language from the source; ask only when both runtimes are plausible.
2. Do not modify, copy, or restyle the existing app unless the user explicitly asks for source changes. Preserve its typography, palette, layout, data, and behavior; the four-font rotation applies only to newly created demos.
3. Run the app locally in its declared environment and inspect the rendered UI. Do not expose secrets or trigger external writes, messages, purchases, destructive operations, or production-data mutations while exploring or recording.
4. Inventory surprising reactive behavior, server-driven updates, validation, layout changes, accessibility, or state synchronization already present in the app. Choose one behavior that passes the creative playbook's proof rule, has a concise existing source line, and supports three meaningful action → reaction beats.
5. Keep the original app as the recording subject. Put `actions.yaml`, narration, and `artifacts/` in a separate sidecar production directory. Run the recorder with that directory as `--project-dir`, the existing source directory as `--app-dir`, and the detected `--app-type r|python`; pass the same two directories to the validator.
6. If no behavior passes the proof rule, report the strongest near-misses and why they are not visually provable; do not manufacture interactions or quietly rewrite the app.

### Silent recording

Create this minimum structure:

```text
demo-name/
├── app.py or app.R
├── actions.yaml
└── artifacts/
    ├── narration.txt
    ├── demo.webm
    ├── demo.mp4
    ├── recording.json
    └── final.png
```

Write the complete narration prompt envelope defined in the creative playbook even for a silent recording, so action timing has a concrete target. Do not write only the transcript, and do not call a paid TTS API unless audio is requested.

Run the bundled shared recorder:

```bash
python .claude/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir demo-name \
  --app-type python \
  --actions actions.yaml
```

Then validate it:

```bash
python .claude/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir demo-name
```

Treat validator errors as blocking. Missing-overlay warnings are expected for clean recordings and do not need to be fixed.

### Narrated or finished video

Generate the audio before recording so action timing follows the real narration instead of a word-count estimate:

1. Write `artifacts/narration.txt` and generate `artifacts/narration.wav` (see [references/tts-and-costs.md](references/tts-and-costs.md)); verify the WAV is non-empty and listen for defects before recording anything.
2. Measure the audio: exact duration with `ffprobe`, sentence boundaries with `ffmpeg -af silencedetect` (see the recording contract's Timing section).
3. Author or adjust `actions.yaml` against those measurements: the first meaningful action must be underway during the hook's first sentence, each visible reaction must begin at or slightly before the sentence that describes it, and the video must run one to three seconds past the narration.
4. Record and validate with `--require-audio`, then merge.

Merge with loudness normalization to the short-form target (-14 LUFS):

```bash
ffmpeg -i artifacts/demo.mp4 -i artifacts/narration.wav \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11,apad" \
  -c:v copy -c:a aac -shortest artifacts/final_with_audio.mp4
```

If edited overlays are requested, preserve `artifacts/demo.mp4` as the clean browser recording and write edited outputs separately. Do not overwrite the clean recording.

## Planning beats and clean recordings

Use `Reveal`, `Proof`, `Code`, and `Payoff` to organize the storyboard and time the actions. They are internal production labels and must not appear as on-screen text, numbered state chips, or a progress rail.

Do not add `beat`, `label`, or `caption` actions to `actions.yaml`, and omit the top-level `overlays` block. The browser deliverable should remain a clean recording of the app, with only the concise `code` action rendered when the storyboard reaches its code section. See [references/recording-contract.md](references/recording-contract.md).

## Research and concept selection

1. Inspect the official docs for the named component.
2. List the genuinely visual behaviors: updates, reactive values, layout effects, validation, accessibility, or state changes.
3. Reject behaviors that need explanation before they become visible.
4. Choose the strongest behavior that supports a direct comparison or two-way proof without unrelated controls.
5. Confirm the exact API names and selectors before writing the app.

If the proposed action plan cannot produce three meaningful reactions from the same trick, choose a stronger angle.

## App rules

- Prefer one primary card or panel sized for a vertical frame.
- Rotate app typography in this fixed order, then repeat: Mona Sans → IBM Plex Sans → Source Sans 3 → Manrope. Across a planned series, assign the families by video order; do not choose randomly or switch typefaces inside a video.
- Use one font family consistently for all app UI text and controls. Load weights 400, 500, 600, and 700 from the selected Google Fonts URL: `https://fonts.googleapis.com/css2?family=Mona+Sans:wght@400;500;600;700&display=swap`, `https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap`, `https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap`, or `https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap`. Set `--bs-body-font-family` to the selected family followed by `system-ui, sans-serif`, and apply the same `font-family` stack to `body`, `button`, `input`, `select`, and `textarea`.
- The font rule works in both languages: use `tags$head(tags$link(...), tags$style(...))` in R Shiny and `ui.tags.head(ui.tags.link(...), ui.tags.style(...))` in Shiny for Python.
- Do not render a visible app title, page title, eyebrow, kicker, series label, or oversized marketing headline. Keep the problem-led hook in the storyboard, narration, or later edit; start the app UI directly with the component or its realistic field/task label.
- Keep the top 20% and bottom 20% visually empty. In the middle band, use 3–5% side gutters, remove narrow desktop `max-width` constraints, and stretch the primary panel across the available horizontal space.
- Use the Shiny preset palette consistently: primary `#007BC2`; light surfaces `#FFFFFF`/`#F8F8F8` with `#1D1F21` primary text and `#48505F` secondary text; dark surfaces `#1D1F21`/`#202020` with `#FFFFFF` primary text and `#CDD4DA` secondary text. Use other Shiny semantic colors only when they convey state.
- Use tiny inline data or built-in data.
- Use Font Awesome icons where a small inline icon makes a label, button, or state readout easier to scan: `from faicons import icon_svg` in Shiny for Python, `fontawesome::fa()` or `shiny::icon()` in R. Match the icon to the adjacent text color and size, and skip icons that would be pure decoration or one per element by rote.
- Use realistic labels and uneven values; avoid lorem ipsum, `Item 1`, `foo`, or synthetic filler.
- Add stable input IDs and selectors for every recorded target; no random Bootstrap-generated IDs.
- Keep the code line featured in the video verbatim in the app.
- Do not add decorative controls just to create motion.
- Make comparison states visible in the same composition when practical.

## Story and narration rules

Use this sequence:

| Time | Beat | Required behavior |
| ---: | --- | --- |
| 0–3 s | Problem | Begin the first meaningful action by second 2 |
| 3–8 s | Reveal | Show the hidden behavior clearly |
| 8–19 s | Proof | Repeat, reverse, or contrast it |
| 19–26 s | Code | Show only the decisive code line over the live app |
| 26–30 s | Payoff | End on the strongest result |

These beat names are planning labels only; never render them in the video.

Keep narration around 60–85 spoken words. Make every sentence describe something literally visible. Use contractions and natural developer language; avoid stock AI phrasing, parameter tours, and forced punchlines. Never use laughter, giggling, chuckling, or other non-speech vocalizations. For audio, use the prompt-and-tag hierarchy and verification rules in [references/tts-and-costs.md](references/tts-and-costs.md); tags must support the visible moment rather than decorate every sentence.

## Recording rules

- Author `actions.yaml` from the storyboard, not after recording.
- Keep storyboard beat names out of `actions.yaml`; do not add `beat` actions or an `overlays` block.
- The recorder pre-validates every selector on the loaded page and fails fast listing any that are missing; fix the app or the selector, never loosen a selector to something unstable.
- Use `type` for text visibly entered by a person and `fill` only for clearing or paste-like actions.
- Keep ordinary waits between 500 and 3000 ms; vary them and let the biggest reveal breathe.
- Keep the total wait before the first meaningful action at or under 1500 ms; the first action must be underway while the narration's opening words are spoken. The validator rejects opening waits over 2000 ms.
- Include one concise animated `code` action timed to the narration's code sentence.
- In horizontal mode, the `code` action must use the recorder's side-by-side layout so the app remains visible beside the code; do not cover the app with the code panel.
- Keep the action sequence at least as long as the estimated narration. When it comes up short, lengthen the holds after reveals or add another proof beat; never pad the opening wait — that delays the first action past the narration's hook.
- End with `screenshot: {path: "artifacts/final.png"}`.
- Let selector, server, browser, FFmpeg, and validation failures stop the workflow.
- Never kill an unknown process to reclaim a port; the recorder refuses occupied ports and retries flaky app startups on its own.

## Verification gate

Do not report completion until all requested outputs exist and are non-empty.

For an app:

- Start it and exercise the chosen behavior.
- Confirm reactive output and stable selectors.

For a recording:

- Run `validate_demo.py` successfully; missing-overlay warnings are expected for clean recordings.
- Confirm `artifacts/demo.mp4` is 1440×2560 unless landscape was explicitly requested.
- Inspect the first, reveal, code, and final frames at phone size; confirm no planning beat names or progress rail appear over the app.
- Confirm the visible cursor reaches each interactive target.
- Confirm the narration would finish before the video ends.

For audio:

- Confirm `artifacts/narration.wav` and `artifacts/final_with_audio.mp4` are non-empty.
- Listen for truncation, incorrect code pronunciation, mismatched timing, laughing, giggling, chuckling, or any other unintended vocal sound.

Do not claim an artifact was generated if its file does not exist.

## Cost reporting (Claude Code)

End every artifact-generating workflow with a `Cost report` section; when writing a demo directory, also write it to `artifacts/cost-report.md`.

| Service | Usage | Cost | Status |
| --- | ---: | ---: | --- |
| Gemini 3.1 Flash TTS | tokens + audio duration | $ estimate | Paid-tier list-price estimate |
| Claude Code | session tokens | $ estimate | List-price estimate from session transcript |
| Local tools | FFmpeg, Playwright, Shiny | $0 API cost | Local compute not priced |

Rules:

1. Read Gemini usage from `artifacts/narration.usage.json`; report exact tokens, label dollars as a paid-tier list-price estimate.
2. Estimate the interactive session cost with the bundled `scripts/claude_session_cost.py`:

   ```bash
   python3 .claude/skills/shiny-component-shorts/scripts/claude_session_cost.py \
     --project-dir ~/.claude/projects/<project-slug> \
     --session <session-uuid>   # omit to use the most recent transcript
   ```

   It measures the whole session so far; for a per-video figure run it before and after and report the delta. Point the user at `/cost` for the harness-reported value.
3. Match the label to the billing model: usage-billed accounts — the estimate approximates the actual charge; subscription accounts — report it as list-price equivalent, never as the invoice amount.
4. State the pricing date and currency. Never invent unavailable usage numbers.

## Final response

Lead with what was created and verified. Link to the app and the final requested media. Mention any intentionally omitted optional outputs, then the cost report when applicable.
