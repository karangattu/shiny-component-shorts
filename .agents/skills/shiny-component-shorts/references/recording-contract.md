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
- `--actions` is relative to the demo directory unless absolute.
- `--orientation vertical|horizontal` overrides `orientation:` in the YAML.
- Vertical is the default. Set horizontal only when the user explicitly requests it.
- The recorder preserves a 720×1280 or 1280×720 logical layout and launches Chromium in native 2× HiDPI mode, producing true 1440×2560 or 2560×1440 video without changing the composition.

Author the app with an empty top 20% and bottom 20% for later branding. The app belongs in the middle 60% band and should span the available horizontal space between 3–5% side gutters.

The `code` action is orientation-aware. Vertical recordings use a compact panel over the live app. Horizontal recordings switch to a side-by-side composition: the live app reflows on the left while the code panel occupies the right, so neither is hidden. The code panel uses the Shiny preset palette: `#007BC2` accent, `#1D1F21`/`#202020` dark surfaces, `#FFFFFF` primary text, and `#CDD4DA` secondary text.

The recorder refuses to start if its port is already occupied. Stop the known process yourself; never kill an unknown listener automatically.

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
      text: |
        ui.input_text_area("notes", autoresize=True)
  - screenshot:
      path: "artifacts/final.png"
```

Supported actions are `wait_for`, `wait`, `click`, `drag`, `select_option`, `hover`, `fill`, `type`, `press`, `code`, and `screenshot`. Each list item must contain exactly one action.

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
- `code` types a compact Shiny-branded editor card, holds it by reading time, then removes it. In horizontal mode it uses the side-by-side layout instead of overlaying the app.
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

Estimate action time from waits, typing duration, approximately one second per interaction, and the code overlay’s typing plus reading hold. If actions are too short, add another proof or reversal and distribute short waits after reactions. Do not pad with a long idle wait.

The code hold defaults to `3200 + 55 × characters` milliseconds, clamped between 5500 and 10000 ms. Its typewriter animation runs before that hold.

The validator requires `artifacts/narration.txt` to contain the complete `Audio profile:`, `Scene:`, `Director's notes:`, and `Transcript:` envelope, even for silent recordings.

## Outputs

- `artifacts/demo.webm` is the Playwright intermediate.
- `artifacts/demo.mp4` is the clean browser deliverable.
- `artifacts/recording.json` records the resolved orientation and dimensions for validation.
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
