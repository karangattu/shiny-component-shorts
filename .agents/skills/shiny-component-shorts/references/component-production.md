# Component video production

Use this workflow for Python and R component videos. Editorial release/blog videos keep their shot-based workflow.

## Preview the complete story before narration

Use the production environment’s interpreter and the absolute installed skill path. After verifying selectors and writing actions.yaml, execute the action sequence without recording or generating audio:

```bash
/path/to/venv/bin/python /path/to/shiny-component-shorts/scripts/record_demo.py \
  --project-dir /path/to/demo --dry-run --preview-states
```

Add `--app-type r` for an R app; add `--app-dir /path/to/app` for a sidecar. This opt-in command executes the same interactions as the recording. Ordinary `--dry-run` still checks the initial page and measured cues without executing them.

The preview skips narration cues and reading holds, captures idle/interacting/busy/completed states and **every** code excerpt, and runs both orientations. It preserves final.png, recordings, and narration. Inspect every numbered phone-size sheet under `artifacts/preflight/<orientation>/`. The index at `artifacts/preflight/index.json` lists frames, elapsed preview times, errors, and wrapping warnings. Review transient panels, result visibility, control spacing, and source readability. Shorten or reframe awkward code; do not silently shrink its font.

Previews are evidence, not an automatic aesthetic verdict. Fix obstructed content and inspect again before a full encode.

## Read source directly

Prefer inclusive line ranges instead of copied code. Line numbers are one-based:

```yaml
- cue: "here's the reactive part"
- code:
    source_file: app.py
    source_lines: [47, 52]
    highlight_lines: [49, 51]
    hold_until: "the location changes"
    reading_pause: 2
```

Replace the example ranges and phrases with the actual source and narration. `highlight_lines` is an inclusive range inside `source_lines`; omitting it highlights the excerpt. The helper reads the file at production time, preserves its relative indentation, and supplies the real filename and line numbers. Paths and symlinks must stay inside the app directory. R uses `source_file: app.R`; frontend source files work too.

Do not mix `source_lines` with copied `before`/`text`/`after`. Existing copied excerpts remain supported and retain source verification. When the source changes, review the selected range again to ensure it still explains the intended behavior.

## Hold through the spoken explanation

After generating/importing narration and measuring word timing, `hold_until` keeps code visible through the **end** of the named phrase plus `reading_pause` seconds. The preceding `cue` supplies its reveal time. Repeated phrases accept `{phrase: "...", occurrence: 2}`. Use the existing numeric `duration` for silent videos or old configurations; do not combine it with `hold_until`.

The normal cued dry-run resolves these holds and rejects missing phrases, reversed holds, and overlap with the next cue before recording. If explanation and reading time do not fit, revise the narration or action plan. Never accelerate speech. Match the reading pause to the intentional silence in the approved audio; narration alignment is approximate to a video frame.

## Wait for an observable result

`wait_stream` still supports a changing region followed by a quiet window. For a native panel that closes, prefer an explicit completion condition:

```yaml
- click: "#run"
- wait_stream:
    completion:
      selector: "#shiny-notification-panel"
      state: detached
    timeout: 15000
    expect_ms: 6000
```

Hidden/detached checks must first observe the target visible/attached, so an initially absent panel does not falsely mean the job finished. For a fast job whose panel cannot be observed, use a stable result instead:

```yaml
- wait_stream:
    completion:
      selector: "#result"
      text: "6 files checked"
    timeout: 15000
    expect_ms: 6000
```

`text` means contains this exact text. Supported states are visible, hidden, attached, and detached. Visible/text conditions can already be true; for repeated jobs choose an indicator that changes for each run, such as the busy state. Use `html.shiny-busy` with `state: detached` when that app exposes Shiny's busy class. Do not use a previous result as proof that a new run finished.

With completion checks, `expect_ms` estimates the total completion span for timing simulation. With quiet-window checks, it estimates the changing portion before `quiet_ms`. Actual recording always waits for the real condition and fails on timeout. A disappearing quiet-window region no longer causes a locator hang; use a stable ancestor when later content updates also matter.

## Narration and final review

Voice rhythm, sentence lengths, contractions, and stylistic wording are advisory warnings. Do not add filler merely to satisfy them. Empty scripts, non-speech vocalization cues, and failed audio transcript checks remain errors. Transcription comparison normalizes numeric currency and common equivalent forms such as filename/file name; raw heard text and genuine differences remain available. Wrong amounts are still different.

After finishing, review_frames.py automatically samples every code action from its measured appearance time, even when it waited on a cue. Inspect all code and result frames in both orientations. Listen when possible; keep the existing explicit unauditioned-audio disclosure when it is not.
