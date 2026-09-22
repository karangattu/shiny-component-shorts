# Recording contract

Read this reference when creating `actions.yaml`, recording a demo, or diagnosing recording failures.

## Shared recorder

Use the bundled recorder directly:

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/demo-name \
  --app-type python \
  --actions actions.yaml
```

Options:

- `--app-type python|r` selects the Shiny runtime.
- `--app-dir` optionally selects a separate source directory containing `app.py` or `app.R`; it defaults to `--project-dir`.
- `--actions` is relative to the demo directory unless absolute.
- `--orientation vertical|horizontal` overrides `orientation:` in the YAML.
- Vertical is the default. Set horizontal only when the user explicitly requests it.
- The recorder preserves a 720×1280 or 1280×720 logical layout and launches Chromium in native 2× HiDPI mode, producing true 1440×2560 or 2560×1440 video without changing the composition.
- `--capture screencast` (the default) records Chromium's own compositor frames at full resolution, stamped on the same clock as the actions, and encodes constant 30 fps H.264. The action timeline and the video therefore agree exactly. `--capture playwright` falls back to Playwright's 25 fps WebM recorder, whose start is only approximately aligned; use it only if screencast capture fails on a machine.

Author the app with an empty top 20% and bottom 20% for later branding. The app belongs in the middle 60% band and should span the available horizontal space between 3–5% side gutters.

The `code` action is orientation-aware. Vertical recordings anchor the panel near the bottom edge of the frame (a 4% margin), growing upward as needed, so it fills the bottom half and sits below the component instead of covering it; during the code beat the panel may occupy the reserved bottom 20%. Compose the app toward the top of the band so the two never fight. Horizontal recordings switch to a side-by-side composition: the live app reflows on the left while the code panel occupies the right, so neither is hidden. The code panel uses the Shiny preset palette: `#007BC2` accent, `#1D1F21`/`#202020` dark surfaces, `#FFFFFF` primary text, and `#CDD4DA` secondary text.

The recorder refuses to start if its port is already occupied. Stop the known process yourself; never kill an unknown listener automatically.

## Preflight

`--dry-run` runs everything the recorder does before the first action and nothing after it: it loads `actions.yaml`, rejects malformed actions and code cards, starts the app, waits for the Shiny session, scans for a **Shiny Client Errors** panel, resolves every selector on the loaded page, and screenshots the composition.

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/demo-name \
  --app-type python \
  --actions actions.yaml \
  --dry-run
```

It also resolves every `cue` against the current narration's word timing and prints each cue's video time, so a misquoted phrase or stale timing fails here instead of mid-take. It records no video, writes no `demo.mp4`, `recording.json`, or `final.png`, and exits non-zero when anything is wrong. It writes three artifacts instead:

- `artifacts/preflight.png` — the composition at recording viewport, for checking gutters, the empty top and bottom bands, and control padding.
- `artifacts/preflight-phone.png` — the same frame at phone width; read this one.
- `artifacts/preflight-app.log` — the app's server output, reported only when the preflight fails.

Selectors named by a `wait_for` action are exempt: declaring them there says they appear asynchronously after an interaction, so the preflight lists them as deferred instead of demanding them on the initial page.

Run it before every full take, and after every app or selector change. A take that dies on a missing selector costs a browser run, an encode, a validation, and a frame review; the preflight costs one page load.

## Brand logo

Every recording carries the Shiny wordmark in the top-left of the reserved top 20% band. The recorder injects it as a fixed overlay before the app loads: 144 logical px wide in vertical recordings (20% of the 720 px logical frame), 180 px in horizontal ones, inset 4% from the top and left edges, sized to stay legible on a phone screen. The artwork renders as it ships, untinted; because its ink is black, the only treatment is a flip to white on backdrops whose relative luminance falls under 0.5 — dark surfaces, and the `#007BC2` primary — so it never disappears into the app. The logo stays visible. Preflight and recording fail if content overlaps it or the logo leaves the top branding band; fix the layout rather than hiding the wordmark. Inspect its size and contrast in the phone-size review sheet.

Keep that corner clear: the top band is already reserved, so no app UI, no in-app logo of your own, and no code card competes with it. `artifacts/recording.json` records the stamped logo under `logo`, and the validator rejects a recording whose `recording.json` has no `logo` entry — that means the video predates the brand overlay and must be re-recorded. Pass `--logo path/to/file.png` only when a demo needs a different mark; the default asset lives at `.agents/skills/shiny-component-shorts/assets/shiny-logo.png`.

## Client-error safety contract

No example may be recorded or delivered with a **Shiny Client Errors** panel visible. Assign unique output IDs across the complete rendered page, including conditional UI, modules, and repeated components. Exercise the full action sequence before accepting the app because some duplicate outputs appear only after reactive UI is inserted.

The shared recorder checks for the panel after startup and after the action run. Detection is a blocking failure: fix the duplicate output IDs or other client error, restart the app, and record again from the beginning. Never click **Dismiss all**, hide the panel with CSS, crop it out, or cover it with the code card. During final review, inspect the first, reveal, code, and final frames and reject the video if the panel appears in any frame.

For an existing app, create a sidecar production directory and keep the source separate:

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/interesting-filter \
  --app-dir /path/to/existing-app \
  --app-type r \
  --actions actions.yaml
```

The existing app remains unchanged. The recorder launches it from `--app-dir` while resolving `actions.yaml`, screenshots, narration, and all video artifacts under `--project-dir`.

Validate the sidecar against the same source directory:

```bash
python .agents/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir generated/interesting-filter \
  --app-dir /path/to/existing-app
```

## Action file

```yaml
url: "http://127.0.0.1:8000"
video_name: "demo.webm"
orientation: "vertical"

actions:
  - wait_for: "#notes"
  - wait: 900
  - cue: "type a few standup notes"
  - type:
      selector: "#notes"
      value: "Standup notes:\n- demo the resize"
      delay: 45
  - click: "#reset"
  - drag:
      selector: "#window + .irs .irs-bar"
      delta_x: 120
      delta_y: 0
      steps: 24
  - select_option:
      selector: "#view"
      value: "orders"
  - hover: "#result"
  - fill:
      selector: "#paste-target"
      value: "Pasted text"
  - press:
      selector: "#notes"
      key: "Escape"
  - cue: "one argument does it"
  - code:
      title: "app.py"
      start_line: 42
      before: |
        @render.ui
        def note_field():
      text: |
            ui.input_text_area("notes", autoresize=True)
      after: |
            return ui.div("Saved")
  - screenshot:
      path: "artifacts/final.png"
```

Supported actions are `wait_for`, `wait`, `cue`, `click`, `drag`, `select_option`, `hover`, `fill`, `type`, `press`, `code`, and `screenshot`. Each list item must contain exactly one action.

Storyboard beats such as `Reveal`, `Proof`, `Code`, and `Payoff` are planning metadata only. Do not add them to `actions.yaml` or render them over the recording.

## Action semantics

- `wait_for` waits for a selector to be attached, including content inside a collapsed component.
- `wait` uses milliseconds. Keep ordinary waits between 500 and 3000 ms.
- `cue` anchors the very next visible action (`click`, `drag`, `select_option`, `hover`, `fill`, `type`, `press`, or `code`) to the moment a phrase is spoken: `cue: "switch to seven days"`, `cue: {phrase: "run it", occurrence: 2}` for a repeated phrase, or `cue: {at: 12.4}` for a narration time in seconds. Quote words exactly as they appear in the `Transcript:`; case, punctuation, hyphens, and digits-versus-words do not matter. The pointer leaves early enough to arrive, then presses, types, drags, or shows the code card exactly on the phrase — whatever the machine speed. Nothing may sit between a cue and its action.
- `click` visibly moves the injected cursor along a gentle arc — quicker for short hops, slower for long reaches — then settles and shows a press pulse. The cursor already rests in the empty bottom band on the first frame.
- `drag` moves from the center of `selector` by `delta_x` and `delta_y` pixels with an optional `steps` count. Use it for sliders, splitters, and other genuine drag interactions.
- `select_option` targets a native select value.
- `hover` moves the visible cursor without clicking.
- `fill` changes a field instantly; reserve it for clearing or realistic paste actions.
- `type` clicks, focuses, moves the caret to the end, and types one key at a time with a person's uneven rhythm — quicker runs, short beats after spaces and punctuation — averaging `delay` (35–70 ms per character).
- `press` sends one named key to the selector.
- `code` types a compact, syntax-highlighted Shiny-branded editor card, holds it by reading time, then fades it out. Its `text` is the highlighted focus line; `before` and `after` blocks show dimmed real source context, and `start_line` keeps the gutter honest. Make that context an authentic slice of the app: include the code that surrounds the trick — for a UI feature, the enclosing UI component plus the related server logic (or the reverse when the server line is the star) — copied verbatim from the app source, typically 6–14 dimmed lines total, and highlight only the decisive line or two. Do not paste the whole app or invent tidied pseudo-source: every non-comment line must exist in the app source exactly, and indentation must mirror the source — the validator permits only one uniform dedent across the whole card, so relative indentation is preserved for both Python and R. In YAML, use a block indentation indicator (for example `text: |2` or `after: |2`) whenever a block's lines all share leading whitespace, otherwise YAML strips it silently. Place any explanatory comment at the end of `before`, directly above the focus line — never in `after`, where a comment below the highlighted code reads as an afterthought and distracts from it. In vertical mode the card fills the bottom half of the frame, anchored near the bottom edge; in horizontal mode it uses the side-by-side layout instead of overlaying the app. The card fades and slides in and out (about 0.3 s), and the horizontal app reflow eases instead of snapping.
- `screenshot` writes a full-page screenshot relative to the demo directory.

## Stable selectors

Prefer explicit Shiny input IDs and semantic attributes. Avoid `nth-child`, generated classes, and Bootstrap collapse IDs.

For a bslib accordion, use its stable `data-value`:

```css
#acc [data-value="reactivity"] .accordion-button
```

For selectize, inspect the rendered DOM and use values derived from the app’s own choices. Verify every selector through the complete action run.

## Timing

Estimate narration as:

```text
spoken words ÷ 2.5 + one second per pause tag + two-second buffer
```

Only Gemini performs other tags; the local voice strips them and turns pause tags into line breaks. Estimate action time from waits, typing duration, approximately one second per interaction (1.5 seconds per drag), and the code overlay’s typing, reading hold, and exit fade; a cue holds its action until the phrase. If actions are too short, add another proof or reversal. Do not pad with a long idle wait, and never pad the opening: keep the total wait before the first meaningful action at or under 1500 ms (the validator rejects over 2000 ms).

For a narrated deliverable, preserve natural speech speed and pauses. Adjust action timing and recording duration to the audio; never compress the audio or remove pauses. If a fixed duration cannot accommodate natural delivery, shorten the transcript and regenerate it before recording. Do not time actions against the word-count estimate, and do not hand-tune waits against silence gaps. Generate `artifacts/narration.wav`, measure its word timing (the batch narration phase does this; otherwise run `align_narration.py`, see the TTS reference), then anchor the storyboard with cues:

```yaml
actions:
  - wait_for: "#window"
  - wait: 500
  - cue: "switch to seven days"      # the click lands on these words
  - click: "#seven"
  - cue: "ninety days"
  - click: "#ninety"
  - cue: "one argument"               # the code card appears on this phrase
  - code: { ... }
```

Cue the phrase that names the visible change, not the start of a long sentence. Timing is a hard contract, and the validator enforces it from `recording.json`:

- Every cued reaction must land within 1.0 s before to 0.5 s after its phrase is spoken.
- A narrated video needs at least three cued meaningful actions and a cued code card.
- The first meaningful action must be visible before the first sentence ends. The pointer needs roughly a second from its resting place, so cue the first action to a word about 1.5–3 s into the narration rather than the first word.
- No visible action may land after the narration ends; after the last sentence, only hold the payoff.
- While narration plays, never leave the screen without a visible reaction for more than 8 seconds.
- Keep the video one to three seconds longer than the narration (the validator enforces 0.75–3.5 s after the narration's end, including its 0.15 s lead-in); place slack in the holds after reveals or the final wait — never at the start.

The validator prints one line per visible action with the sentence it lands in and its offset from its cue, and `--simulate-timing` projects the same check before recording. When you can, also watch the merged video with sound; the cue offsets prove timing, but only listening proves the delivery sounds natural.

The code hold defaults to `4800 + 70 × focus characters + 18 × context characters` milliseconds, clamped between 7500 and 16000 ms, so richer dimmed context earns a slightly longer read and the code stays on screen long enough to copy. Its typewriter animation runs before that hold, and its 0.3 s exit fade after it.

The validator requires `artifacts/narration.txt` to contain the complete `Audio profile:`, `Scene:`, `Director's notes:`, and `Transcript:` envelope, even for silent recordings.

## Outputs

- `artifacts/demo.webm` is the Playwright intermediate, written only with `--capture playwright`.
- `artifacts/demo.mp4` is the clean browser deliverable.
- `artifacts/recording.json` records the resolved orientation, dimensions, trimmed preamble, capture mode and frame rate, and an `action_timeline` of per-action start, end, and `reaction` timestamps relative to the trimmed video, plus each cued action's phrase and target; the validator compares that timeline against the narration's sentence windows and rejects a first meaningful action that starts after the first sentence ends.
- `artifacts/final.png` captures the ending state.
- `artifacts/validation.json` is the validator's full report; the console gets a summary.
- `artifacts/review.png` is the phone-size review sheet.
- Edited and narrated outputs use separate filenames and never replace `demo.mp4`.

## Review sheet

The gate asks whether the video reads on a phone, so review it at phone width. `review_frames.py` samples the first, reveal, code, and final frames — using `action_timeline` from `recording.json` to find the reveal and code beats, and `final.png` for the payoff — scales each to 390 logical px, and tiles them into one image:

```bash
python .agents/skills/shiny-component-shorts/scripts/review_frames.py \
  --project-dir generated/demo-name
```

It prints which tile is which and writes `artifacts/review.png` (780×1386 for a vertical demo). Inspect that one sheet rather than opening four 1440×2560 frames: it answers the same questions — legibility, cursor position, client-error panels, code card placement — at the size a viewer actually sees.

Use `--images a.png b.png` to tile specific frames instead, `--output` for another path, and `--width` to change the tile width.

## Troubleshooting

- The recorder waits three seconds after network idle for the Shiny WebSocket session.
- A missing selector fails the run; update the app or action file rather than weakening the selector.
- A **Shiny Client Errors** panel fails the run; repair the app instead of dismissing, hiding, cropping, or covering the panel.
- Playwright uses UUID video names; the recorder moves the current run’s video to the requested name after closing the context.
- Missing `ffmpeg` is a hard failure because MP4 is the deliverable.
- The recorder terminates only the Shiny process it started.
- Always rerun the validator after changing the app, action timing, narration, or orientation.

## Validation
 
```bash
python .agents/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir generated/demo-name
```

Use `--require-audio` for a narrated deliverable. Use `--simulate-timing` before recording to project action timings and test sentence window alignments without running Playwright. Treat any validation error as incomplete work.

The console output is a summary: action counts, video dimensions and duration, narration length, and one line per visible action naming the narration sentence it lands in — the comparison this contract's Timing section asks for, already resolved. `no sentence` means that action drifted outside the spoken track. The complete report, including the raw `action_timeline` and `narration_sentences` arrays, goes to `artifacts/validation.json`; `--json` prints it to the console instead.

### Prevent layout overflow before recording

Use the demo-local Python interpreter when the app depends on a pinned Shiny or shinychat build; the recorder launches the app with its own interpreter. Run both dry-run and recording with that interpreter. Inspect the phone preflight, not only selector success: size the entire interactive stage to the middle 60% of the viewport, including labels, chat inputs, and output cards. A fixed tall chat height can put inputs below the branding band even though every selector resolves. Use viewport-relative component heights, account for label height, and keep side gutters aligned near the logo's 4% inset. Check text readability and component bounds again after populated states and the code reveal.

The code card uses 20 logical px text in portrait and 18 px in landscape. Keep enough context to explain the change without hiding the highlighted line; inspect wrapping at phone size. `start_line` is the first line of the `before` block, or the highlighted text when no context precedes it. Review sheets prefer the first click, key press, selection, or drag after typing for the reveal tile; inspect additional frames if an asynchronous response arrives later.
