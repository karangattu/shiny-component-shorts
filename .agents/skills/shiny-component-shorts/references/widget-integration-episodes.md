# Widget integration episodes

Use this workflow when a request names an app from the [shinywidgets gallery](https://posit-dev.github.io/py-shinywidgets/gallery/), asks for a video about a widget integration, or asks for the "You Can Build This with Shiny" series. It builds on [widget showcases](widget-showcases.md) and [editorial production](editorial-production.md). Where this guide differs from them, this guide applies.

## The idea every episode carries

An interaction inside one Python library becomes an input to another part of the Shiny app. A lasso on a chart filters a table. A box on a map selects cities. A click on a network runs a graph query.

Each episode shows one such link. It does not introduce a package, and it does not list supported libraries. The viewer should finish knowing that a widget can drive other outputs and that Python can change the widget in return.

## Start from the catalog

[`episodes.yaml`](../assets/integration-episode-starter/episodes.yaml) lists the eight planned episodes in release order. Each entry gives the gallery example, the libraries, the renderers, the one accessor to show, the install command, the hook action, the demo actions, and the result. Produce Plotly, Lonboard, and K3D first: they cover a chart, a map, and a 3D scene.

The catalog records the commit it was checked against. The gallery changes, so confirm each entry before you plan:

1. Get the example's source from `website/gallery/<gallery>/` in `posit-dev/py-shinywidgets`. Use an existing local clone when there is one. Record the commit in the production index.
2. Open `app.py`. Confirm that the accessor, the renderer, and every control named in `demo` are still there. Update the entry if they changed.
3. Run the app with the `run` command from the example's `index.md`. Perform the hook and each demo action by hand before you write narration.

### Add an episode for another gallery example

Every gallery example has the same four files. Read them in this order:

| File | Take from it |
| --- | --- |
| `index.md` front matter | `title` (the example name), `widgets` (the libraries), `pattern` (the link to show, such as `selection -> table`), `summary`, and `run` |
| `requirements.txt` | The install command for the end card |
| `app.py` | The renderer decorators and the accessor: a method called on the render function's name, such as `plot.selected_rows(df)` |
| `img/` | Nothing for the video. Capture the cover from your own recording. |

Choose the one accessor that carries the `pattern`. Then add an entry to `episodes.yaml` with the same keys as the others. Write `hook` as an action and its visible result. Write `title` as a plain statement of the effect, in two phone lines or fewer.

## The four beats

Aim for 45–55 seconds before the end card. That is about 110–130 spoken words. Measure the narration; do not estimate it.

| Time | Beat | On screen | Narration |
| --- | --- | --- | --- |
| 0–3 s | Hook | The interaction and its result in another component | One short sentence that says what just happened |
| 3–20 s | Demo | The working app: what the data is, then one or two more real interactions | Why each result matters, not where the mouse moves |
| 20–37 s | Integration | The app, still in use | Name each library and its job, then say what shinywidgets connects |
| 37–50 s | Get started | A few whole lines of `app.py` with the accessor line highlighted, then the app result | What the line returns, the gallery example's name, and the conclusion |
| After | End card | Install command and the gallery address | Silent |

Rules for the beats:

- **The hook is footage.** The first frame is the app with the interaction about to happen. Finish the action and show its result inside three seconds. Do not open on a poster, a title, a package name, or the words "shinywidgets".
- **The cover stays out of playback.** Use `context.layout: showcase` with the `label` and `title` from the catalog. The cover becomes the thumbnail. This replaces the integration poster that other vertical shorts open on.
- **Name the libraries in the integration beat, not before.** One job for each library in `integration`, then the link: "shinywidgets sends the selection to Python."
- **Show one accessor.** Use the `accessor` from the catalog. Show the smallest run of whole lines around it from the real `app.py`, and set `highlight` to its line. Do not scroll the file and do not show a second excerpt. The names under `also` are for your own understanding of the app.
- **Name the starting point as a fact.** Say which gallery example the app is, such as "This app is the Lasso explorer in the shinywidgets gallery." Do not tell the viewer to go there. The end card does that.
- **End on the conclusion.** One or two plain sentences on what the viewer now knows and when it matters. Use the entry's `payoff` and `audience` as the source.

### Keep the house voice

The source ideas for this series phrase each hook as a question, such as "What if drawing on a chart could filter your entire dashboard?" Narration in this skill never asks a pitch question and never speaks a call to action. Turn each one into a statement of what the viewer sees:

| Do not say | Say |
| --- | --- |
| "What if drawing on a chart could filter your whole dashboard?" | "I lasso a few points, and the table keeps only those countries." |
| "Start with the Lasso explorer in the gallery." | "This app is the Lasso explorer in the shinywidgets gallery." |
| "No custom JavaScript required." | "The app has no JavaScript of its own." Say this only after you check that it is true. |

A question can still be the text of the social post that carries the video. Write every script with the `simple-english` skill, as for any other video.

## Record the app

Use the gallery `app.py` as the evidence. The code on screen comes from that file, unchanged.

- **Fill the phone frame with the component.** Record the vertical take in a portrait viewport. The widget and the output it drives must both be readable at phone size in the same frame, or in two frames joined by a hard cut on the action. Never shrink a desktop dashboard into a 9:16 frame.
- **Change layout only when you must.** If the gallery app does not fit a portrait viewport, record a production copy that changes layout only: stack the widget above the linked output, and collapse or remove a sidebar the episode does not use. Keep the reactive code, the data, and the widget options as they are. List each change in the production index. The code still shows the gallery file, not the copy.
- **Record real interactions.** A lasso, a box selection, an orbit, and a camera flight are drags and animations. Record them as continuous browser footage at original speed, and hold until the linked output has finished updating.
- **Wait for the widget, not the page.** WebGL canvases, map tiles, and streaming tables finish loading after the page does. Reject a blank canvas, missing tiles, or a client error.
- **Keep what the widget requires.** Map attribution stays visible. Read each entry's `notes` for simulated data, live values that differ between takes, and the chat rule.
- **Never call a real LLM.** For an example with a chat, record a production copy with scripted replies and tool calls. Keep the widget accessor and the code path that moves the widget real.

The tooling has no click magnifier and no free text overlay. Make the action readable through the capture size and the cut. The cover label, the highlighted code line, and the burned-in captions carry the package and method names.

## Assemble

Bootstrap the production as [editorial production](editorial-production.md) describes. Copy the [integration episode starter](../assets/integration-episode-starter/) into the production directory:

| File | Use |
| --- | --- |
| `episodes.yaml` | The catalog. Copy the one entry you are producing into the production index. |
| `source-shots.yaml` | The cover and the single code still |
| `interaction-shot.yaml` | The four footage beats, with the code still placed before the result |
| `reel.yaml` | The end card: the entry's `install` command and the gallery address |

Then follow the capture, narration, alignment, and validation steps in [widget showcases](widget-showcases.md#capture-and-assemble). Ship both orientations from the same actions and narration. In the horizontal video, show the code beside the app. Burn captions into the vertical video as [social captions](social-captions.md) describes, and use a different caption style and code theme for each episode in the series.

## Check before delivery

- The result of the hook is visible by the three-second mark.
- No library or package name is spoken before the integration beat.
- Exactly one code still appears, and its highlighted line contains the catalog `accessor`.
- The narration names the gallery example, asks no question, and gives no instruction to the viewer.
- The end card shows the install command you tested and the gallery address. On the vertical card, the command breaks only at spaces.
- The production index records the gallery commit, any layout-only changes, and any scripted chat.
