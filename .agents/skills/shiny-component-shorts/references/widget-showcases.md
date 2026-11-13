# Widget showcases

Use this workflow for a short video about one [shinywidgets](https://github.com/posit-dev/py-shinywidgets) integration. Start from the [official Jupyter Widgets guide](https://shiny.posit.co/py/docs/jupyter-widgets.html) and the chosen library's documentation. `py-shinywidgets` is the repository name. The package to install and import is `shinywidgets`.

Choose one widget and one useful task. If the user names several widgets, make one independently understandable video for each, unless they request a comparison. If none is named, Plotly is a useful starting point: a Shiny input changes a chart, and the chart retains its own hover and legend controls. Other candidates include a linked Altair selection, an ipyleaflet map control, or a Bokeh chart update. Verify the specific behavior before writing narration.

Give each video a `context` label, specific title, and short outcome sentence in `source-shots.yaml`.
Use `context.layout: showcase` for a cover built from one strong piece of app evidence. Supply a dedicated capture of the result, such as a chart or map with its labels and attribution. Use a short title that fits in two lines on a phone. The cover stays out of playback so the app can fill the opening frame. See [context posters and opening titles](editorial-production.md#context-posters-and-opening-titles).
Set `outro.command` in `reel.yaml` to the tested installation command, so the [end card](editorial-production.md#end-card) shows what the viewer needs to install.

## Plan the explanation

Use editorial framing, hard cuts, readable source, and about 5% margins. The 45-second component quotas, three-action rule, and middle-60% composition do not apply. Keep the video focused on one behavior while giving viewers enough setup to reproduce it.

| Approximate time | Show | Explain |
| --- | --- | --- |
| First 5–8 s | Full-frame live app and first action | What is at stake in the example |
| Next 4–8 s | Install and run commands with one app detail | Which packages the app uses |
| Main sequence | Real app interactions | How the result changes the decision |
| One short code beat | A single excerpt of a few whole lines | What connects the widget to the result |
| Closing beat | The actual outcome, followed by the silent end card | What the viewer can now see or decide |

Aim for 40–60 seconds for a portrait showcase with one simple story. Allow more time when the app interaction needs it. Cut on measured narration. Keep the app visible for most of the runtime and finish the story before the end card.

For portrait-only requests, declare `orientations: [vertical]` in `source-shots.yaml` or `editorial.yaml`. Use `--orientation vertical` for both export and validation. Keep both views for other requests.


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

Show the smallest excerpt from the actual app that explains the interaction. Keep setup and code separate. Keep the complete runnable app in the production directory and link it in the delivery index. Keep sample data local and deterministic when possible. Avoid a network dataset or map key for a chart that needs neither.

## Capture and assemble

Follow [editorial production](editorial-production.md) for bootstrapping, narration takes, cue alignment, rendering, and validation. Copy the [widget starter](../assets/widget-starter/) into the production directory after bootstrapping. Replace its title, cues, source ranges, and media paths for the selected widget.

Use `source-shots.yaml` for readable code and app stills. Each cue must quote the final transcript. In landscape, use `views.horizontal.layout: columns` to place the code beside the related app capture. In portrait, cut between readable code and the app. Capture each orientation separately rather than shrinking a desktop screenshot.

For code beside the app, capture the app at about 550–600 CSS pixels wide so its labels remain readable. Save this narrow capture as `sources/app-horizontal-code.png` for the starter. Keep the full-width landscape capture for shots that show only the app.

Set `code_theme: dark` and `code_wrap: false` on the portrait setup and source views. Start around 30–34 logical pixels. The builder removes common leading indentation and refuses lines that would overflow. If a line is too long, select a smaller excerpt or put a meaningful break in the real app source. Keep tokens on one line and preserve relative indentation and source line numbers. For shell commands, write a valid continuation in the actual setup script and show it as written. Keep the captured app's native appearance and inspect the encoded frames at phone size.

Record widget interactions as continuous, original-speed browser footage. Show the pointer approaching its target, the hover or click, and the widget's actual response. Keep setup, imports, and code as readable stills. Do not substitute changed-state screenshots for an interaction because capture is difficult. Do not move a cursor over a still or animate screenshots to imply a recording.

The starter's `source-shots.yaml` builds the setup and code stills. Its `interaction-shot.yaml` contains the three video shots. Interleave them with the stills in `editorial.yaml` as described in the editorial workflow. Replace its footage paths and `in` points with the clean recordings. Use the same measured narration and actions for both layouts, and record enough footage for the whole shot and final hold.

Verify the app and all planned states before generating voiceover. Wait for the actual widget output and assets, not just the page load. Check the chosen interaction's semantics and any server reaction in both orientations. Reject client errors, missing widgets, blank canvases, and clipped controls. Preserve map attribution and essential limitations.

Resolve mouse targets immediately before the action, after any narration-cue wait and widget layout update. A Shiny rerender can move SVG points after the input value or axis title changes. Wait for the intended rendered point and its settled position, then measure its current box. Verify the actual tooltip or changed state during recording. If a capture method interferes with hover, fix the target timing or use another real browser-video capture method.

Run `prepare_editorial.py`, the normal narration takes and alignment phases, `stitch_reel.py --separate`, and `validate_editorial.py` with the pinned tools. Do not route editorial videos through the component `finish` phase. Review every encoded shot and code excerpt at phone size in both orientations. Check that setup and imports match the delivered app, the interaction matches its narration, and the finished duration is within the requested range. Revise and regenerate if it does not fit naturally.

Deliver the requested orientations, thumbnails, review sheets, the runnable app and its dependency files, editable narration and shot configuration, and a short source index. Report any missing listening check without claiming the voice sounds natural.
