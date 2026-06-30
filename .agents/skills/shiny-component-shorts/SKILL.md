---

name: Shiny Component Shorts
description: Create tiny Shiny Python or R mini-apps, 30-second "Did you know?" video concepts, Gemini TTS narration scripts, storyboards, and recording notes for Shiny components. Use when the user provides a Shiny component name, Shiny docs URL, or asks for a short demo/video around a Shiny UI feature.
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

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
|   0-3 sec | Show the boring/default pattern | Short pain-point line           |
|   3-8 sec | Reveal the feature              | "Did you know..." line          |
|  8-20 sec | Interact with the mini-app      | Show the feature changing state |
| 20-27 sec | Highlight the key code line     | Explain only the important line |
| 27-30 sec | End on result                   | Memorable takeaway              |

The storyboard should be visual and recordable. Avoid abstract explanation.

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
[curious] Did you know this tiny dropdown can control the whole card?

[very fast] Instead of sending every filter to a giant sidebar, Shiny lets the control live right inside the card header.

Now watch the card change itself when I pick a new view.

The trick is this one line: `ui.toolbar_input_select()`.

[very slow] A filter does not have to live beside the chart. Sometimes it belongs in the chart's own roof.
```

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
9. If recording is requested, the app has stable selectors.
10. If recording is requested, the action script matches the storyboard.
11. If recording is requested, the recorder starts and stops the Shiny server cleanly.
12. Do not claim a video was recorded unless an output file exists.

## Avoid

* Full component tutorials
* Long parameter tours
* Apps that require too much data setup
* Purely cosmetic changes unless the visual result is dramatic
* Multiple tricks in one video
* Abstract reactivity explanations without visible interaction
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
| 0-3 sec | [Visual] | [Narration] |
| 3-8 sec | [Visual] | [Narration] |
| 8-20 sec | [Visual] | [Narration] |
| 20-27 sec | [Visual] | [Narration] |
| 27-30 sec | [Visual] | [Narration] |

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

## Recording output files

When recording is requested, create this structure:

```text
demo-name/
├── app.py                  # Python Shiny app, if Python
├── app.R                   # R Shiny app, if R
├── actions.yaml            # Browser action script
├── scripts/
│   └── record_demo.py      # Playwright recorder
└── artifacts/
    └── demo.webm           # Recorded browser video
```

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

  - press:
      selector: "body"
      key: "Escape"

  - screenshot:
      path: "artifacts/final.png"
```

Rules:

* Every action should connect to the storyboard.
* Keep the total action sequence close to 30 seconds.
* Add short waits after visible state changes.
* Do not over-click.
* Use selectors that exist in the generated app.
* If the component needs a hover, use `hover`.
* If the component needs a select input, use `select_option`.
* If the component needs typing, use `fill`.
* If the component needs a button, use `click`.

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
* Close the browser context so the video is saved.
* Stop the Shiny process.

Use Playwright video recording, not OS-level screen recording.

## Recording command

Add a command the user can run:

```bash
python scripts/record_demo.py --app-type python --actions actions.yaml
```

or:

```bash
python scripts/record_demo.py --app-type r --actions actions.yaml
```

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

### wait_for_selector and collapsed panels

Collapsed accordion panels (and other hidden bslib elements) are in the DOM but not visible. Use `state="attached"` when waiting for them — the default `state="visible"` will time out.

```python
page.wait_for_selector("#acc", state="attached", timeout=15000)
```

## Recording constraints

If the environment cannot run browsers, Playwright, Shiny, R, Python, or local servers, explain the missing dependency and still generate the app, action script, and recorder file.

Do not claim a video was recorded unless the file exists in `artifacts/`.

## Optional audio step

The browser recording should produce silent video.

The Gemini TTS narration should remain a separate text artifact unless the user asks to synthesize audio and combine it with the video.

If audio merging is requested, generate a separate step using `ffmpeg` after the TTS audio file exists.

Example:

```bash
ffmpeg -i artifacts/demo.webm -i artifacts/narration.wav -c:v copy -c:a aac -shortest artifacts/final.mp4
```


## Takeaway

[One memorable sentence]

```
```
