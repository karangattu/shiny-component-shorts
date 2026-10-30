# Release and blog videos

For the complete source capture → stills → narration → render → validation sequence, follow [editorial-production.md](editorial-production.md).

Follow [visual style](visual-style.md) for all added labels and code excerpts: bslib Shiny fonts and palette, with GitHub light/dark syntax highlighting.

## Default: one detailed editorial video per point

New release, changelog, and blog requests produce a series: one independent
video per selected feature or teachable idea. Each has its own title, opening
context, complete explanation, proof, narration, and both orientations. Closely
related bullets may share a video when they describe one workflow. Do not
squeeze unrelated points into a shared running time.

Start around 60–120 seconds per point and allow more time when the example
needs it. This is a starting range, not a cap or a padding target. Show the
situation, what changes, how to use it, the decisive code or action, and its
actual result. Include a meaningful caveat or edge case when relevant. Let
viewers read code and follow the demonstration before moving on. No 15–25 s
segment limit or fixed 95–130-word quota applies. The voice generators use
`--editorial` automatically through batch processing; direct generator calls
need that flag. Spoken text must still be non-empty and pass the normal
transcript/voice checks. Pauses are purposeful rather than a tag quota.

Write a fresh script for each expanded explanation. Cutting an existing
22-second overview into smaller files or lengthening its holds does not add
detail. Keep each point understandable on its own and link its sources.

### Vary the series

Viewers watch these videos back to back, so a shape that is fine once reads as
a template by the third video. Before narration, lay the series' scripts side
by side and check:

- No two videos open the same way. Rotate the opening move: the problem in the
  running app, the surprising result first, the decisive code first, or what
  you expected to happen and did not.
- No two videos end the same way. A closing caveat is one option, not the
  default; others are the result on screen, the code that caused it, or one
  plain fact about when it applies.
- No transition phrase repeats across videos. "Here's why", "Here's the app",
  "One thing to know", and "One condition" each appear in at most one script of
  the series, and the series as a whole leans on none of them.
- Chapter labels name the specific thing on screen ("All three ready after one
  second"), not a slot in the template. "The result" or "Why it works" in every
  video is a template showing through. Titles vary in form too; a series where
  every title is a tidy claim sentence looks generated.
- Pause tags follow the thought, not the paragraph. A `[pause 1s]` after every
  paragraph is a metronome; let one stretch run long and cut another short.

Run `scripts/check_narration_voice.py --series <series-dir>` after writing the
scripts; it reports openers, closers, and phrases shared across the sibling
`narration.txt` files, alongside each script's own warnings.

Use `style: editorial` in the series configuration. Ground each
claim in real app footage, a source excerpt or figure, captured output, or a
measured result. Use a concise evidence-based diagram or timeline when it clarifies behavior that is hard to see directly; distinguish it from a real recording and derive its events from verified runs or authoritative sources. No generated decorative artwork, fake editor/browser
windows, simulated typing, invented results, or illustrative objects added for
motion. Prefer real recordings where an app interaction or changing state demonstrates the point, with actions timed to the narration. Preserve the native appearance of captured apps and documents. Use stills for readable code or evidence and whenever motion adds no understanding. Avoid repeated source labels and explanatory footers; keep provenance in the production index and retain only essential on-screen attribution or qualifications. Optional accurate narration captions must not obscure evidence.

Open on useful content. The renderer adds a small title over the first shot
and no wordmark by default. It uses hard
cuts and brief annotation fades; no feature-card interstitials or mandatory
intro/outro. Use one consistent overlay typeface and Shiny blue for emphasis.
Compose media with about 5% safe margins. Reserve space only for the title, essential labels, or optional captions actually present. Let evidence fill the remaining frame. Framing is
specific to each orientation; never shrink a complete landscape desktop into
an unreadable portrait frame.

Each feature directory has `editorial.yaml`, clean media in `sources/`, and
`artifacts/narration.wav` plus its current `narration-timing.json`. Create or
import narration with the normal batch narration phase; it discovers editorial
segments. Do not use the component `finish` phase for editorial segments.

```yaml
# reel.yaml
style: editorial
orientation: vertical
title: Shiny for Python feature walkthroughs
release: "1.8.0"  # omit for a blog; identify the post in the production index
features:
  - title: Test without a browser
    dir: 01-server-tests
  - title: Bring your own HTML
    dir: 02-own-html
```

```yaml
# 01-server-tests/editorial.yaml
shots:
  - cue: Testing reactive server logic
    views:
      vertical: {file: sources/release-vertical.png, fit: contain}
      horizontal: {file: sources/release-horizontal.png, fit: contain}
  - cue: Now your test runs in memory
    views:
      vertical:
        file: sources/test-vertical.png
        fit: contain
        highlight: [0.08, 0.42, 0.84, 0.05]
      horizontal: {file: sources/test-horizontal.png, fit: contain}
```

Every shot needs an explicit `vertical` and `horizontal` view with `file` and
`fit: contain|cover`. Reusing the same file is allowed only with deliberate
framing. Optional `crop: [x, y, width, height]` uses normalized source
coordinates before fitting; `highlight` uses normalized final-frame coordinates
and draws one static outline. A video view can set `in` in seconds; playback
stays at original speed and its embedded audio is replaced by the narration.
Provide enough footage for the whole shot, including the final hold.

Cues quote actual spoken words; a repeated phrase uses
`cue: {phrase: "the result", occurrence: 2}`. The first shot matches the
opening words and begins at frame zero. Later cuts land on the first video
frame at or after their phrase plus the shared 0.15-second narration offset.
They must be strictly ordered, without overlapping frames. Each shot lasts
until the next; the final shot lasts until one second after narration ends,
rounded up to a frame. The renderer rejects absent media, stale timing,
invalid framing, bad cues, and insufficient footage before encoding. Still
shots need no artificial action quota or activity timer.

Render the series with
`scripts/stitch_reel.py --reel-dir <series> --separate` using the project's
explicit Python environment. Each point writes its own `reel.mp4`, companion
orientation, timing JSON, source-labelled review sheets, and thumbnails into
`artifacts/series/<number>-<point-title>/`. The `artifacts/series.json` manifest
indexes all delivered videos. Each video starts at time zero with its own
title without a wordmark; other points' narration is not included. An optional
`--orientation vertical|horizontal` renders only that view. Series can contain
more than six selected points; the combined-reel feature cap does not apply. Style, media bytes, narration, framing, fonts, and
renderer code participate in caching. Keep originals separate from edits.

Review both phone-size sheets and transition frames. Fully decode both MP4s;
verify their dimensions, 30 fps, audio presence, chapter boundaries, and phrase
timing. Listen at normal speed when possible; state separately when listening
was unavailable. Keep the script conversational and show only what its sources
support. New narration uses the existing local voice workflow; no paid service,
background music, or presenter footage is required.

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

For a series, inventory every selected distinct capability and order the videos by usefulness; there is no six-point series cap. A post's breaking changes and deprecations are user-facing too, and often the most useful video for someone about to upgrade: give them one combined video when the post has a section for them, and prove each one with a real run that fails on the previous release and passes after the documented edit (a test suite, a selector, a column name). Describe a change that cannot be shown this way, such as a telemetry span shape, in one plain sentence over its source, and skip a deprecation that has no visible effect. The "never pad with bug fixes" rule still applies to the fixes list. Read each point's pull request (from `references` in the JSON) before writing anything; the changelog line alone is not enough to explain behavior. For a combined overview explicitly requested by the user, choose at most six features and keep the pacing concise.

## Optional combined overview

Only assemble multiple points into one video when the user asks for an
overview or compilation. Omit `--separate` to retain the combined editorial
renderer. Overview segments can be brief, but do not shorten the standalone
series to fit that optional overview. Existing combined exports are preserved
when rendering the separate series.

An overview is one connected explanation, not the changelog read aloud. Open
on the change that matters most to someone with an existing app, said the way a
developer would say why it happened ("Most of 1.9 is about what happens while
an app is waiting on something"). Group the points that share that idea as its
consequences, in the order a person would discover them, with a connecting
clause rather than "And" between them. When the remaining points share nothing
with it, say so plainly ("Two things in this release aren't about waiting at
all") instead of inventing a theme that covers everything; a forced through-line
reads as generated as a list does. One sentence per feature, each carrying a
number, is a list; the ear hears it as release notes. Title the overview by its
subject and release ("Shiny 1.9", "Concurrent async in Shiny 1.9"), never by
its length or a count ("in 40 seconds", "4 things").

## Legacy reels

The remaining scene/card options describe existing reels without `style`, or
an explicit `style: legacy`. Keep them reproducible. Do not use these animated
explainer defaults for new release or blog videos.

## Choose a legacy segment type per feature

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
- Record segments without a logo. Only use `logo_seconds` to add one when the user explicitly requests it.

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

## Legacy blog post walkthroughs

A video about a blog post uses the same reel: one segment per idea or feature in the post (six at most), each a demo or an explainer as above. Set `eyebrow` in `reel.yaml` (for example `From the Shiny blog`) to replace the release label, and leave `release` out. Read the whole post and its linked pull requests before writing; narrate what the post shows, not its headings. Put the post's URL in the outro's `why` line if the user wants it, never in the narration.

## Legacy combined-reel narration

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

Optional `reel.yaml` keys: `eyebrow` (replaces the release label), `intro_seconds` (5.4; must cover any explicitly requested `logo_seconds`), `card_seconds` (2.6), `outro.seconds` (3.2), `outro.why`, and a per-feature `accent` from the Shiny palette. Cards are silent; the feature title and the "why" line carry the transition.
