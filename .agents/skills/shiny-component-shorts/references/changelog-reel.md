# Changelog reel

A changelog reel walks through the new features of one release, one after another. An animated feature card ("02 of 04", the feature title, and one line on why it helps) comes before each feature, so the viewer always knows a new feature is starting. The reel informs. It does not chase one hidden trick.

## Pick the release and the features

```bash
python .agents/skills/shiny-component-shorts/scripts/changelog_features.py \
  https://github.com/posit-dev/py-shiny/blob/main/CHANGELOG.md \
  --output generated/reel-py-shiny-next/features.json
```

- The source can be a local path, a URL, a GitHub blob URL, or `owner/repo[:path]` (for example `posit-dev/shinychat:pkg-py/CHANGELOG.md`). GitHub sources go through `gh`.
- With no `--version`, the script reads the unreleased section (`## [Unreleased]`, or `# shiny (development version)` in R). Pass `--version 1.8.0` for a named release.
- It lists the bullets under "New features" and "API additions". Add `--include-improvements` when the user asks for improvements too, or `--section <text>` for a custom heading.
- An R development section often has no subsections. The script then lists every bullet that does not start with "Fixed". Keep only new, user-facing features from that list.
- If the release has no features, say so and offer the latest release that has them. Never pad the reel with bug fixes.

Keep a reel to six features at most. With more, rank them by how much they help a typical app author and offer a second reel for the rest. For each feature, read its pull request (from `references` in the JSON) before writing anything; the changelog line alone is not enough to describe a behavior.

## Choose a segment type per feature

Each feature gets one segment directory beside the reel: `generated/<reel>/<NN-feature-slug>/`.

| The feature… | Segment | What it shows |
| --- | --- | --- |
| changes something you can see or click | **Demo** | A recorded mini-app, built with the normal demo workflow |
| is an API, testing, server, performance, or tooling change | **Explainer** | 1–4 animated scenes that show the idea: a flow diagram, a before/after, a code diff, a bar comparison, or a custom animation |

Prefer a demo whenever the feature has a visible effect: a real Shiny recording is the strongest proof. Use an explainer when a demo would be staged or empty. Even then, show the concept, not a list: a flow, a diff, or a comparison explains a change better than bullet points. The user does not need code on screen: show code only when the code is the point.

### Demo segments

Follow the normal app, recording, and narration rules, with these reel changes:

- Aim for 15–25 seconds. The batch narration phase warns when a segment's narration runs past 25 s, before you record; the reel warns past 30 seconds.
- Two meaningful actions are often enough to show one feature; the validator still asks for three, so make the third a natural follow-up (reverse, repeat, or contrast).
- The `code` action is optional. Use it only when the code is the point of the feature.
- Install the release or the unreleased build into a throwaway environment, as in [changeset-sourcing.md](changeset-sourcing.md), and confirm the feature exists in the installed build.
- Every demo segment needs both orientations: record the reel's orientation as the primary, then run `companion.py` for the other one.
- Put `logo_seconds: 0` at the top of the segment's `actions.yaml`. The reel shows the Shiny logo only in its first 5 seconds, on the intro card, so segments record without it. `stitch_reel.py` warns about a segment recorded with the logo.

### Explainer segments

Create `explainer.yaml` and `artifacts/narration.txt` (no app, no `actions.yaml`). An explainer keeps the eyebrow and title fixed (top in vertical, left column in horizontal) and plays 1–4 scenes in the rest of the band. Each scene starts on a narration sentence and replaces the one before it:

```yaml
title: Reconnect without losing state   # defaults to the feature title in reel.yaml
scenes:
  - type: flow
    nodes:                               # 2-4 boxes, lit in order
      - {label: Browser tab, caption: User fills in a form, sentence: 1}
      - {label: Connection drops, caption: Wi-Fi blip, sentence: 2}
      - {label: "`allow_reconnect()`", caption: Same session picks up, sentence: 3}
  - type: code
    sentence: 4                          # this scene starts when sentence 4 starts
    caption: One line in your server function.
    code: |
      def server(input, output, session):
      -     pass
      +     session.allow_reconnect(True)
    highlight: [3]
```

Pick the scene that matches the shape of the idea:

| Scene | Use it for | Keys |
| --- | --- | --- |
| `flow` | A sequence or a data path: browser → server → output, a request lifecycle, a reactive chain | `nodes`: 2–4 of `label` (or a plain string), optional `caption` and `sentence` |
| `compare` | Old way versus new way, in words or code | `before` and `after`, each with `label` and either `lines` (1–4) or `code`; `after_sentence` |
| `code` | An API change you can read in a few lines | `code` (12 lines of 64 characters at most); a leading `+ ` or `- ` marks an added or removed line; `change_sentence` swaps them; `highlight` (line numbers) and `highlight_sentence` |
| `bars` | A measured number: time, size, lines of code | `items`: 2–4 of `label`, `value` (positive), `text` (the label shown, like `60 ms`), optional `sentence`; the last bar takes the accent |
| `bullets` | Short benefit points, when nothing above fits | `points`: 1–4 of `text` (or a plain string) with optional `sentence`; optional one-line `code` and `code_sentence` |
| `html` | A custom animation none of the above can show | `file`: an HTML fragment in the segment directory |

Every scene also takes `sentence` (when it starts), and an optional `caption` with `caption_sentence`. Wrap names in backticks (`` `allow_reconnect()` ``) to show them as inline code. Use real numbers only in `bars`: take them from the pull request or a measurement, and say where they come from in the caption.

Timing rules:

- Points, nodes, and bars without `sentence` are spread across their scene. A beat cued to a sentence outside its own scene is an error; move the cue or the next scene's start.
- Scenes start in order, at least 2 s apart. Two or three scenes are usually enough for a 15–25 s segment; give each one at least a full sentence.
- An explainer without `scenes:` is read as one `bullets` scene from top-level `points`, `code`, and `code_sentence`, the original format.

Text that is too wide or too tall shrinks to fit the band in both orientations, but a scene that needs to shrink is usually carrying too much. Keep labels to 2–5 words and captions to one line.

#### Custom `html` scenes

Write a custom scene when the concept has its own shape, for example a dropped connection that reconnects, or an output that updates while its neighbors stay put. The file is an HTML fragment (a `<style>` block and markup, optionally a `<script>`) that fills the scene area. The renderer draws every frame by seeking the page's animations, so:

- Animate only with CSS animations or the Web Animations API. Timers, `requestAnimationFrame`, transitions, video, and network requests do not render.
- Time each animation with `animation-delay`: `var(--in)` is the scene's start, and `var(--s1)`, `var(--s2)`, … are narration sentence starts, all in clip time. Use `animation-fill-mode: both` so elements wait hidden before their delay.
- Use `var(--accent)` and `var(--on-accent)` (the readable text color on the accent), the Shiny preset palette, `#FFFFFF` text on the dark background, and the `Open Sans` and `Source Code Pro` fonts. Keep every element inside the scene area.
- Preview a few frames before rendering the whole reel, and look at both orientations.

Run the batch narration phase on explainer directories exactly as on demo directories; it generates `narration.wav` and `narration-timing.json`. Write `explainer.yaml` after the timing exists, so each cue points at the sentence that says it. The finish phase skips explainers, because `stitch_reel.py` renders and merges them.

## Blog post walkthroughs

A video about a blog post uses the same reel: one segment per idea or feature in the post (six at most), each a demo or an explainer as above. Set `eyebrow` in `reel.yaml` (for example `From the Shiny blog`) to replace the release label, and leave `release` out. Read the whole post and its linked pull requests before writing; narrate what the post shows, not its headings. Put the post's URL in the outro's `why` line if the user wants it, never in the narration.

## Narration

Each segment carries its own narration, 35–65 words (about 15–25 seconds). Write it with the `simple-english` rules and the speech-texture pass from the main skill. Focus on why the feature helps:

1. The situation or pain the user had before (one sentence).
2. What the feature does now, matched to what is on screen.
3. What that saves you, as one concrete fact (“you don't need the CSS anymore”), not a pitch.

Talk like a developer walking a teammate through the release, not a launch announcement: no hype words, no “exciting new”, no exclamation marks, and no “try it today” at the end. The outro card carries the install command.

Name the function or argument once, the way the changelog does. Do not say "in this release" unless the release notes confirm the version. For the unreleased section, say "coming soon" or "in the next release", never a version number. Do not read the card's title aloud as the first words; the card already shows it, so open on the problem.

## Assemble the reel

Write `generated/<reel>/reel.yaml`:

```yaml
title: What's new in Shiny for Python
release: "1.8.0"                # "Unreleased" shows "Coming in the next release"
orientation: vertical
outro:
  title: Try it today
  command: pip install -U shiny  # for unreleased: the install-from-GitHub command
features:
  - title: Reconnect without losing state   # 2-5 words, shown on the card
    why: Users keep their inputs after a network blip.   # one line, 4-10 words
    dir: 01-allow-reconnect
  - title: Headless server tests
    why: Check reactive logic in milliseconds.
    dir: 02-test-server
```

Then render and stitch:

```bash
python .agents/skills/shiny-component-shorts/scripts/stitch_reel.py \
  --reel-dir generated/reel-py-shiny-1-8
```

The script builds the reel twice: `reel.mp4` in the reel's orientation and `reel-<orientation>.mp4` in the other one (pass `--orientation` to build one). For each, it renders explainer segments, then an intro card listing every feature, one feature card per segment, and the outro card. It joins them with a slide into each card and a circle-open into each feature. It writes `artifacts/reel.mp4`, `artifacts/reel.json` with chapter start times (paste them into a video description as chapters), and `artifacts/reel-review.png` with one frame per chapter. It also writes `artifacts/reel-thumbnail.jpg` (and `reel-thumbnail-<orientation>.jpg`) from the intro card. Rendered cards, explainer clips, and normalized clips are cached in `artifacts/.reel-cache/` by a hash of their inputs, so a rebuild after a small change only renders what changed; delete that folder to force a full rebuild. Cards use the Open Sans and Source Code Pro files bundled in `assets/fonts/`, so a reel looks the same on every machine. Inspect that sheet before you report the reel done, and report every warning the script prints.

Optional `reel.yaml` keys: `eyebrow` (replaces the release label), `intro_seconds` (5.4, at least 5 so the logo can fade out on the intro card), `card_seconds` (2.6), `outro.seconds` (3.2), `outro.why`, and a per-feature `accent` from the Shiny palette. Cards are silent; the feature title and the "why" line carry the transition.
