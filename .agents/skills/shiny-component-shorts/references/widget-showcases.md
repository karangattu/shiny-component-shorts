# Widget showcases

Use this workflow for a 60–90 second video about one [shinywidgets](https://github.com/posit-dev/py-shinywidgets) integration. Start from the [official Jupyter Widgets guide](https://shiny.posit.co/py/docs/jupyter-widgets.html) and the chosen library's documentation. `py-shinywidgets` is the repository name. The package to install and import is `shinywidgets`.

Choose one widget and one useful task. If the user names several widgets, make one independently understandable video for each, unless they request a comparison. If none is named, Plotly is a useful starting point: a Shiny input changes a chart, and the chart retains its own hover and legend controls. Other candidates include a linked Altair selection, an ipyleaflet map control, or a Bokeh chart update. Verify the specific behavior before writing narration.

Give each video a `context` label, specific title, and short outcome sentence in `source-shots.yaml`.
The shared scripts automatically generate professional posters and brief opening titles in both orientations.
Use the actual widget capture as evidence. See [context posters and opening titles](editorial-production.md#context-posters-and-opening-titles).
Set `outro.command` in `reel.yaml` to the tested installation command, so the [end card](editorial-production.md#end-card) shows what the viewer needs to install.

## Plan the explanation

Use editorial framing, hard cuts, readable source, and about 5% margins. The 45-second component quotas, three-action rule, and middle-60% composition do not apply. Keep the video focused on one behavior while giving viewers enough setup to reproduce it.

| Approximate time | Show | Explain |
| --- | --- | --- |
| 0–8 s | Working widget and a useful result | The task it solves |
| 8–18 s | Short, tested installation command | Shiny, shinywidgets, and the widget library |
| 18–32 s | Exact imports and the input declaration | Which package supplies each piece |
| 32–48 s | Small rendering function | How a Shiny input changes the widget |
| 48–75 s | Recorded interaction and its actual result | The visible cause and effect |
| 75–90 s, if needed | Return to the result or one useful detail | A relevant boundary or event integration |

These are planning ranges. Measured narration sets the cuts. Do not pad the ending to reach 90 seconds, accelerate speech, or read every code token aloud. Write narration with simple-English meaning and spoken contractions, then apply the usual speech-texture pass. Name the library naturally while the frame shows the exact API spelling.

## Install and render the selected integration

Check the current official examples and install only the selected integration in the production environment. Do not add every widget package to the skill's base requirements.

| Integration | Renderer | Check during setup |
| --- | --- | --- |
| Plotly | `render_plotly` | `plotly`, its FigureWidget dependencies, and a real browser render |
| Altair | `render_altair` | `altair`, its widget dependencies, and the selected interaction API |
| Bokeh | `render_bokeh` | `bokeh` and `jupyter_bokeh` |
| ipyleaflet | `render_widget` | `ipyleaflet`, tile access, and required map attribution |
| Other ipywidgets | `render_widget` | The actual widget type and its frontend assets |

Not every notebook visualization is an ipywidget. Do not promise generic support for a library merely because it displays in Jupyter. Follow the official guide for HTML-based alternatives and library-specific limits. Do not claim a widget event reaches Python unless that callback or reactive trait is implemented and verified.

Prefer Shiny Express. A compact Plotly example can use these commands in a new uv project:

```bash
uv add shiny shinywidgets plotly pandas
uv run shiny run app.py
```

Save the exact tested commands as `setup.sh` for the installation shot. A code panel shows a command, not proof that it ran. Save dependency versions and any actual setup output in the production index. For a requirements-based project, use its explicit virtual-environment interpreter instead.

Express creates the output UI for a decorated rendering function. A Core app instead needs a matching `output_widget()` in the UI and renderer in the server. Keep the syntax consistent throughout a video. A specialized decorator accepts the library's supported chart object. The generic `render_widget` expects a compatible widget.

Show a short excerpt from the actual app for each thought: imports, input, then renderer. Keep the complete runnable app in the production directory and link it in the delivery index. Keep sample data local and deterministic when possible. Avoid a network dataset or map key for a chart that needs neither.

## Capture and assemble

Follow [editorial production](editorial-production.md) for bootstrapping, narration takes, cue alignment, rendering, and validation. Copy the [widget starter](../assets/widget-starter/) into the production directory after bootstrapping. Replace its title, cues, source ranges, and media paths for the selected widget.

Use `source-shots.yaml` for readable code and app stills. Each cue must quote the final transcript. In landscape, use `views.horizontal.layout: columns` to place the code beside the related app capture. In portrait, cut between readable code and the app. Capture each orientation separately rather than shrinking a desktop screenshot.

For code beside the app, capture the app at about 550–600 CSS pixels wide so its labels remain readable. Save this narrow capture as `sources/app-horizontal-code.png` for the starter. Keep the full-width landscape capture for shots that show only the app.

Give code panels a clear boundary against the surrounding canvas. On the light canvas, prefer Shiny charcoal `#1D1F21` code cards with GitHub dark syntax colors, white default text, and light `#CDD4DA` line numbers. Keep the captured app's native appearance. Apply the same code treatment to setup commands and excerpts in both orientations, then inspect the encoded frames at phone size. Do not let a pale code block blend into a similar pale background.

Record widget interactions as continuous, original-speed browser footage. Show the pointer approaching its target, the hover or click, and the widget's actual response. Keep setup, imports, and code as readable stills. Do not substitute changed-state screenshots for an interaction because capture is difficult. Do not move a cursor over a still or animate screenshots to imply a recording.

The starter's `source-shots.yaml` builds the result and code stills. Its `interaction-shot.yaml` is a video-shot fragment, not an input to `prepare_editorial.py`. After building the stills, append that fragment's shot to the assembled `editorial.yaml`, as described in the editorial workflow. Replace its footage paths and `in` points with the clean recordings. Use the same measured narration and actions for both layouts, and record enough footage for the whole shot and final hold.

Verify the app and all planned states before generating voiceover. Wait for the actual widget output and assets, not just the page load. Check the chosen interaction's semantics and any server reaction in both orientations. Reject client errors, missing widgets, blank canvases, and clipped controls. Preserve map attribution and essential limitations.

Resolve mouse targets immediately before the action, after any narration-cue wait and widget layout update. A Shiny rerender can move SVG points after the input value or axis title changes. Wait for the intended rendered point and its settled position, then measure its current box. Verify the actual tooltip or changed state during recording. If a capture method interferes with hover, fix the target timing or use another real browser-video capture method.

Run `prepare_editorial.py`, the normal narration takes and alignment phases, `stitch_reel.py --separate`, and `validate_editorial.py` with the pinned tools. Do not route editorial videos through the component `finish` phase. Review every encoded shot and code excerpt at phone size in both orientations. Check that setup and imports match the delivered app, the interaction matches its narration, and the finished duration is within the requested range. Revise and regenerate if it does not fit naturally.

Deliver both videos, thumbnails, review sheets, the runnable app and its dependency files, editable narration and shot configuration, and a short source index. Report any missing listening check without claiming the voice sounds natural.
