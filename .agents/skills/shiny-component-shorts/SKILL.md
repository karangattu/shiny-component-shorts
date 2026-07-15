---
name: shiny-component-shorts
description: Create focused Shiny Python or R mini-apps, 30-second component video concepts, browser recordings, Gemini TTS narration, and finished short-form video artifacts. Use when a user names a Shiny component, provides a Shiny docs URL, requests a component demo, or asks for a short video about a Shiny UI behavior.
---

# Shiny Component Shorts

Create one-screen Shiny demos that make one hidden component behavior obvious in about 30 seconds.

## Core contract

- Make one video about one trick, not a component tutorial.
- Prove the trick on screen through either a direct comparison or two-way proof.
- Use at least three meaningful actions and three visible state changes for recordings.
- Prefer Python Shiny Express unless the user requests R or R is materially clearer.
- Default to a true 9:16 vertical composition. Use landscape only when the user explicitly requests it.
- Keep the app small, realistic, and understandable without narration.
- Use official Shiny documentation as the source of truth.

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
6. Before implementation, assign each video a one-line visual direction covering backdrop mode, palette, composition, and setting. For series of three or more, include both light and dark or color-led treatments, and do not let one backdrop treatment dominate more than about half the series unless the user requests a fixed brand system or the component behavior requires it.

If the user requests runnable apps, recordings, or finished videos, apply the corresponding workflow separately to each selected idea. Use one directory per video and verify every requested output independently.

### Runnable app

Create the idea deliverables plus a minimal `app.py` or `app.R`. Run the app and verify the chosen behavior. Do not create recording or narration files unless requested.

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

Run the shared recorder; never generate a demo-specific recorder:

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir demo-name \
  --app-type python \
  --actions actions.yaml
```

Then validate it:

```bash
python .agents/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir demo-name
```

### Narrated or finished video

Complete the silent workflow first. Then generate TTS only when requested, merge audio only after verifying the WAV, and validate with `--require-audio`.

If edited overlays are requested, preserve `artifacts/demo.mp4` as the clean browser recording and write edited outputs separately. Do not overwrite the clean recording.

## Research and concept selection

1. Inspect the official docs for the named component.
2. List the genuinely visual behaviors: updates, reactive values, layout effects, validation, accessibility, or state changes.
3. Reject behaviors that need explanation before they become visible.
4. Choose the strongest behavior that supports a direct comparison or two-way proof without unrelated controls.
5. Confirm the exact API names and selectors before writing the app.

If the proposed action plan cannot produce three meaningful reactions from the same trick, choose a stronger angle.

## App rules

- Prefer one primary card or panel.
- Use tiny inline data or built-in data.
- Use realistic labels and uneven values; avoid lorem ipsum, `Item 1`, `foo`, or synthetic filler.
- Add stable input IDs and selectors for every recorded target.
- Do not use random Bootstrap-generated IDs.
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

These beat names are planning labels only. They organize the storyboard, action timing, and review frames; do not render them as labels, chips, or a progress rail in the video.

Keep narration around 60–85 spoken words. Make every sentence describe something literally visible. Use contractions and natural developer language; avoid stock AI phrasing, parameter tours, and forced punchlines.

## Recording rules

- Author `actions.yaml` from the storyboard, not after recording.
- Keep storyboard beat names out of `actions.yaml`; they are not recorded actions.
- Use `type` for text visibly entered by a person and `fill` only for clearing or paste-like actions.
- Keep ordinary waits between 500 and 3000 ms.
- Use varied waits and allow the biggest reveal to breathe.
- Include one concise animated `code` action timed to the narration’s code sentence.
- Keep the action sequence at least as long as the estimated narration.
- End with `screenshot: {path: "artifacts/final.png"}`.
- Let selector, server, browser, FFmpeg, and validation failures stop the workflow.
- Never kill an unknown process to reclaim a port.

## Verification gate

Do not report completion until all requested outputs exist and are non-empty.

For an app:

- Start it and exercise the chosen behavior.
- Confirm reactive output and stable selectors.

For a recording:

- Run `validate_demo.py` successfully.
- Confirm `artifacts/demo.mp4` is 720×1280 unless landscape was explicitly requested.
- Inspect the first, reveal, code, and final frames at phone size.
- Confirm the visible cursor reaches each interactive target.
- Confirm the narration would finish before the video ends.

For audio:

- Confirm `artifacts/narration.wav` and `artifacts/final_with_audio.mp4` are non-empty.
- Listen for truncation, incorrect code pronunciation, or mismatched timing.

Do not claim an artifact was generated if its file does not exist.

## Final response

Lead with what was created and verified. Link to the app and final requested media. Mention any intentionally omitted optional outputs. Include a cost report only when an artifact-generating workflow used a paid API or the user requested cost information; never invent unavailable Codex usage.
