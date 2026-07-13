---
name: shiny-component-shorts
description: Create interactive Shiny Python or R mini-apps, 30-second "Did you know?" video concepts, Gemini 3.1 TTS narration and audio, storyboards, recording automation, and editing notes. Use when the user provides a Shiny component name or docs URL, or asks for a short demo or video around a Shiny UI feature.
---

# Shiny Component Micro-App Video Factory

## Mission

Create tiny Shiny mini-apps and 30-second video concepts for individual Shiny components.

The goal is not to explain the whole component. The goal is to find the one surprising behavior, hidden option, or overlooked interaction that makes the component worth showing in a short video.

Each output should feel like:

> "Wait, that component can do that?"

## Inputs to accept

The user may provide:

* A Shiny component name
* A Shiny component docs URL
* A language: Python, R, or both
* A target audience
* A desired number of video ideas
* Whether they want storyboard only, code only, narration only, or everything

If the user gives no language, default to Python Shiny Express for short demos unless the component is only available or clearer in R.

## Core rule

One video = one trick.

Do not create a full tutorial. Do not list every parameter. Pick one visual behavior that can be demonstrated in under 30 seconds.

## Interaction and motion budget

Make the component do something visible throughout the recording. One trick does not mean one click.

Use this interaction arc:

1. Show the starting state for no more than 2 seconds.
2. Trigger the hidden behavior immediately.
3. Change the input or state again to prove the result is reactive rather than a one-off animation.
4. Add one contrast, reversal, or reset that makes the behavior unmistakable.
5. End on the strongest result, not an idle screen.

Require at least three meaningful user actions and three clearly visible state changes in a 30-second recording. A meaningful action changes content, selection, layout, focus, validation, or server state; moving the pointer or clicking an inert element does not count.

Avoid static shots longer than 3 seconds. If narration needs more time, continue interacting with the same feature, compare two states, or replay the reveal. Size code overlays by reading time (the recorder computes the hold from the character count) and show them over the live app when possible; the typewriter animation counts as motion.

Choose interactions native to the component: select, type, sort, filter, expand, drag, hover, dismiss, update, validate, or reset. Do not bolt on unrelated buttons or decorative motion just to satisfy the budget.

## Short-form retention layer

When creating a recorded or edited short, read [references/short-form-pacing.md](references/short-form-pacing.md) and apply its hook, caption, state-label, progress-rail, vertical-layout, and editing guidance.

Keep the Shiny app as the hero. Use the reference patterns as a visual grammar, not as permission to copy another creator's wording, branding, footage, or exact design.

Good tricks include:

* A component that looks decorative but behaves reactively
* A compact UI feature that replaces a messier layout
* A component that stores user state
* A component that prevents a common app bug
* A component that can be updated from the server
* A tiny parameter that changes the whole user experience
* A small UI placement trick that makes an app feel cleaner
* A hidden reactive behavior that is easy to miss in the docs

## Research process

For each component:

1. Inspect the official Shiny docs URL if provided.
2. Identify:

   * The function name
   * The basic purpose
   * The most visual variation
   * Any update function
   * Any reactive value exposed to the server
   * Any surprising layout behavior
   * Any useful accessibility or UX detail
3. Ignore anything that cannot be shown clearly on screen.
4. Choose the strongest "I didn't know Shiny could do that" feature.
5. Build a tiny app around that feature.

## Output format

For every component, produce the following sections.

## Component

Name and language.

Example:

```text
Toolbar Select — Python Shiny Express
```

## Best video angle

One sentence describing the hidden feature.

Example:

```text
A select input can live inside a card header toolbar, so the card controls itself instead of relying on a separate sidebar.
```

## Hook

A short opening line for the video.

Lead with the viewer's precise frustration or desired result, then reveal the component. Avoid opening with the component name when a problem-led hook is available.

Example:

```text
Did you know your Shiny filter does not have to live in the sidebar?
```

## Mini-app concept

A tiny app idea that makes the feature obvious.

Keep it small. The app should be understandable from one screen recording.

Example:

```text
A sales dashboard card with a toolbar dropdown in the header. Changing the dropdown switches the card body between revenue, orders, and customers.
```

## Variations

Provide 3 to 5 variations.

| Variation       | What changes                           | Why it is video-worthy                   |
| --------------- | -------------------------------------- | ---------------------------------------- |
| Minimal         | The smallest possible version          | Shows the trick clearly                  |
| Dashboard       | More realistic app layout              | Shows where people would use it          |
| Weird demo      | Funny or memorable example             | Makes the behavior stick                 |
| Server-reactive | Server logic responds to the component | Shows it is not just decorative          |
| UX polish       | Cleaner placement or labels            | Shows why the component improves the app |

## 30-second storyboard

Use this structure:

|      Time | Visual                          | Narration                       |
| --------: | ------------------------------- | ------------------------------- |
|   0-3 sec | Show the initial state, then start the first action | Short pain-point line |
|   3-8 sec | Complete the first reveal | "Did you know..." line |
|  8-14 sec | Trigger a second state | Describe the visible response |
| 14-20 sec | Reverse, reset, or contrast it | Prove the behavior is reactive |
| 20-26 sec | Overlay the key code on the live result (typewriter + reading-time hold) | Explain only the important line |
| 26-30 sec | Perform the strongest final interaction and end on its result | Concrete takeaway (an aphorism is allowed, not required) |

The storyboard should be visual and recordable. Avoid abstract explanation.

## Interaction plan

After the storyboard, list the exact action → reaction beats. Include at least three rows.

| Beat | User action | Visible reaction | Why it earns screen time |
| ---: | --- | --- | --- |
| 1 | [Exact action] | [Specific UI change] | [What this proves] |

Reject the concept and choose another angle if the table cannot contain three meaningful beats without adding unrelated controls.

## Narration Script

Create one narration script only: a Gemini TTS-ready script for the 30-second video.

The narration must match the storyboard timing. It should sound like a short vertical video, not a lecture, podcast, or tutorial.

## Gemini TTS narration rules

Use light inline audio tags to guide delivery.

Preferred tags for this series:

* `[curious]`
* `[amazed]`
* `[serious]`
* `[whispers]`
* `[laughs]`
* `[very fast]`
* `[very slow]`

You may use other natural tags when they clearly improve the performance, but do not rely on obscure tags. Audio tags are performance hints, not guaranteed controls.

Rules:

* Keep the transcript around 60 to 85 spoken words.
* Use 3 to 6 audio tags total.
* Do not tag every sentence.
* Keep the pacing brisk.
* The first line should hook the viewer in under 3 seconds.
* Match the video structure:

  * 0-3 sec: surprising hook
  * 3-8 sec: reveal the hidden component behavior
  * 8-20 sec: describe what the viewer is seeing
  * 20-27 sec: call out the key code line
  * 27-30 sec: memorable takeaway
* Use punctuation or a short blank line before reveals instead of overusing pause tags.
* Use `[very fast]` only for setup that should feel compressed.
* Use `[very slow]` only for the final takeaway or code reveal.
* Avoid theatrical tags unless the video concept is intentionally funny.
* Do not write visual stage directions inside the transcript.
* Do not include timestamps inside the transcript.
* Do not make the narration explain every parameter.
* The narration should be tightly connected to what appears on screen.

## Required Gemini TTS format

```text
Synthesize this as a natural, curious tech explainer for a 30-second vertical video.

Audio profile:
A clear developer voice. Brisk, precise, lightly amused, and not salesy.

Scene:
A short screen-recorded demo of a Shiny component. The viewer is seeing the UI change live.

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[Gemini-tagged narration here]
```

## Gemini TTS example

```text
Synthesize this as a natural, curious tech explainer for a 30-second vertical video.

Audio profile:
A clear developer voice. Brisk, precise, lightly amused, and not salesy.

Scene:
A short screen-recorded demo of a Shiny card with a dropdown in the card header.

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[curious] Why is this card's filter all the way over in a sidebar?

Watch — I'll pick a new view from the card's own header, and the whole body switches.

Orders. Customers. Back to revenue. [amazed] The card runs itself.

One line does this: ui.toolbar_input_select, dropped inside the card header.

[very slow] That's it. The filter just lives on the card now.
```

Note how this example ends plain rather than on a punchline, keeps contractions, and names what is literally on screen. Vary your own endings and rhythm from video to video — reusing this example's cadence verbatim recreates the pattern it exists to avoid.

After generating the narration, continue with the Code section.

## Code

Generate a runnable Shiny mini-app.

For Python:

* Prefer Shiny Express for short demos.
* Use Shiny Core only when the layout needs clearer structure.
* Keep dependencies minimal.
* Prefer built-in datasets or tiny inline data.
* Avoid complicated setup.
* The app should be small enough to understand from one screen.

For R:

* Use `shiny` and `bslib`.
* Add packages only when needed.
* Prefer built-in datasets or tiny inline data.
* Keep the app small enough to understand from one screen.

The code should directly support the video idea. Do not add unrelated features.

## Recording notes

Include:

* What to click
* What changes on screen
* Where to zoom
* Which line of code to highlight
* What the final visual should look like

Example:

```text
Recording notes:
- Start with the card visible and the dropdown closed.
- Click the dropdown and switch from Revenue to Orders.
- Zoom into the card header to show that the control lives inside the card.
- Highlight `ui.toolbar_input_select()`.
- End with the card showing the updated value.
```

## Style rules

Use a recurring "Did you know?" framing, but avoid generic titles.

Bad:

* "Did you know Shiny has tooltips?"
* "Introduction to Shiny data grids"
* "How to use action buttons"

Good:

* "Did you know a tooltip can trigger server logic?"
* "Did you know a table can become an input?"
* "Did you know a notification can update itself instead of stacking?"
* "Did you know a card can carry its own filter?"
* "Did you know a button can protect your app from impatient clicking?"

## Writing style

Write like a sharp, curious developer explaining a small trick to another developer.

Use:

* Plain English
* Short sentences
* Specific visual examples
* One memorable line
* A tiny bit of humor when it fits

Avoid:

* Textbook phrasing
* Generic summaries
* Long parameter tours
* Fake excitement
* Explaining every caveat
* Turning the video into documentation

## Make it feel human, not generated

Viewers pattern-match AI narration and robotic demos fast. Run this pass on every script and action script before recording.

Narration realness rules:

* Do the read-aloud test: if a sentence sounds like documentation or a keynote, rewrite it as something you would say to a coworker at their desk.
* Use contractions everywhere they fit. "It doesn't" not "it does not".
* Ban stock AI vocabulary: game-changer, seamless, powerful, unlock, elevate, dive in, let's explore, effortlessly, supercharge.
* Avoid the negative-parallelism template ("It's not just X, it's Y") and rule-of-three lists; both are strong LLM tells.
* At most one metaphor or aphorism per script — and not necessarily at the end. Ending every video on a tidy punchline is itself a pattern; sometimes end on a plain, concrete observation ("that's the whole change").
* Vary sentence rhythm within and across scripts. Mix a three-word sentence with a longer one. Do not reuse the previous video's cadence.
* Reference only what is literally on screen, with the real numbers shown ("nine lines", "three toasts"), not rounded idealizations.
* Allow one small conversational imperfection — a "honestly", "okay, watch", or mid-sentence correction — where it fits naturally. One, not three.

Demo realness rules:

* Type on camera at human speed with the `type` action; never paste whole paragraphs with `fill` unless pasting is the realistic gesture.
* Use content a person would actually have: real-sounding notes, names, uneven numbers (141, not 100). Never "Item 1 / Item 2", "line1", lorem ipsum, or "foo".
* Vary wait durations (900, 1400, 2100 ms) instead of uniform round numbers; humans do not act on a metronome.
* Let one beat breathe slightly longer after the biggest reveal, the way a person pauses when something works.

## Quality checks

Before finalizing, verify:

1. The idea is visually understandable in 30 seconds.
2. It is specific to this component.
3. There is one code line worth zooming into.
4. It reveals behavior, not just appearance.
5. The mini-app is runnable.
6. The narration matches the storyboard.
7. The Gemini TTS transcript is around 60 to 85 spoken words.
8. A Shiny user would say, "Oh, I could use that."
9. The interaction plan contains at least three meaningful action → visible reaction beats.
10. No planned idle shot lasts longer than 3–4 seconds. Code overlays may run longer because the typewriter animation provides motion, but keep computed typing + hold under ~9 seconds.
11. The video is composed and verified in its chosen orientation (9:16 vertical by default, or 16:9 when horizontal is requested), not cropped from a mismatched layout as an afterthought.
12. The hook names a viewer problem or outcome rather than merely announcing the component.
13. The edit has a visible change every 1.5–3 seconds without decorative noise.
14. If recording is requested, the app has stable selectors.
15. If recording is requested, the action script matches the storyboard.
16. If recording is requested, the recorder starts and stops the Shiny server cleanly.
17. If recording is requested, the action script's total duration is at least as long as the estimated narration duration.
18. If TTS is requested and an API key is available, `artifacts/narration.wav` exists.
19. If recording is requested, the final delivered file is `artifacts/demo.mp4`, not `.webm`.
20. Do not claim a video or narration was generated unless its output file exists.
21. End every completed generation workflow with a cost report for Gemini and the active agent harness.
22. The narration passes the "Make it feel human, not generated" rules: it survives the read-aloud test, contains no stock AI vocabulary, avoids negative-parallelism and rule-of-three templates, and has at most one aphorism (not required to be the ending).
23. Any text the viewer watches being written uses the `type` action at human speed, waits are varied rather than uniform round numbers, and demo content looks like something a real person would have on screen.
24. The code overlay uses the animated editor card with a reading-time hold computed from character count (or a narration-justified override), and the snippet matches the app code verbatim.

## Avoid

* Full component tutorials
* Long parameter tours
* Apps that require too much data setup
* Purely cosmetic changes unless the visual result is dramatic
* Multiple tricks in one video
* Abstract reactivity explanations without visible interaction
* A single click followed by long waits
* Cursor movement presented as interaction
* Seven-second full-screen code cards
* Long explanations before showing the demo
* Narration that sounds like API documentation
* Narration that does not match what appears on screen

## Final response template

Use this structure when generating an idea.

````markdown
# Component: [Component name]

## Best Video Angle

[One-sentence hidden feature]

## Hook

[Opening spoken line]

## Mini-App Concept

[Short description]

## Variations

| Variation | What changes | Why it is video-worthy |
|---|---|---|
| [Variation] | [Change] | [Reason] |

## 30-Second Storyboard

| Time | Visual | Narration |
|---:|---|---|
| 0-3 sec | [Initial state and first action] | [Narration] |
| 3-8 sec | [First reveal] | [Narration] |
| 8-14 sec | [Second state] | [Narration] |
| 14-20 sec | [Reverse, reset, or contrast] | [Narration] |
| 20-26 sec | [Code overlay on live app, typewriter + reading-time hold] | [Narration] |
| 26-30 sec | [Strongest final interaction and result] | [Narration] |

## Interaction Plan

| Beat | User action | Visible reaction | Why it earns screen time |
|---:|---|---|---|
| 1 | [Action] | [Reaction] | [Reason] |
| 2 | [Action] | [Reaction] | [Reason] |
| 3 | [Action] | [Reaction] | [Reason] |

## Gemini TTS Narration

```text
Synthesize this as a natural, curious tech explainer for a 30-second vertical video.

Audio profile:
A clear developer voice. Brisk, precise, lightly amused, and not salesy.

Scene:
[Describe the screen-recorded Shiny demo in one sentence.]

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[Gemini-tagged narration]
````

## Code

```python
# Runnable Shiny app here
```

## Recording Notes

* Click:
* Watch for:
* Zoom into:
* Highlight this code line:
* End on:

## Browser Recording Automation

When the user asks to record the demo, generate a runnable browser recording workflow in addition to the Shiny app.

The workflow should:

1. Write the Shiny app to disk.
2. Start the app on a fixed local port.
3. Wait until the app is reachable.
4. Open the app in a browser using Playwright.
5. Perform the exact UI actions from the storyboard.
6. Record the browser video.
7. Save the video to an `artifacts/` directory.
8. Stop the Shiny server cleanly.
9. If silent editing is requested, run a separate FFmpeg edit step after recording.

## Recording output files

When recording is requested, create this structure:

```text
demo-name/
├── app.py                  # Python Shiny app, if Python
├── app.R                   # R Shiny app, if R
├── actions.yaml            # Browser action script
├── edit.yaml               # Timed edit overlays, if editing requested
├── scripts/
│   ├── record_demo.py      # Playwright recorder
│   ├── edit_video.py       # FFmpeg silent editor, if editing requested
│   └── generate_tts.py     # Gemini narration generator, if audio requested
└── artifacts/
    ├── demo.webm           # Raw Playwright recording (intermediate)
    ├── demo.mp4            # Clean browser recording
    ├── final.mp4           # Edited silent video, if editing requested
    ├── narration.txt       # Gemini prompt, if audio requested
    ├── narration.wav       # Gemini TTS audio, if audio requested
    ├── narration.usage.json # Gemini tokens and cost estimate
    └── cost-report.md      # End-of-run cost ledger
```

The `.webm` file is an intermediate artifact only. If editing is not requested, the final deliverable is `demo.mp4`. If editing is requested, keep `demo.mp4` as the clean input and deliver `final.mp4`.

## Stable selector rule

The app must include stable selectors for recording.

Prefer:

* Explicit input IDs
* Buttons with predictable labels
* `data-testid` attributes when useful
* Simple DOM structure

Avoid selectors based only on visual position, generated classes, or fragile nested markup.

Good:

```python
ui.input_select("view", "View", choices=["Revenue", "Orders", "Customers"])
```

Good Playwright selector:

```text
#view
```

Bad:

```text
div:nth-child(3) > button:nth-child(2)
```

## Stable selectors for bslib components

bslib components (accordion, navset tabs, etc.) generate **random internal IDs** for Bootstrap collapse targets (e.g. `bslib_accordion_panel_cef967`). Never use those IDs in selectors.

For `ui.accordion(id="acc")`, each panel is rendered as `.accordion-item[data-value="..."]`. The `data-value` maps directly to the `value=` argument in Python.

Click a panel header with:

```css
#acc [data-value="reactivity"] .accordion-button
```

Full DOM structure for reference:

```html
<div id="acc" class="accordion">
  <div class="accordion-item" data-value="reactivity">
    <span class="accordion-header">
      <button class="accordion-button collapsed">Reactivity</button>
    </span>
    <div id="bslib_accordion_panel_RANDOM" class="accordion-collapse collapse">
      ...
    </div>
  </div>
</div>
```

## Action script format

Generate an `actions.yaml` file that mirrors the 30-second storyboard.

Supported actions:

```yaml
url: "http://127.0.0.1:8000"
video_name: "demo.webm"

actions:
  - wait_for: "#view"

  - wait: 1000

  - click: "#view"

  - select_option:
      selector: "#view"
      value: "orders"

  - hover: ".card"

  - fill:
      selector: "#search"
      value: "penguin"

  - type:
      selector: "#notes"
      value: "Reads like a person wrote it"
      delay: 45

  - press:
      selector: "body"
      key: "Escape"

  - code:
      title: "app.py"
      text: |
        ui.toolbar_input_select()
        input.view()

  - screenshot:
      path: "artifacts/final.png"
```

Rules:

* Every action should connect to the storyboard.
* Keep the total action sequence close to 30 seconds.
* The recorded video must be long enough to cover the full narration script — see "Video duration must match the narration" below.
* Include at least three meaningful actions that produce at least three visible state changes.
* Keep ordinary waits between 500 and 2500 ms. Never pad the recording with one long idle wait.
* When more duration is needed, replay, reverse, or contrast the same feature with additional meaningful actions.
* Add short waits after visible state changes so viewers can register the result.
* Do not over-click or count opening a control as a meaningful action unless it reveals the component behavior.
* Use selectors that exist in the generated app.
* For recorder-only output, include one `code` action around the 20-27 second storyboard slot.
* For edited output, keep the recording clean and put hook, code, and takeaway overlays in `edit.yaml`.
* If the component needs a hover, use `hover`.
* If the component needs a select input, use `select_option`.
* If the component needs typing the viewer watches, use `type`; use `fill` only for paste-like bulk input or clearing.
* If the component needs a button, use `click`.
* For `code`, inline the exact snippet in `text`; `title` defaults to `app.py`. Omit `duration` so the recorder computes the hold from reading time (~55 ms per character + 1.2 s, clamped 3.5–8 s); only set it when narration timing demands.
* Use `type` (not `fill`) for any text a human would visibly write on camera — it types character by character with a per-key delay. Reserve `fill` for paste-like bulk text and for clearing a field with an empty value.

## Video duration must match the narration

The recorded browser video must be at least as long as the narration script takes to speak. If the video is shorter, the final audio+video mix gets cut off before the narration finishes.

To enforce this:

1. Estimate spoken duration from the Gemini TTS transcript: word count ÷ 2.5 words per second (about 150 words per minute), plus 1 second per audio tag (e.g. `[curious]`, `[very slow]`) for the pause it implies.
2. Add a 2-second buffer to that estimate.
3. Sum the duration of `actions.yaml`: every `wait` value, plus roughly 1 second for each `click`, `select_option`, `hover`, `fill`, and `press` action (the time it takes Playwright to settle).
4. If the action sequence is shorter than the narration estimate, add another contrast/reversal action or distribute 500–1500 ms waits after visible changes. Do not add one long idle wait.

Do not shrink the narration to fit a fixed 30-second action script — extend the action script to shadow the narration.

## Python Shiny start command

For Python apps, use a fixed port:

```bash
shiny run --host 127.0.0.1 --port 8000 app.py
```

## R Shiny start command

For R apps, use a fixed port:

```bash
Rscript -e 'shiny::runApp(".", host="127.0.0.1", port=8000, launch.browser=FALSE)'
```

## Playwright recorder

Generate `scripts/record_demo.py`.

The recorder should:

* Start the Shiny app as a subprocess.
* Wait for `http://127.0.0.1:8000`.
* Launch Chromium with Playwright.
* Create a browser context with video recording enabled.
* Execute `actions.yaml`.
* Close the browser context so the `.webm` video is saved.
* Stop the Shiny process.
* Convert the saved `.webm` to `.mp4` with `ffmpeg` and write it to `artifacts/demo.mp4`.

Support both a vertical and a horizontal recording size, selected with an `--orientation` flag (default `vertical`). Vertical is the short-form default; horizontal suits landscape/desktop-style demos.

```python
if orientation == "horizontal":
    size = {"width": 1280, "height": 720}  # 16:9
else:
    size = {"width": 720, "height": 1280}  # 9:16

context = browser.new_context(
    viewport=size,
    record_video_dir=str(artifacts_dir),
    record_video_size=size,
)
```

Resolve orientation as: CLI `--orientation` flag first, then an optional `orientation:` key in `actions.yaml`, then `vertical`. Add the flag with `default=None` so the actions-file value is not shadowed:

```python
parser.add_argument("--orientation", choices=["vertical", "horizontal"], default=None)
...
orientation = args.orientation or config.get("orientation", "vertical")
```

Build the Shiny layout for the chosen viewport: one main panel, short labels, readable controls, and reserved overlay space around the app. For vertical, keep phone-readable sizing and reserve space above and below; for horizontal, reserve space along the sides. When narration and 9:16 delivery are the goal, keep vertical; only switch to horizontal when the user asks for a landscape recording.

Use Playwright video recording, not OS-level screen recording.

The recorder's job is not done until `artifacts/demo.mp4` exists. The `.webm` is a working file, not the deliverable.

### Implement the `type` action with human typing speed

Instant `fill` makes demos look machine-generated. For any text the viewer watches being written, type it with a per-character delay (35–70 ms reads as human). Move the caret to the end first so repeated `type` actions append instead of inserting mid-string:

```python
elif "type" in action:
    t = action["type"]
    page.eval_on_selector(
        t["selector"],
        "el => { el.focus(); if (el.setSelectionRange) el.setSelectionRange(el.value.length, el.value.length); }",
    )
    page.locator(t["selector"]).press_sequentially(t["value"], delay=t.get("delay", 45))
```

Newlines in `value` are pressed as Enter, so multi-line notes type naturally into a textarea. Budget its duration as `len(value) × delay` when summing the action script against the narration length.

### Render the `code` action as an animated editor card

In recorder-only output, the `code` action must actually appear on screen — waiting silently is not enough. The recorder injects an editor-style code card into the live page, types the snippet character by character with a blinking cursor, holds it long enough to read, then removes it so the app stays the hero.

Style the card like a small code editor, not a chat bubble: macOS-style window dots, a filename in the title bar (`app.py`), a coding font stack (`'JetBrains Mono','Fira Code','SF Mono',ui-monospace,Menlo`), dark background, generous line height.

Hold the finished snippet long enough for an average viewer to read it. Compute the hold from the character count — about 55 ms per character (≈220 words per minute, slowed for code) plus 1.2 s of orientation, clamped to 3.5–8 s:

```python
hold_ms = cfg.get("duration") or max(3500, min(8000, 1200 + 55 * len(text)))
```

The typewriter animation runs before the hold, so total screen time is typing + hold. Omit `duration` in `actions.yaml` and let the recorder compute it; only hardcode a value when narration timing demands it.

Build the card with DOM nodes and `textContent` (never string-concatenated `innerHTML`) so quotes, `f"..."`, and other code characters render literally:

```python
CODE_OVERLAY_JS = """async (cfg) => {
    const style = document.createElement('style');
    style.id = '__code_overlay_style__';
    style.textContent = '@keyframes __blink {0%,55%{opacity:1}56%,100%{opacity:0}}'
        + '#__code_overlay__ .cursor{animation:__blink 1s step-end infinite;}';
    document.head.appendChild(style);
    const el = document.createElement('div');
    el.id = '__code_overlay__';
    el.style.cssText = 'position:fixed;left:5%;right:5%;top:34%;z-index:99999;'
        + 'background:#0b1020;border:1px solid rgba(255,255,255,.08);'
        + 'border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.55);overflow:hidden;';
    const bar = document.createElement('div');
    bar.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px 14px;'
        + 'background:rgba(255,255,255,.05);border-bottom:1px solid rgba(255,255,255,.06);';
    for (const c of ['#ff5f57', '#febc2e', '#28c840']) {
        const dot = document.createElement('span');
        dot.style.cssText = 'width:11px;height:11px;border-radius:50%;background:' + c + ';';
        bar.appendChild(dot);
    }
    const title = document.createElement('span');
    title.textContent = cfg.title;
    title.style.cssText = 'margin-left:8px;color:#8b93a7;font-size:12.5px;'
        + "font-family:ui-monospace,'SF Mono',Menlo,monospace;";
    bar.appendChild(title);
    const body = document.createElement('div');
    body.style.cssText = 'padding:16px 18px;white-space:pre-wrap;color:#e8ecf4;'
        + "font-family:'JetBrains Mono','Fira Code','SF Mono',ui-monospace,Menlo,monospace;"
        + 'font-size:16px;line-height:1.65;';
    const textSpan = document.createElement('span');
    const cursor = document.createElement('span');
    cursor.className = 'cursor';
    cursor.textContent = '\\u258B';
    cursor.style.color = '#7aa2ff';
    body.appendChild(textSpan);
    body.appendChild(cursor);
    el.appendChild(bar);
    el.appendChild(body);
    document.body.appendChild(el);
    for (let i = 1; i <= cfg.text.length; i++) {
        textSpan.textContent = cfg.text.slice(0, i);
        await new Promise(r => setTimeout(r, cfg.typeMs));
    }
}"""

elif "code" in action:
    cfg = action["code"]
    text = cfg["text"].rstrip("\n")
    hold_ms = cfg.get("duration") or max(3500, min(8000, 1200 + 55 * len(text)))
    page.evaluate(
        CODE_OVERLAY_JS,
        {"title": cfg.get("title", "app.py"), "text": text, "typeMs": cfg.get("type_ms", 22)},
    )
    page.wait_for_timeout(hold_ms)
    page.evaluate(
        "() => { document.getElementById('__code_overlay__')?.remove();"
        " document.getElementById('__code_overlay_style__')?.remove(); }"
    )
```

Place the card so it does not cover the UI region that is reacting (for a bottom-right toast, float the card in the upper-middle). Account for typing time plus hold time when summing the action script's duration.

### Time the code overlay to the narration's code line

When narration audio exists, the `code` action must be on screen while the narrator speaks the code sentence, or the overlay and voice drift apart. Estimate where the code sentence falls in the transcript (words-so-far ÷ 2.5 words/sec, plus ~1 sec per audio tag before it) and schedule the `code` action's start near that time by summing the preceding `actions.yaml` waits and interaction settle time. Extend the reveal beats before it if the overlay would otherwise fire too early.

## Recording command

Add a command the user can run:

```bash
python scripts/record_demo.py --app-type python --actions actions.yaml
```

or:

```bash
python scripts/record_demo.py --app-type r --actions actions.yaml
```

Add `--orientation horizontal` for a 16:9 landscape recording (default is `vertical`, 9:16):

```bash
python scripts/record_demo.py --app-type python --actions actions.yaml --orientation horizontal
```

This produces `artifacts/demo.mp4` as the final deliverable.

## Recorder known issues and fixes

### Shiny session readiness

After `page.wait_for_load_state("networkidle")`, Shiny's WebSocket session may still be initializing. Add a fixed 3-second wait before running actions.

**Do not** poll for `document.body.classList.contains('shiny-connected')` — Shiny for Python does not add this class.

```python
page.wait_for_load_state("networkidle")
page.wait_for_timeout(3000)  # let Shiny WebSocket session initialize
```

### Port conflict

Before starting the recorder, verify the target port is free. A stale Shiny process on port 8000 from a previous run causes `wait_for_server` to succeed immediately (the old server answers), and Playwright will then record the wrong page.

Check and clear before recording:

```bash
lsof -ti :8000 | xargs kill -9 2>/dev/null
```

### Playwright video file naming

Playwright saves videos as UUID-named `.webm` files inside `record_video_dir`. After closing the browser context, rename the most recently modified `.webm` to the configured `video_name`:

```python
videos = sorted(artifacts_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
if videos:
    videos[-1].rename(artifacts_dir / video_name)
```

### Convert the final video to mp4

`.webm` is only the raw Playwright output. After renaming it, convert it to `.mp4` with `ffmpeg` so the deliverable is mp4, not webm:

```python
subprocess.run(
    ["ffmpeg", "-y", "-i", str(artifacts_dir / video_name), str(artifacts_dir / video_name.replace(".webm", ".mp4"))],
    check=True,
)
```

This requires `ffmpeg` to be installed and on `PATH`. If it is missing, report the missing dependency rather than claiming `demo.mp4` was produced.

### wait_for_selector and collapsed panels

Collapsed accordion panels (and other hidden bslib elements) are in the DOM but not visible. Use `state="attached"` when waiting for them — the default `state="visible"` will time out.

```python
page.wait_for_selector("#acc", state="attached", timeout=15000)
```

## Recording constraints

If the environment cannot run browsers, Playwright, Shiny, R, Python, or local servers, explain the missing dependency and still generate the app, action script, and recorder file.

If `ffmpeg` is unavailable, explain that the webm-to-mp4 conversion could not run and that only `demo.webm` exists.

Do not claim a video was recorded unless `artifacts/demo.mp4` exists.

## Silent video editing

When the user asks for complete video editing without audio tracks, generate `edit.yaml` and `scripts/edit_video.py` in addition to the recorder.

Use FFmpeg directly for burned-in overlays. Do not add LosslessCut as a dependency for this workflow; it is useful for manual lossless cuts/remuxing, but FFmpeg is the scriptable editing engine.

Example `edit.yaml`:

```yaml
input: "artifacts/demo.mp4"
output: "artifacts/final.mp4"
canvas:
  width: 1080
  height: 1920

headline:
  start: 0
  end: 7
  text: "Still stacking the same alert?"

beats:
  labels: ["Reveal", "Proof", "Code", "Payoff"]
  cues:
    - {start: 0, end: 7, active: "Reveal"}
    - {start: 7, end: 19, active: "Proof"}
    - {start: 19, end: 23, active: "Code"}
    - {start: 23, end: 30, active: "Payoff"}

captions:
  - {start: 0, end: 2.5, text: "This gets noisy fast."}
  - {start: 2.5, end: 6, text: "Update it instead."}

state_labels:
  - {start: 2, end: 7, text: "#1 REVEAL"}
  - {start: 7, end: 14, text: "#2 PROOF"}

overlays:
  - start: 1
    end: 5
    title: "Did you know?"
    text: "One short hook."

  - start: 20
    end: 27
    title: "Key code"
    text: |
      important_code_line()

  - start: 28
    end: 30
    title: "Takeaway"
    text: "One memorable sentence."
```

Rules:

* Keep `actions.yaml` focused on app interactions and waits; do not burn overlays into the recording when `edit.yaml` will add them.
* `edit_video.py` should read `edit.yaml`, render the 9:16 canvas, headline, captions, state labels, beat rail, and short code card with FFmpeg, strip audio with `-an`, and write `artifacts/final.mp4`.
* Keep the persistent headline to 5–9 words and each caption card to one or two short lines.
* Advance the beat rail at actual story transitions; do not animate it continuously.
* Use one accent color sampled from the app and keep the live UI visible behind code overlays.
* Add punch-ins only on the UI region that visibly reacts, then return to the full composition.
* Verify at least one extracted frame from each overlay window before claiming the edit is complete.

## Gemini 3.1 TTS audio generation

When the user asks for narration audio, voiceover, TTS, or a finished video with audio:

1. Write the complete required Gemini TTS prompt to `artifacts/narration.txt`.
2. Check whether `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set. Never print, persist, or request the key value in chat.
3. If a key is set, run the bundled `scripts/generate_tts.py` with the narration and output paths.
4. Verify `artifacts/narration.wav` exists and is non-empty before reporting success.
5. If neither key is set, keep `artifacts/narration.txt` and give the user the setup command; do not claim audio was generated.

Install the official SDK once:

```bash
python3 -m pip install google-genai
```

Set a key in the shell that launches Codex or Claude:

```bash
export GEMINI_API_KEY="your-key"
```

Generate speech with Gemini 3.1 Flash TTS Preview:

```bash
python3 .agents/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input demo-name/artifacts/narration.txt \
  --output demo-name/artifacts/narration.wav \
  --usage-output demo-name/artifacts/narration.usage.json
```

Claude Code may use the identical script under `.claude/skills/shiny-component-shorts/scripts/generate_tts.py`.

The script defaults to model `gemini-3.1-flash-tts-preview` and voice `Kore`. Allow `--voice` or `--model` overrides when the user requests them. Treat the model as a preview API that may change.

The usage JSON records the API token counts, audio duration, pricing snapshot, and paid-tier list-price estimate. The default pricing snapshot is $1 per million text input tokens and $20 per million audio output tokens; audio output corresponds to 25 tokens per second. Verify the current official Gemini pricing page when the model or pricing changes. Do not describe the estimate as the actual invoice amount because free-tier and account-specific billing may differ.

The browser recording (`artifacts/demo.mp4`) and edited video (`artifacts/final.mp4`, if present) remain silent until audio is merged.

If audio merging is requested, run FFmpeg after `artifacts/narration.wav` exists. Because the action script was padded to be at least as long as the narration, `-shortest` trims only a silent tail.

Example:

```bash
ffmpeg -i artifacts/final.mp4 -i artifacts/narration.wav -c:v copy -c:a aac -shortest artifacts/final_with_audio.mp4
```

Write the merged result as `artifacts/final_with_audio.mp4`, never `.webm`.

## End-of-run cost report

End every workflow that generates artifacts with a `Cost report` section in the final response. When writing a demo directory, also write the information available before handoff to `artifacts/cost-report.md`.

Use this table:

| Service | Usage | Cost | Status |
| --- | ---: | ---: | --- |
| Gemini 3.1 Flash TTS | [input + audio output tokens, duration] | [$ estimate] | Paid-tier list-price estimate or free-tier actual |
| Claude Code or Codex | [tokens, credits, or turns] | [$ or credits] | Exact, included in plan, estimate, or unavailable |
| Local tools | FFmpeg, Playwright, Shiny | $0 API cost | Local compute not priced |

Apply these reporting rules:

1. Read Gemini usage and estimated cost from `artifacts/narration.usage.json`. Report exact token counts but label the dollar value as a paid-tier list-price estimate unless billing data confirms the actual charge.
2. For Claude Code invoked with `claude -p --output-format json`, use the returned `total_cost_usd` after the process exits. This value is available to the caller or wrapper, so it may need to be appended outside Claude's own generated response.
3. For interactive Claude Code sessions, estimate the session cost with the bundled `scripts/claude_session_cost.py`. It parses the session transcript JSONL, dedupes messages, sums tokens per model, and applies list prices (including cache write at 1.25x and cache read at 0.1x input):

   ```bash
   python3 .claude/skills/shiny-component-shorts/scripts/claude_session_cost.py \
     --project-dir ~/.claude/projects/<project-slug> \
     --session <session-uuid>   # omit to use the most recent transcript
   ```

   The project slug is the working directory path with `/` replaced by `-` (e.g. `-Users-name-repos-project`). The session UUID appears in the scratchpad path the harness provides. Label the result `List-price estimate from session transcript` — it measures the whole session so far, not just one video; for a per-video figure, run it before and after and report the delta, or note that the figure covers the session. Suggest the user run `/cost` for the harness-reported value.
4. Match the label to the billing model. Usage-billed accounts (Enterprise per-usage, API): the rule-3 estimate approximates the actual charge, subject to negotiated rates — cite the Console usage dashboard as authoritative. Pro/Max subscription: the marginal charge may be $0 — report it as `what this would cost at API list prices`, never as the invoice amount.
5. For Codex, use token or credit consumption surfaced by the harness or Codex Usage panel. Convert credits to dollars only when the account exposes the applicable credit price. For subscription-included usage, state that the marginal task charge may be $0 while allowance or credits were consumed.
6. If harness usage is unavailable, write `Unavailable from this harness` and tell the user exactly where to retrieve it. Do not estimate hidden reasoning, cached input, tool, or context tokens from visible text.
7. Show a `Known API subtotal` containing only dollar amounts that are actually known or defensible list-price estimates, and — when a Claude session estimate exists — an `Estimated E2E total` that adds the Gemini estimate and the Claude list-price estimate. Label both as estimates; do not present them as an invoice.
8. State the pricing date and currency. Costs change; prefer provider-reported totals over locally calculated totals.

Example:

```text
Cost report — USD, pricing checked 2026-07-13

Gemini TTS: 210 input tokens + 750 audio tokens (30.0 sec)
Paid-tier list-price estimate: $0.015210

Codex: 6.2 credits consumed; dollar conversion unavailable for this account
Known API subtotal: $0.015210, excluding Codex subscription/credit value
```


## Takeaway

[One memorable sentence]

```
```
