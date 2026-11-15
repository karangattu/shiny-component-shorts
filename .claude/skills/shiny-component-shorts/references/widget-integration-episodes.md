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
3. Check that the release has shipped: compare the newest `shinywidgets` on PyPI with the renderer and the `shinywidgets[...]` extras the example needs. While the catalog says `released: false`, install `shinywidgets` from the repository clone to record, and leave the install command off the end card.
4. Run the app in a new environment built from the example's `requirements.txt`. If it fails, add the missing package and record it in the production index. The Lonboard example needed `pyarrow`.
5. Perform the hook and each demo action before you write narration, and read the real values the app shows. The starter's `capture.py preflight` does this and prints them.

### Add an episode for another gallery example

Every gallery example has the same four files. Read them in this order:

| File | Take from it |
| --- | --- |
| `index.md` front matter | `title` (the example name), `widgets` (the libraries), `pattern` (the link to show, such as `selection -> table`), `summary`, and `run` |
| `requirements.txt` | The install command for the end card |
| `app.py` | The renderer decorators and the accessor: a method called on the render function's name, such as `plot.selected_rows(df)` |
| `img/` | Nothing for the video. Capture the cover from your own recording. |

Choose the one accessor that carries the `pattern`. Then add an entry to `episodes.yaml` with the same keys as the others. Write `hook` as an action and its visible result. Write `title` as a plain statement of the effect, in 32 characters or fewer. The portrait cover rejects a longer title.

## The four beats

Aim for 45–55 seconds before the end card, and about 60 seconds in total. That is about 125–140 spoken words. Measure the narration; do not estimate it. The times below are targets. The order of the beats matters more than the exact second each one starts.

| Time | Beat | On screen | Narration |
| --- | --- | --- | --- |
| 0–3 s | Hook | The interaction and its result in another component | One short sentence that says what just happened |
| 3–20 s | Demo | The working app: what the data is, then one or two more real interactions | Why each result matters, not where the mouse moves |
| 20–37 s | Integration | The app, still in use | Name each library and its job, then say what shinywidgets connects |
| 37–50 s | Get started | A few whole lines of `app.py` with the accessor line highlighted, then the app result | What the line returns, the gallery example's name, and the conclusion |
| Last 5 s | End card | The Shiny wordmark, "Try this integration", and the py-shinywidgets address | The closing line: "To try this integration, go to the py-shinywidgets website." |

Rules for the beats:

- **The hook is footage.** The first frame is the app with the interaction about to happen. Finish the action and show its result inside three seconds. Do not open on a poster, a title, a package name, or the words "shinywidgets".
- **The cover stays out of playback.** Use `context.layout: showcase` with the `label` and `title` from the catalog. The cover becomes the thumbnail. This replaces the integration poster that other vertical shorts open on.
- **Name the libraries in the integration beat, not before.** One job for each library in `integration`, then the link: "shinywidgets sends the selection to Python."
- **Show one accessor.** Use the `accessor` from the catalog. Show the smallest run of whole lines around it from the real `app.py`, and set `highlight` to its line. Do not scroll the file and do not show a second excerpt. The names under `also` are for your own understanding of the app.
- **Name the starting point as a fact.** Say which gallery example the app is, such as "This app is the Lasso explorer in the shinywidgets gallery."
- **End on the conclusion, then speak the closing line.** Give one or two plain sentences on what the viewer now knows and when it matters. Use the entry's `payoff` and `audience` as the source. Then pause, and say the catalog's `closing_line` over the end card. This series is the one place where the narration speaks a call to action, and it speaks only that sentence.
- **Put a pause between beats.** Write a `[pause 1s]` tag after the hook, between the beats, and before the closing line. Without them the local voice runs past the 160 words-per-minute gate and every take is rejected.

### Keep the house voice

The source ideas for this series phrase each hook as a question, such as "What if drawing on a chart could filter your entire dashboard?" Narration in this skill never asks a pitch question, and it speaks no call to action except the closing line. Turn each hook into a statement of what the viewer sees:

| Do not say | Say |
| --- | --- |
| "What if drawing on a chart could filter your whole dashboard?" | "I lasso a few points, and the table keeps only those countries." |
| "Start with the Lasso explorer in the gallery." | "This app is the Lasso explorer in the shinywidgets gallery." |
| "Check out the website and try it today." | "To try this integration, go to the py-shinywidgets website." Say it once, as the last sentence. |
| "No custom JavaScript required." | "The app has no JavaScript of its own." Say this only after you check that it is true. |

A question can still be the text of the social post that carries the video. Write every script with the `simple-english` skill, as for any other video.

## Record the app

Use the gallery `app.py` as the evidence. The code on screen comes from that file, unchanged.

- **Leave the caption band empty in portrait.** Captions sit about 18% above the bottom edge, and social apps cover what is below them. Add bottom padding to the portrait copy so the app ends about 75% of the way down the frame, such as `body { padding-bottom: 300px }` in a 720×1280 viewport. Without it, the captions cover the linked output.
- **Give the linked output the height.** In the portrait copy, remove the page title and give the widget and its output equal rows, such as `row_heights=[1, 1]`. A table's own search and paging controls take most of a short card, so check that at least three rows show.
- **Fill the phone frame with the component.** Record the vertical take in a portrait viewport. The widget and the output it drives must both be readable at phone size in the same frame, or in two frames joined by a hard cut on the action. Never shrink a desktop dashboard into a 9:16 frame.
- **Change layout only when you must.** If the gallery app does not fit a portrait viewport, record a production copy that changes layout only: stack the widget above the linked output, and collapse or remove a sidebar the episode does not use. Keep the reactive code, the data, and the widget options as they are. List each change in the production index. The code still shows the gallery file, not the copy.
- **Record real interactions.** A lasso, a box selection, an orbit, and a camera flight are drags and animations. Record them as continuous browser footage at original speed, and hold until the linked output has finished updating.
- **Set up the hook off camera.** Switch to the tab that shows the linked output and arm the selection tool before the recording starts. A box or lasso needs about two seconds of pointer travel, so `capture.py` presses its first corner off camera when the opening action has `at`. The recording then opens on the shape about to stretch, and the result lands at about two seconds.
- **Use pixel points for a canvas.** A map, a 3D scene, and a WebGL scatter plot have no selectors. Give each orientation its own points in `capture.yaml`, read from a preflight screenshot. Every layout change moves them, so run the preflight again.
- **Write names the way they are said.** In the transcript, write "Shiny Widgets" for the spoken name, and keep "py-shinywidgets" as it is: the local voice says it as "pie shiny widgets". The recognizer hears "Lonboard" and "ITables" as other words, and that is not a defect when the audio is right.
- **Wait for the widget, not the page.** WebGL canvases, map tiles, and streaming tables finish loading after the page does. Reject a blank canvas, missing tiles, or a client error.
- **Keep what the widget requires.** Map attribution stays visible. Read each entry's `notes` for simulated data, live values that differ between takes, and the chat rule.
- **Never call a real LLM.** For an example with a chat, record a production copy with scripted replies and tool calls. Keep the widget accessor and the code path that moves the widget real.

The tooling has no click magnifier and no free text overlay. Make the action readable through the capture size and the cut. The cover label, the highlighted code line, and the burned-in captions carry the package and method names.

## Assemble

Bootstrap the production as [editorial production](editorial-production.md) describes. Copy the [integration episode starter](../assets/integration-episode-starter/) into the production directory:

| File | Use |
| --- | --- |
| `episodes.yaml` | The catalog. Copy the one entry you are producing into the production index. |
| `capture.yaml` | The verified actions for one episode: the setup, each clip's cue, and each action with the phrase it lands on. The starter holds the tested Lonboard episode. |
| `capture.py` | Runs `capture.yaml`. `preflight` performs every action and prints the result. `record` times each action to the measured narration. Put it beside `.video-skill`. |
| `source-shots.yaml` | The cover and the single code still |
| `assemble.py` | Places the recorded clips around the code still in `editorial.yaml`, with the still before the last clip |
| `reel.yaml` | The end card. `outro.spoken` names the first words of the closing line, and `assemble.py` adds the card as the last shot on that phrase. |

Work in this order: preflight both orientations, build the stills, write the narration from the values the preflight printed, generate and pin the takes, record, assemble, render, validate, then burn the captions with `--stop-at` set to the first words of the closing line. The end card shows its own text, so captions stop before it.

Then follow the capture, narration, alignment, and validation steps in [widget showcases](widget-showcases.md#capture-and-assemble). Ship both orientations from the same actions and narration. In the horizontal video, show the code beside the app. Burn captions into the vertical video as [social captions](social-captions.md) describes, and use a different caption style and code theme for each episode in the series.

## Check before delivery

- The result of the hook is visible by the three-second mark.
- No library or package name is spoken before the integration beat.
- Exactly one code still appears, and its highlighted line contains the catalog `accessor`.
- The narration names the gallery example and asks no question. Its only instruction to the viewer is the closing line.
- The end card appears on the first word of the closing line and stays until the video ends.
- The end card shows the py-shinywidgets address. It shows an install command only when the release has shipped and you tested the command. On the vertical card, the command breaks only at spaces.
- In the captioned portrait video, no caption covers the widget or the output it drives.
- The production index records the gallery commit, any layout-only changes, and any scripted chat.
