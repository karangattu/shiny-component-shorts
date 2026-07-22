# Recording contract

Read this reference when creating `actions.yaml`, recording a demo, or diagnosing recording failures.

## Shared recorder

Use the bundled recorder directly:

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir demo-name \
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

Author the app with an empty top 20% and bottom 20% for later branding. The app belongs in the middle 60% band and should span the available horizontal space between 3–5% side gutters.

The `code` action is orientation-aware. Vertical recordings anchor the panel to the bottom of the middle safe band (just above the reserved bottom 20%), growing upward as needed, so it sits below the component instead of covering it; compose the app toward the top of the band so the two never fight. Horizontal recordings switch to a side-by-side composition: the live app reflows on the left while the code panel occupies the right, so neither is hidden. The code panel uses the Shiny preset palette: `#007BC2` accent, `#1D1F21`/`#202020` dark surfaces, `#FFFFFF` primary text, and `#CDD4DA` secondary text.

The recorder refuses to start if its port is already occupied. Stop the known process yourself; never kill an unknown listener automatically.

For an existing app, create a sidecar production directory and keep the source separate:

```bash
python .agents/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir videos/interesting-filter \
  --app-dir /path/to/existing-app \
  --app-type r \
  --actions actions.yaml
```

The existing app remains unchanged. The recorder launches it from `--app-dir` while resolving `actions.yaml`, screenshots, narration, and all video artifacts under `--project-dir`.

Validate the sidecar against the same source directory:

```bash
python .agents/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir videos/interesting-filter \
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

Supported actions are `wait_for`, `wait`, `click`, `drag`, `select_option`, `hover`, `fill`, `type`, `press`, `code`, `zoom`, and `screenshot`. Each list item must contain exactly one action.

Storyboard beats such as `Reveal`, `Proof`, `Code`, and `Payoff` are planning metadata only. Do not add them to `actions.yaml` or render them over the recording.

## Action semantics

- `wait_for` waits for a selector to be attached, including content inside a collapsed component.
- `wait` uses milliseconds. Keep ordinary waits between 500 and 3000 ms.
- `click` visibly moves the injected cursor and shows a press pulse.
- `drag` moves from the center of `selector` by `delta_x` and `delta_y` pixels with an optional `steps` count. Use it for sliders, splitters, and other genuine drag interactions.
- `select_option` targets a native select value.
- `hover` moves the visible cursor without clicking.
- `fill` changes a field instantly; reserve it for clearing or realistic paste actions.
- `type` clicks, focuses, moves the caret to the end, and types sequentially. Use 35–70 ms per character.
- `press` sends one named key to the selector.
- `code` types a compact, syntax-highlighted Shiny-branded editor card, holds it by reading time, then removes it. Its `text` is the highlighted focus line; `before` and `after` blocks show dimmed real source context, and `start_line` keeps the gutter honest. Make that context an authentic slice of the app: include the code that surrounds the trick — for a UI feature, the enclosing UI component plus the related server logic (or the reverse when the server line is the star) — copied verbatim from the app source, typically 6–14 dimmed lines total, and highlight only the decisive line or two. Do not paste the whole app or invent tidied pseudo-source. Place any explanatory comment at the end of `before`, directly above the focus line — never in `after`, where a comment below the highlighted code reads as an afterthought and distracts from it. In vertical mode the card renders in the lower half of the frame, anchored above the bottom branding band; in horizontal mode it uses the side-by-side layout instead of overlaying the app.
- `zoom` is an optional camera punch-in: it scales the page toward the center of `selector` (`scale`, default 1.6), holds (`hold` ms, default 1800), then eases back out over about a second total of transitions. Use at most one per video, on the proof beat's changing region, and never while the code card is visible.
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
spoken words ÷ 2.5 + one second per audio tag + two-second buffer
```

Estimate action time from waits, typing duration, approximately one second per interaction, and the code overlay’s typing plus reading hold. If actions are too short, add another proof or reversal and distribute short waits after reactions. Do not pad with a long idle wait, and never pad the opening: keep the total wait before the first meaningful action at or under 1500 ms (the validator rejects over 2000 ms) so the first action is underway while the narration's opening words are spoken.

For a narrated deliverable, do not time actions against the word-count estimate. Generate `artifacts/narration.wav` first, then measure it:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 artifacts/narration.wav
ffmpeg -i artifacts/narration.wav -af "silencedetect=noise=-30dB:d=0.4" -f null -
```

Map each silence gap to a sentence boundary and set the waits so every visible reaction begins at or slightly before the sentence that describes it. Keep the video one to three seconds longer than the WAV, and place any slack needed to reach that length in the holds after reveals or before the code card — never at the start.

The code hold defaults to `3200 + 55 × focus characters + 14 × context characters` milliseconds, clamped between 5500 and 11000 ms, so richer dimmed context earns a slightly longer read. Its typewriter animation runs before that hold.

The validator requires `artifacts/narration.txt` to contain the complete `Audio profile:`, `Scene:`, `Director's notes:`, and `Transcript:` envelope, even for silent recordings.

## Outputs

- `artifacts/demo.webm` is the Playwright intermediate.
- `artifacts/demo.mp4` is the clean browser deliverable.
- `artifacts/recording.json` records the resolved orientation, dimensions, trimmed preamble, and an `action_timeline` of per-action start/end timestamps relative to the trimmed video; the validator compares that timeline against the narration's sentence windows and rejects a first meaningful action that starts after the first sentence ends.
- `artifacts/final.png` captures the ending state.
- Edited and narrated outputs use separate filenames and never replace `demo.mp4`.

## Troubleshooting

- The recorder waits three seconds after network idle for the Shiny WebSocket session.
- A missing selector fails the run; update the app or action file rather than weakening the selector.
- Playwright uses UUID video names; the recorder moves the current run’s video to the requested name after closing the context.
- Missing `ffmpeg` is a hard failure because MP4 is the deliverable.
- The recorder terminates only the Shiny process it started.
- Always rerun the validator after changing the app, action timing, narration, or orientation.

## Validation

```bash
python .agents/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir demo-name
```

Use `--require-audio` for a narrated deliverable. Treat any validation error as incomplete work.
