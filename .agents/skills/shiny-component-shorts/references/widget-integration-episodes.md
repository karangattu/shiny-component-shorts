# Widget integration episodes

Use this workflow when a request names an app from the [shinywidgets gallery](https://posit-dev.github.io/py-shinywidgets/gallery/), asks for a video about a widget integration, or asks for the "You Can Build This with Shiny" series. It builds on [widget showcases](widget-showcases.md) and [editorial production](editorial-production.md). Where this guide differs from them, this guide applies.

## The idea every episode carries

An interaction inside one Python library becomes an input to another part of the Shiny app. A lasso on a chart filters a table. A box on a map selects cities. A click on a network runs a graph query.

Each episode shows one such link. It does not introduce a package, and it does not list supported libraries. The viewer should finish knowing that a widget can drive other outputs and that Python can change the widget in return.

## Start from the catalog

[`episodes.yaml`](../assets/integration-episode-starter/episodes.yaml) lists the eight planned episodes in release order. Each entry gives the gallery example, the libraries, the renderers, the one accessor to show, the install command, the hook action, the demo actions, the result, and the episode's planned `look`. Produce Plotly, Lonboard, and K3D first: they cover a chart, a map, and a 3D scene.

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

Choose the one accessor that carries the `pattern`. Then add an entry to `episodes.yaml` with the same keys as the others. Write `hook` as an action and its visible result. Write `title` as a plain statement of the effect, in 32 characters or fewer. The portrait cover rejects a longer title. Then run `look.py assign` to give the new entry a look.

### Draft a new episode from a gallery link

`assets/integration-episode-starter/make_episode.py` writes a reviewable production skeleton. It is specific to py-shinywidgets: it reads a local clone's `website/gallery/<gallery>/app.py`, `requirements.txt`, and the `index.md` front matter when present. Copy it beside the production's `.video-skill` directory, then run:

```bash
python make_episode.py --project-dir generated/you-can-build-this/<episode-id> \
  --url "https://posit-dev.github.io/py-shinywidgets/gallery/templates/<example>/" \
  --repo ../py-shinywidgets
```

`--gallery` can replace or override the gallery path in the URL. Pass `--id`, `--title`, `--widgets`, `--accessor`, and `--install` when front matter is missing. The script detects renderers and a likely accessor from `app.py`, copies the source with its `data/` and `img/` folders, writes a draft `episode.yaml`, `episodes.yaml`, `source-shots.yaml`, `reel.yaml`, `capture.yaml`, and a local-voice `tts-settings.json`, and lists the checks in `PRODUCTION.md`. It never overwrites a non-empty directory without `--force`, and it makes no network calls.

A link to a component page, pull request, or commit is accepted as provenance, but those pages carry no gallery front matter. The draft marks the gallery, accessor, and hook as TODO instead of guessing; confirm the example from the gallery before planning. A changeset still follows [changeset-sourcing.md](changeset-sourcing.md).

## The four beats

Aim for 45–55 seconds before the end card, and about 60 seconds in total. That is about 125–140 spoken words. Measure the narration; do not estimate it. The times below are targets. The order of the beats matters more than the exact second each one starts.

| Time | Beat | On screen | Narration |
| --- | --- | --- | --- |
| 0–3 s | Hook | The interaction and its result in another component | One short sentence that says what just happened |
| 3–20 s | Demo | The working app: what the data is, then one or two more real interactions | Why each result matters, not where the mouse moves |
| 20–37 s | Integration | The app, still in use | Name each library and its job, then say what shinywidgets connects |
| 37–50 s | Get started | A few whole lines of `app.py` with the accessor line highlighted, then the app result | What the line returns, the gallery example's name, and the conclusion |
| Last 5 s | End card | The Shiny wordmark, the title from the episode's look, and the py-shinywidgets address | The closing line: "To try this integration, go to the py-shinywidgets website." |

Rules for the beats:

- **The hook is footage.** The first frame is the app with the interaction about to happen. Finish the action and show its result inside three seconds. Do not open on a poster, a title, a package name, or the words "shinywidgets".
- **The cover stays out of playback.** Use `context.layout: showcase` with the `label` and `title` from the catalog. The cover becomes the thumbnail. This replaces the integration poster that other vertical shorts open on.
- **Name the libraries in the integration beat, not before.** One job for each library in `integration`, then the link: "shinywidgets sends the selection to Python."
- **Show one accessor.** Use the `accessor` from the catalog. Show the smallest run of whole lines around it from the real `app.py`, and set `highlight` to its line. Do not scroll the file and do not show a second excerpt. The names under `also` are for your own understanding of the app.
- **Name the starting point as a fact.** Say which gallery example the app is, such as "This app is the Lasso explorer in the shinywidgets gallery."
- **End on the conclusion, then speak the closing line.** Give one or two plain sentences on what the viewer now knows and when it matters. Use the entry's `payoff` and `audience` as the source. Then pause, and say the catalog's `closing_line` over the end card. This series is the one place where the narration speaks a call to action, and it speaks only that sentence.
- **Follow the order in the look.** `integration-code` is the order in the table. `code-integration` shows the code line straight after the demo and names the libraries after it, so the integration beat runs to about 37 s and the last beat keeps the app result, the gallery example's name, and the conclusion. In both orders, speak no library name before the integration beat.
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

## Planned variety

A series of 20 or more episodes must not look like one video made 20 times. Each catalog entry has a `look` that sets five things:

| Key | Values | Where it shows |
| --- | --- | --- |
| `captions` | `clean`, `pill`, `karaoke`, `outline`, `card`, `bar` | The burned-in captions in the portrait video |
| `code_theme` | `dark`, `light` | The code still |
| `order` | `integration-code`, `code-integration` | The order of the two middle beats |
| `code_side` | `left`, `right` | The side the code sits on in the landscape video |
| `card_title` | Four titles, listed in `look.py` | The end card |

Do not choose these values yourself, and do not draw them at render time. `look.py assign` draws each look from the catalog's `look_seed` and the episode id, and stores it in `episodes.yaml`. A rerender then gives the same video, and a new episode never changes an older one. The script keeps neighbours apart: a caption style does not repeat within two episodes, and two episodes in a row never share an end card title or share both the order and the code theme. `look.py check` reports a catalog that breaks these rules.

`look.py apply <project> <episode>` writes the look into the production: the code theme and the panel order in `source-shots.yaml`, the title in `reel.yaml`, and a `look.yaml` that `assemble.py` reads for the order. Burn the captions with the style in `look.yaml`.

The look does not cover words. Write a different opening sentence and conclusion for each episode, and run `check_narration_voice.py` across the series to find phrasing the scripts share.

These parts stay the same in every episode, because they make it a series: the hook is footage, one accessor line, the gallery example's name, and the closing line over the end card.

## Record the app

Use the gallery `app.py` as the evidence. The code on screen comes from that file, unchanged.

- **Leave the caption band empty in portrait.** Captions sit about 18% above the bottom edge, and social apps cover what is below them. Add bottom padding to the portrait copy so the app ends about 75% of the way down the frame, such as `body { padding-bottom: 300px }` in a 720×1280 viewport. Without it, the captions cover the linked output.
- **Give the linked output the height.** In the portrait copy, remove the page title and give the widget and its output equal rows, such as `row_heights=[1, 1]`. A table's own search and paging controls take most of a short card, so check that at least three rows show.
- **Fill the phone frame with the component.** Record the vertical take in a portrait viewport. The widget and the output it drives must both be readable at phone size in the same frame, or in two frames joined by a hard cut on the action. Never shrink a desktop dashboard into a 9:16 frame.
- **Change layout only when you must.** If the gallery app does not fit a portrait viewport, record a production copy that changes layout only: stack the widget above the linked output, and collapse or remove a sidebar the episode does not use. Keep the reactive code, the data, and the widget options as they are. List each change in the production index. The code still shows the gallery file, not the copy.
- **Record real interactions.** A lasso, a box selection, an orbit, and a camera flight are drags and animations. Record them as continuous browser footage at original speed, and hold until the linked output has finished updating.
- **Set up the hook off camera.** Switch to the tab that shows the linked output and arm the selection tool before the recording starts. A box or lasso needs about two seconds of pointer travel, so `capture.py` presses its first corner off camera when the opening action has `at`. The recording then opens on the shape about to stretch, and the result lands at about two seconds.
- **Use pixel points for a canvas or a widget frame.** A map, a 3D scene, and a WebGL scatter plot have no selectors, and a selector does not reach inside a widget's own iframe, such as the mols2grid grid. Give each orientation its own points in `capture.yaml`, read from a preflight screenshot. Every layout change moves them, so run the preflight again.
- **Draw a lasso as a `drag`.** Name the corners of the lasso as points, and take them from the chart's axes when you can: in Plotly, `gd._fullLayout.xaxis.l2p(value)` plus the axis offset gives the pixel for a data value. Keep every point below the Plotly toolbar, which appears on hover and takes the press.
- **Find the real click target.** Press the control in the preflight and read the result before you write the sentence about it. In the Chemical explorer the arrow button on a structure opens the card, and a click on the drawing does nothing.
- **Write names the way they are said.** In the transcript, write "Shiny Widgets" for the spoken name, and keep "py-shinywidgets" as it is: the local voice says it as "pie shiny widgets". The recognizer hears "Lonboard" and "ITables" as other words, and that is not a defect when the audio is right.
- **Wait for the widget, not the page.** WebGL canvases, map tiles, and streaming tables finish loading after the page does. Reject a blank canvas, missing tiles, or a client error.
- **Keep what the widget requires.** Map attribution stays visible. Read each entry's `notes` for simulated data, live values that differ between takes, and the chat rule.
- **Never call a real LLM.** For an example with a chat, record a production copy with scripted replies and tool calls. Keep the widget accessor and the code path that moves the widget real.

The tooling has no click magnifier and no free text overlay. Make the action readable through the capture size and the cut. The cover label, the highlighted code line, and the burned-in captions carry the package and method names.

### Browser flags and idle footage

Some widget canvases need browser flags. Put them in `capture.yaml` as an opt-in list; the starter forwards them to Chromium:

```yaml
browser_args: ["--enable-unsafe-webgpu", "--use-angle=metal"]
```

Preflight then checks for a WebGPU adapter and for the widget's "WebGPU is unavailable" notice, and fails before recording if the canvas would be blank. The check only runs when a browser argument mentions WebGPU.

The recorder prints `WARNING: long hold: ...` for a clip with more than seven seconds between visible actions. A hold on the final result is deliberate and is not reported; recut the others, add a real interaction, or shorten the narration beat.

## Assemble

Bootstrap the production as [editorial production](editorial-production.md) describes. Copy the [integration episode starter](../assets/integration-episode-starter/) into the production directory:

| File | Use |
| --- | --- |
| `episodes.yaml` | The catalog. Copy the one entry you are producing into the production index. |
| `capture.yaml` | The verified actions for one episode: the setup, each clip's cue, and each action with the phrase it lands on. The starter holds the tested Lonboard episode. |
| `capture.py` | Runs `capture.yaml`. `preflight` performs every action and prints the result. `record` times each action to the measured narration. Put it beside `.video-skill`. |
| `look.py` | Assigns the planned look to each catalog entry, and applies one to a production. Put it beside `.video-skill`. |
| `source-shots.yaml` | The cover and the single code still |
| `assemble.py` | Places the recorded clips around the code still in `editorial.yaml`, in the look's order. It stops when a clip's `end` phrase is not where the next shot starts. |
| `reel.yaml` | The end card. `outro.spoken` names the first words of the closing line, and `assemble.py` adds the card as the last shot on that phrase. |
| `make_episode.py` | Optional py-shinywidgets scaffolder: drafts a reviewable production from a gallery link, a gallery id, or explicit metadata. |

When a gallery line is too long for the card but splits a name under `code_wrap: false`, set `code_wrap: smart` on the view. It dedents the excerpt and wraps long lines at spaces with a four-character hanging indent. An unbreakable token still fails the overflow check rather than being split.

Work in this order: apply the look, preflight both orientations, build the stills, write the narration from the values the preflight printed, generate and pin the takes, record, assemble, render, validate, then burn the captions with `--stop-at` set to the first words of the closing line. The end card shows its own text, so captions stop before it.

Then follow the capture, narration, alignment, and validation steps in [widget showcases](widget-showcases.md#capture-and-assemble). Ship both orientations from the same actions and narration. In the horizontal video, show the code beside the app. Burn captions into the vertical video as [social captions](social-captions.md) describes, with the caption style from the episode's look.

## Check before delivery

- The result of the hook is visible by the three-second mark.
- No library or package name is spoken before the integration beat.
- Exactly one code still appears, and its highlighted line contains the catalog `accessor`.
- The narration names the gallery example and asks no question. Its only instruction to the viewer is the closing line.
- The end card appears on the first word of the closing line and stays until the video ends.
- The end card shows the py-shinywidgets address. It shows an install command only when the release has shipped and you tested the command. On the vertical card, the command breaks only at spaces.
- In the captioned portrait video, no caption covers the widget or the output it drives.
- Every frame shows one pointer arrow. A widget that draws in its own iframe gets its own demo cursor, and a second arrow left on screen makes the recording look fake. The recorder and `capture.py` stop when two show, so do not work around that error. Still look for it in the review frames, with any other mark the app did not draw: a stale tooltip, a leftover selection box, or a cursor that jumps.
- The caption style, code theme, beat order, code side, and end card title match the episode's `look`.
- The production index records the gallery commit, any layout-only changes, and any scripted chat.
