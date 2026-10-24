# Recording contract

Read this reference when creating `actions.yaml`, recording a demo, or diagnosing recording failures.


## Editorial source media

New release/changelog/blog videos use `style: editorial` and the shot contract
in [changelog-reel.md](changelog-reel.md). `editorial.yaml` combines clean still
images and original-speed video clips with phrase cues and explicit framing
for both orientations. Source labels and static highlights identify evidence;
no fake editor chrome, simulated command results, or decorative animations.
Keep source captures and edited exports separate. Source text must be verbatim,
and test/performance results must come from saved actual runs.

The source media uses about 5% safe margins, with the top 12% and bottom 7%
clear for small metadata overlays. Preserve native app/document styling.
Capture any app behavior with the same stable selectors and client-error checks
as below. Never crop out an error panel. The component recorder's existing
three-action, code-action, activity-gap, and middle-band checks apply to its
component captures; editorial timeline validation replaces those quotas in the
assembled editorial segment. Narration and its measured timing still must pass.

For editorial media there is no `actions.yaml` unless a component recording is
one of its sources, and no `companion.py` step: each shot supplies both views.
The shared reel renderer validates all media/cues before rendering, and writes
review sheets showing every shot. Decode and inspect both final orientations.

## Standalone component capture

## Shared recorder

Use the bundled recorder directly:

```bash
python .claude/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/demo-name \
  --app-type python \
  --actions actions.yaml
```

Options:

- `--app-type python|r` selects the Shiny server runtime, including shinyreact apps. Build any JSX/TSX frontend before starting the recorder; there is no separate React runtime flag.
- `--app-dir` optionally selects a separate source directory containing `app.py` or `app.R`; it defaults to `--project-dir`.
- `--actions` is relative to the demo directory unless absolute.
- `--orientation vertical|horizontal` overrides `orientation:` in the YAML.
- Vertical is the default. Set horizontal only when the user explicitly requests it.
- The recorder preserves a 720×1280 or 1280×720 logical layout and launches Chromium in native 2× HiDPI mode, producing true 1440×2560 or 2560×1440 video without changing the composition.
- `--capture screencast` (the default) records Chromium's own compositor frames at full resolution, stamped on the same clock as the actions, and encodes constant 30 fps H.264. The action timeline and the video therefore agree exactly. `--capture playwright` falls back to Playwright's 25 fps WebM recorder, whose start is only approximately aligned; use it only if screencast capture fails on a machine.

Author the app with an empty top 20% and bottom 20% for later branding. The app belongs in the middle 60% band and should span the available horizontal space between 3–5% side gutters.

The `code` action shows a complete syntax-highlighted source excerpt with its real filename and line numbers. Portrait cuts to full-frame code with about 5% margins; landscape uses a side-by-side layout with the live app. Code uses GitHub dark syntax colors on `#0D1117`, Source Code Pro, Open Sans labels, and Shiny blue `#007BC2` highlights. App light-mode text remains `#1D1F21`, and dark labels use `#FFFFFF`. No fabricated editor UI. See [visual style](visual-style.md).

The recorder refuses to start if its port is already occupied. Stop the known process yourself; never kill an unknown listener automatically.

## Paparazzi capture for R Shiny

For R Shiny videos, set `capture: paparazzi` at the top of `actions.yaml`, or pass
`--capture paparazzi --app-type r`. Keep the same actions, narration, and cue phrases.
The companion inherits the YAML setting automatically. An explicit `--capture`
overrides YAML; projects without either continue to use `screencast`.

Install [paparazzi](https://posit-dev.github.io/paparazzi/) and `av` in a dedicated
R library. Set `R_LIBS_USER` to that library for preflight, recording, and batch
commands. Paparazzi is an optional development package; pin its Git commit in
production environments. This integration was exercised with commit `3e595ed`.

```bash
mkdir -p generated/.r-library
export R_LIBS_USER="$PWD/generated/.r-library"
Rscript -e 'pak::pkg_install(c("posit-dev/paparazzi@3e595ed", "av"), lib=Sys.getenv("R_LIBS_USER"), ask=FALSE)'
```

If `pak` reports missing build tools after installing the dependencies, install the
pure-R package directly from its pinned source archive:

```bash
curl -fL https://api.github.com/repos/posit-dev/paparazzi/tarball/3e595ed -o generated/paparazzi-3e595ed.tar.gz
R CMD INSTALL --library="$R_LIBS_USER" generated/paparazzi-3e595ed.tar.gz
```

Paparazzi owns Chromium and captures full-density frames with `pz_record_start()`
in poll mode at a requested 30 fps. The existing Python action runner shares that
browser over CDP, so cursor motion, narration cues, code cards, branding, and client
error checks retain their existing behavior. This backend supports the shared
`actions.yaml` contract, rather than translating it into a second R action language.

The bridge writes a `shorts-clock` marker to Paparazzi's public WebVTT sidecar.
The final encode removes the lead before that marker and maps the action clock to
the exported video. It rejects a clock handshake with more than 50 ms of uncertainty.
Do not add Paparazzi pauses or frame holds to the bridge: they splice the video clock
and invalidate that mapping. Use the shared `wait` and `cue` actions instead.
The shared validator still checks every cue against the measured spoken words.
Paparazzi exports a silent recording; `merge_audio.py` adds the local narration.

`artifacts/paparazzi-raw.mp4`, `paparazzi-raw.vtt`, and `paparazzi.log` retain the
capture evidence. `demo.mp4`, `recording.json`, and the finished narrated files keep
the same names and structure as other backends. Preflight checks the R dependencies
and runtime, then uses the shared browser checks for selectors and layout.

Run the real R/browser regression test when this backend or its dependencies change:

```bash
SHORTS_TEST_PAPARAZZI=1 .venv/bin/python -m unittest discover -s tests -p test_paparazzi_contract.py -v
```

It decodes pixels from the MP4 to check that three cued reactive changes appear at
the expected video times. Environments without R can run the remaining contract tests.

## Preflight

`--dry-run` runs everything the recorder does before the first action and nothing after it: it loads `actions.yaml`, rejects malformed actions and code cards, starts the app, waits for the Shiny session, scans for a **Shiny Client Errors** panel, resolves every selector on the loaded page, and screenshots the composition.

```bash
python .claude/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/demo-name \
  --app-type python \
  --actions actions.yaml \
  --dry-run
```

It also resolves every `cue` against the current narration's word timing and prints each cue's video time, so a misquoted phrase or stale timing fails here instead of mid-take. It records no video, writes no `demo.mp4`, `recording.json`, or `final.png`, and exits non-zero when anything is wrong. It writes three artifacts instead:

- `artifacts/preflight.png` — the composition at recording viewport, for checking gutters, the empty top and bottom bands, and control padding.
- `artifacts/preflight-phone.png` — the same frame at phone width; read this one.
- `artifacts/preflight-app.log` — the app's server output, reported only when the preflight fails.

Run it before every full take, and after every app or selector change. A take that dies on a missing selector costs a browser run, an encode, a validation, and a frame review; the preflight costs one page load.

## Brand logo

Every recording carries the Shiny wordmark in the top-left of the reserved top 20% band. The recorder injects it as a fixed overlay before the app loads: 144 logical px wide in vertical recordings (20% of the 720 px logical frame), 180 px in horizontal ones, inset 4% from the top and left edges, sized to stay legible on a phone screen. The artwork renders as it ships, untinted; because its ink is black, the only treatment is a flip to white on backdrops whose relative luminance falls under 0.5 — dark surfaces, and the `#007BC2` primary — so it never disappears into the app. The logo stays visible for the first 5 seconds of the video, then fades out over 0.4 s so the app has the frame to itself. Set `logo_seconds:` at the top level of `actions.yaml` to change that time; `logo_seconds: 0` records without the logo, and a page reload or navigation during the recording keeps the logo hidden once its time has passed; which changelog reel segments use because the reel's intro card carries it. While the logo shows, preflight and recording fail if content overlaps it or the logo leaves the top branding band; fix the layout rather than hiding the wordmark. Inspect its size and contrast in the phone-size review sheet.

Keep that corner clear: the top band is already reserved, so no app UI, no in-app logo of your own, and no code card competes with it. `artifacts/recording.json` records the stamped logo under `logo` (with `visible_seconds`), and the validator rejects a recording whose `recording.json` has no `logo` entry — that means the video predates the brand overlay and must be re-recorded. Pass `--logo path/to/file.png` only when a demo needs a different mark; the default asset lives at `.claude/skills/shiny-component-shorts/assets/shiny-logo.png`.

## Client-error safety contract

No example may be recorded or delivered with a **Shiny Client Errors** panel visible. Assign unique output IDs across the complete rendered page, including conditional UI, modules, and repeated components. Exercise the full action sequence before accepting the app because some duplicate outputs appear only after reactive UI is inserted.

The shared recorder checks for the panel after startup and after the action run. Detection is a blocking failure: fix the duplicate output IDs or other client error, restart the app, and record again from the beginning. Never click **Dismiss all**, hide the panel with CSS, crop it out, or cover it with the code card. During final review, inspect the first, reveal, code, and final frames and reject the video if the panel appears in any frame.

For an existing app, create a sidecar production directory and keep the source separate:

```bash
python .claude/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/interesting-filter \
  --app-dir /path/to/existing-app \
  --app-type r \
  --actions actions.yaml
```

The existing app remains unchanged. The recorder launches it from `--app-dir` while resolving `actions.yaml`, screenshots, narration, and all video artifacts under `--project-dir`.

Validate the sidecar against the same source directory:

```bash
python .claude/skills/shiny-component-shorts/scripts/validate_demo.py \
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

Supported actions are `wait_for`, `wait`, `cue`, `click`, `drag`, `select_option`, `hover`, `fill`, `type`, `press`, `code`, `wait_stream`, and `screenshot`. Each list item must contain exactly one action. The recorder also accepts the legacy overlay actions `caption`, `beat`, and `label`, but the skill does not use them for clean videos.

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
- `code` shows a static source excerpt immediately and cuts back to the app after its hold. `text` identifies the highlighted line or small block; `before` and `after` provide relevant source context. `start_line` is the actual source line. Prefer 4–7 relevant lines, copied verbatim with relative indentation intact; only one common dedent is allowed. Portrait uses the full frame; landscape keeps the app beside the excerpt. No simulated editor title bars, breadcrumbs, status bars, cursor, typing, or slides. Keep GitHub highlighting and the real filename. Use `duration` in milliseconds to cover the complete explanation plus a quiet reading pause. For a second function, use another cued code action followed by the real interaction it explains. Never shorten speech to fit the code hold.
- `screenshot` writes a full-page screenshot relative to the demo directory.
- `wait_stream` spans an asynchronous reaction. It waits until the region inside its `selector` stops changing for `quiet_ms` (1500 ms by default), giving up after `timeout` (30000 ms by default). Its entry ends when the region goes quiet, so a streamed answer covers the dead air it actually filled on screen instead of one click standing in for the whole stream. Cue the click that starts the stream, never `wait_stream` itself, and do not count it toward the three meaningful actions. `expect_ms` (5000 ms by default) is only the projected span `--simulate-timing` uses before the stream exists. Accepts a bare selector or `{selector, quiet_ms, timeout, expect_ms}`.
- Legacy `caption`, `beat`, and `label` actions inject visible overlays and require an `overlays` block. Do not use them in skill-generated recordings. In particular, storyboard beat names such as `Reveal` and `Proof` are planning metadata, not action entries.

## Clean recordings

Omit the top-level `overlays` block. It injects visible hook, caption, state-chip, and beat-rail UI into the browser recording. The clean deliverable should show the app interactions and the concise `code` card only. Keep the hook, captions, and beat names in the narration, storyboard, or later editing plan rather than `actions.yaml`. The validator may warn about missing overlays; for this workflow that warning is expected and is not a quality failure.

## Reliability

- Before running any action, the recorder checks that every selector referenced by `click`, `hover`, `drag`, `select_option`, `fill`, `type`, and `press` resolves on the loaded page, and fails fast listing all missing selectors. A selector targeted by a `wait_for` action is exempt — use `wait_for` to declare elements that appear asynchronously.
- App startup is retried up to three times with backoff before the run is abandoned.

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

Only Gemini performs other tags; the local voice strips them and turns pause tags into line breaks, except `[pause Ns]`, which the local voice renders as exactly N seconds of silence (count N seconds, not one, in the estimate). Estimate action time from waits, typing duration, approximately one second per interaction (1.5 seconds per drag), and the static source excerpt’s reading hold; a cue holds its action until the phrase. If actions are too short, add another proof or reversal. Do not pad with a long idle wait, and never pad the opening: keep the total wait before the first meaningful action at or under 1500 ms (the validator rejects over 2000 ms).

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

Cue the phrase that names the visible change, not the start of a long sentence. While choosing one, `scripts/narration_map.py --project-dir <demo> --phrase '...'` prints every sentence's narration and video time and resolves any phrase against the measured take. Timing is a hard contract, and the validator enforces it from `recording.json`:

- Every cued reaction must land within 1.0 s before to 0.5 s after its phrase is spoken.
- A narrated video needs at least three cued meaningful actions and a cued code card.
- The first meaningful action must be visible before the first sentence ends. The pointer needs roughly a second from its resting place, so cue the first action to a word about 1.5–3 s into the narration rather than the first word.
- No visible action may land after the narration ends; after the last sentence, only hold the payoff.
- While narration plays, never leave the screen without a visible reaction for more than 8 seconds.
- Keep the video one to three seconds longer than the narration (the validator enforces 0.75–3.5 s after the narration's end, including its 0.15 s lead-in); place slack in the holds after reveals or the final wait — never at the start.

The validator prints one line per visible action with the sentence it lands in and its offset from its cue, and `--simulate-timing` projects the same check before recording. When you can, also watch the merged video with sound; the cue offsets prove timing, but only listening proves the delivery sounds natural.

The legacy fallback code hold remains `4800 + 70 × focus characters + 18 × context characters` milliseconds, bounded to 7500–16000 ms. New videos must set an explicit `duration` from measured narration: allow the whole explanation and a quiet reading pause. A static excerpt has no added typing or exit-animation time. Older `type_ms` fields are ignored. Longer explanations can use holds beyond the fallback range.

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
python .claude/skills/shiny-component-shorts/scripts/review_frames.py \
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
python .claude/skills/shiny-component-shorts/scripts/validate_demo.py \
  --project-dir generated/demo-name
```

Use `--require-audio` for a narrated deliverable. Use `--simulate-timing` before recording to project action timings and test sentence window alignments without running Playwright. Treat any validation error as incomplete work.

The console output is a summary: action counts, video dimensions and duration, narration length, and one line per visible action naming the narration sentence it lands in — the comparison this contract's Timing section asks for, already resolved. `no sentence` means that action drifted outside the spoken track. The complete report, including the raw `action_timeline` and `narration_sentences` arrays, goes to `artifacts/validation.json`; `--json` prints it to the console instead.

### Prevent layout overflow before recording

Use the demo-local Python interpreter when the app depends on a pinned Shiny or shinychat build; the recorder launches the app with its own interpreter. Run both dry-run and recording with that interpreter. Inspect the phone preflight, not only selector success: size the entire interactive stage to the middle 60% of the viewport, including labels, chat inputs, and output cards. A fixed tall chat height can put inputs below the branding band even though every selector resolves. Use viewport-relative component heights, account for label height, and keep side gutters aligned near the logo's 4% inset. Check text readability and component bounds again after populated states and the code reveal.

Static source uses 25 logical px text in portrait and 20 px in landscape. Prefer short excerpts and intentional line breaks in the actual source; inspect phone-size wrapping. `start_line` is the first line of `before`, or the highlighted text when no context precedes it. Inspect every code excerpt, not just the first one.

## Frontend code cards (shinyreact)

A code action can set `source_file` to an app-relative source path. The validator reads it relative to `--app-dir` (or `--project-dir` when omitted), requires it to stay inside that directory, and checks the card against that file alone. Without this field, validation still uses `app.py` or `app.R`. `title` is only a display label. Set one source file per card; never combine Python and JavaScript lines into one card.

```yaml
- code:
    source_file: www/ui.js
    title: ui.js
    text: |
      const count = useShinyOutputValue("count", 0);
```

Copy the actual line and surrounding `before`/`after` context from the app. JS/JSX and TS/TSX filenames select JavaScript or TypeScript highlighting automatically; a `language` override is optional. Standalone `//` commentary is allowed, while executable lines must match the selected source. Frontend source, CSS, lockfiles, and built assets participate in recording cache checks; `node_modules` does not.
