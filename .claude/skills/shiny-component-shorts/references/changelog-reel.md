# Changelog reel

A changelog reel walks through the new features of one release, one after another. An animated feature card ("02 of 04", the feature title, and one line on why it helps) comes before each feature, so the viewer always knows a new feature is starting. The reel informs. It does not chase one hidden trick.

## Pick the release and the features

```bash
python .claude/skills/shiny-component-shorts/scripts/changelog_features.py \
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
| is an API, testing, server, or tooling change | **Explainer** | An animated card: title, 1–4 benefit points, an optional one-line code snippet |

Prefer a demo whenever the feature has a visible effect. Use an explainer when a demo would be staged or empty. The user does not need code on screen: show code only when one line explains the feature better than words.

### Demo segments

Follow the normal app, recording, and narration rules, with these reel changes:

- Aim for 15–25 seconds. The reel warns past 30 seconds.
- Two meaningful actions are often enough to show one feature; the validator still asks for three, so make the third a natural follow-up (reverse, repeat, or contrast).
- The `code` action is optional. Use it only when the code is the point of the feature.
- Install the release or the unreleased build into a throwaway environment, as in [changeset-sourcing.md](changeset-sourcing.md), and confirm the feature exists in the installed build.
- Every segment keeps the reel's orientation.
- Put `logo_seconds: 0` at the top of the segment's `actions.yaml`. The reel shows the Shiny logo only in its first 5 seconds, on the intro card, so segments record without it. `stitch_reel.py` warns about a segment recorded with the logo.

### Explainer segments

Create `explainer.yaml` and `artifacts/narration.txt` (no app, no `actions.yaml`):

```yaml
title: Headless server tests          # defaults to the feature title in reel.yaml
points:                               # 1-4 short benefit lines, 3-7 words each
  - text: Test reactive logic without a browser
    sentence: 2                       # reveal when narration sentence 2 starts
  - text: Runs in memory, in milliseconds
    sentence: 3
code: "with test_server(app) as session: ..."   # optional, one line
code_sentence: 4                      # optional reveal time for the code
```

Points without `sentence` are spread evenly across the narration. Run the batch narration phase on explainer directories exactly as on demo directories; it generates `narration.wav` and `narration-timing.json`. The finish phase skips explainers, because `stitch_reel.py` renders and merges them.

## Narration

Each segment carries its own narration, 35–65 words (about 15–25 seconds). Write it with the `simple-english` rules and the speech-texture pass from the main skill. Focus on why the feature helps:

1. The situation or pain the user had before (one sentence).
2. What the feature does now, matched to what is on screen.
3. The benefit to the user's app or workflow.

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
python .claude/skills/shiny-component-shorts/scripts/stitch_reel.py \
  --reel-dir generated/reel-py-shiny-1-8
```

The script renders explainer segments, then an intro card listing every feature, one feature card per segment, and the outro card. It joins them with a slide into each card and a circle-open into each feature. It writes `artifacts/reel.mp4`, `artifacts/reel.json` with chapter start times (paste them into a video description as chapters), and `artifacts/reel-review.png` with one frame per chapter. Inspect that sheet before you report the reel done, and report every warning the script prints.

Optional `reel.yaml` keys: `intro_seconds` (5.4, at least 5 so the logo can fade out on the intro card), `card_seconds` (2.6), `outro.seconds` (3.2), `outro.why`, and a per-feature `accent` from the Shiny palette. Cards are silent; the feature title and the "why" line carry the transition.
