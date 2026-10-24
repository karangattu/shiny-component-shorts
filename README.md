# Shiny Component Shorts

Make short videos about [Shiny](https://shiny.posit.co) features. Component shorts show one useful behavior. Release and blog videos explain one point in detail, usually in 60–120 seconds.

This repo is an agent skill. You open it in an AI coding agent (Claude Code, Codex, Google Antigravity, or OpenCode), describe the video you want, and the agent does the rest: it writes a small Shiny app, records the browser, adds narration, and checks the result.

## Examples

https://github.com/user-attachments/assets/af6b0ec9-b78a-4f4b-a849-ad896d4500e6

https://github.com/user-attachments/assets/79519994-e8be-4450-91f2-549f5765c4fa

Made from a pull request, [posit-dev/shinychat#269](https://github.com/posit-dev/shinychat/pull/269):

https://github.com/user-attachments/assets/a3459a49-3647-4136-b171-1801008269f1

## Setup

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

You also need `ffmpeg` and `ffprobe` on your `PATH`.

Narration is optional. Gemini narration needs `pip install google-genai` and a `GEMINI_API_KEY` in your environment. Never commit the key.

## Make a video

Open the repo in your agent and ask:

```text
/shiny-component-shorts Create a video about Shiny's date range picker in Python.
```

Everything lands in `generated/<demo-name>/`, which git ignores. You get two finished videos in `artifacts/`:

| Video | Narrated | Silent |
| --- | --- | --- |
| Vertical 9:16, for phones | `final_with_audio.mp4` | `demo.mp4` |
| Horizontal 16:9 | `final_with_audio-horizontal.mp4` | `demo-horizontal.mp4` |

You also get a cover image for each one, `thumbnail.jpg` and `thumbnail-horizontal.jpg`, ready to upload.

Both videos come from one recording script and one narration track, so the voice lines up with the same clicks in each. Ask for a horizontal video and you get a vertical copy instead. If you only want one shape, say so.

In OpenCode, start with `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 opencode` so only one copy of the skill loads.

### What you can ask for

| Ask for | Example prompt |
| --- | --- |
| Ideas only | `Give me 5 video ideas for Shiny's data grid.` |
| A runnable app | `Create a runnable mini-app for toolbar-select in Python.` |
| A finished video | `Make a narrated video about bslib value boxes in R.` |
| An existing app | `Make a video about the best behavior in ~/apps/sales-dashboard.` The agent never edits your app. |
| A pull request or commit | `Make a video about https://github.com/posit-dev/py-shiny/pull/2051` |
| A changelog reel | `Make a changelog reel of the unreleased features in https://github.com/posit-dev/py-shiny/blob/main/CHANGELOG.md` |
| A series | `Make 3 videos about Shiny's data grid.` The limit is 5 per component. |

The skill covers Shiny for Python, R Shiny, [shinychat](https://github.com/posit-dev/shinychat), and [shinyreact](https://github.com/posit-dev/shinyreact). Chat demos use canned replies and never call a real LLM.

**Pull requests and commits** work for `rstudio/shiny`, `posit-dev/py-shiny`, `posit-dev/shinychat`, and `posit-dev/shinyreact`. The agent installs that exact build and demos one user-facing change. If the change has nothing to show on screen, it says so.

**Changelogs and blog posts** default to one independently understandable editorial video per feature or idea. Real app recordings, faithful code excerpts, source figures, and verified output support the narration, with hard cuts and reading time. Write `style: editorial` in `reel.yaml`, then run `stitch_reel.py --reel-dir <directory> --separate`. Each video gets both orientations, a thumbnail, chapter times, and a review sheet under `artifacts/series/`. The explanation sets the length. Combined reels remain available when explicitly requested; configurations without `style` retain their existing rendering behavior.

## Narration

- **Local voice** is the default for new videos and uses the saved voice `karan`. Setup is in the [TTS reference](.agents/skills/shiny-component-shorts/references/tts-and-costs.md#use-local-voice-cloning).
- **Gemini** narration needs an API key.
- **Your own audio**: point the agent at a WAV or a narrated video, and it uses that audio instead of generating new audio.
- **Silent**: the agent still writes a script to time the actions, but it generates no audio.

The agent measures when each word is spoken and times every click to the words that describe it. A transcript check catches dropped or garbled words without anyone having to listen.

## Visual style

New demos and added labels use the [bslib Shiny preset](https://rstudio.github.io/bslib/): Open Sans, Source Code Pro, and Shiny blue. All displayed code uses bundled GitHub light/dark syntax highlighting. Native captures keep their appearance.

Standalone component recordings use these composition rules:

- Vertical and horizontal versions of the same video. The app fills the middle 60% of the frame in both.
- In the horizontal version, the code card sits beside the app instead of below it.
- The Shiny logo sits in the top-left for the first 5 seconds, then fades out.
- At least three clicks or inputs, each with a visible change.
- A syntax-highlighted code card using GitHub colors. It shows real source context from the app with the key line highlighted.
- Only the official Shiny colors.

## Repository layout

```text
.claude/skills/shiny-component-shorts/   the skill for Claude Code
.agents/skills/shiny-component-shorts/   the skill for Codex, Antigravity, and OpenCode
  SKILL.md                               instructions the agent follows
  references/                            detailed rules for pacing, recording, and narration
  scripts/                               recorder, validator, narration, and reel tools
tests/                                   contract tests
presentation/                            a talk about this pipeline
generated/                               your videos (gitignored)
```

The two skill copies are edited together but are not identical, so don't copy one over the other.

## Troubleshooting

- **Missing selectors in the preflight**: the app or `actions.yaml` changed. Fix the selector instead of making it looser.
- **"Shiny Client Errors" panel on screen**: the recording fails. Fix the app and record again.
- **The horizontal version looks cramped or empty**: the app was styled for a phone screen. Give it fluid widths and center it so it fills both shapes.
- **The app won't start**: the error shows the app's own output. This is usually a missing package in the demo's environment.
- **`ffmpeg` not found**: install it and make sure `ffmpeg` and `ffprobe` are on your `PATH`.
- **Port already in use**: the recorder picks a free port by itself. Don't kill unknown processes to free one.

## Cost

Each run ends with a cost report. Gemini token usage is saved to `artifacts/narration.usage.json`. Local voice, your own audio, and silent videos cost $0 in TTS.

### Paparazzi recordings for R Shiny

Set `capture: paparazzi` in a demo's `actions.yaml` to record through
[Paparazzi](https://posit-dev.github.io/paparazzi/). Install its optional R
packages in a dedicated library and set `R_LIBS_USER` for recording commands.
The [recording contract](.agents/skills/shiny-component-shorts/references/recording-contract.md#paparazzi-capture-for-r-shiny)
includes setup and the real browser regression test.

Paparazzi captures the browser while the shared scripts drive actions, narration
cues, the Shiny wordmark, and code cards. The exported video clock is checked through
a WebVTT marker. Existing local voice generation, transcript alignment, cue
validation, audio merging, and both video orientations use the same workflow.
Projects without this setting keep the existing recording backend.

### Reproducible editorial production

For the evidence-led release and blog style, start from the bundled
[editorial starter](.agents/skills/shiny-component-shorts/assets/editorial-starter/)
and follow the [production workflow](.agents/skills/shiny-component-shorts/references/editorial-production.md).
`prepare_editorial.py` turns real captures and exact source excerpts into readable
GitHub-highlighted shots in both orientations. `stitch_reel.py` supports optional
exact-duration overviews and embedded phrase-aligned chapters.
`validate_editorial.py` checks the encoded files and rejects stale evidence.
Models still choose the story and verify the app; they no longer need custom
screenshot layout, padding, chapter, or export-validation scripts for each video.

## Versioned releases

[GitHub releases](https://github.com/karangattu/shiny-component-shorts/releases) provide
separate Codex and Claude skill archives and `SHA256SUMS`. Each archive includes
its `VERSION` and a `release.json` recording the tag and exact source commit.
Record these with a video's production inputs when you need to pin the workflow.

For maintainers, push a stable `vMAJOR.MINOR.PATCH` tag on a reviewed commit.
The release workflow runs the existing tests and type checks, packages only
tracked skill files, and publishes both archives with checksums. A matching
`.github/release-notes/<tag>.md` supplies curated notes; otherwise GitHub generates
them. Patch versions cover fixes; minor versions add capabilities.
