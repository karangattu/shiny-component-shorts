# Shiny Component Shorts

Make short videos about [Shiny](https://shiny.posit.co) features. Component shorts focus on a single behavior. Release and blog videos explain one feature in detail, usually in 60 to 120 seconds.

This repo is an agent skill for Claude Code, Codex, Google Antigravity, and OpenCode. Describe the video you want, and the agent builds a small Shiny app, records the browser, adds narration, and validates the output.

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

Make sure `ffmpeg` and `ffprobe` are on your `PATH`.

Narration is optional. Gemini voice generation requires `pip install google-genai` and a `GEMINI_API_KEY` environment variable. Never commit the key.

## Make a video

Open the repo in your agent and ask:

```text
/shiny-component-shorts Create a video about Shiny's date range picker in Python.
```

Output is written to `generated/<demo-name>/` (ignored by git). The finished files land in `artifacts/`:

| Video | Narrated | Silent |
| --- | --- | --- |
| Vertical 9:16 | `final_with_audio.mp4` | `demo.mp4` |
| Horizontal 16:9 | `final_with_audio-horizontal.mp4` | `demo-horizontal.mp4` |

Each run also generates cover images (`thumbnail.jpg` and `thumbnail-horizontal.jpg`).

Both orientations share the same action script and narration, keeping voice cues and clicks synchronized. The skill generates both formats by default unless you request only one.

In OpenCode, start with `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 opencode` to prevent loading duplicate skills.

### What you can ask for

| Goal | Example prompt |
| --- | --- |
| Ideas only | `Give me 5 video ideas for Shiny's data grid.` |
| A runnable app | `Create a runnable mini-app for toolbar-select in Python.` |
| A finished video | `Make a narrated video about bslib value boxes in R.` |
| An existing app | `Make a video about the best behavior in ~/apps/sales-dashboard.` The agent does not modify your app. |
| A pull request or commit | `Make a video about https://github.com/posit-dev/py-shiny/pull/2051` |
| A changelog reel | `Make a changelog reel of the unreleased features in https://github.com/posit-dev/py-shiny/blob/main/CHANGELOG.md` |
| A series | `Make 3 videos about Shiny's data grid.` The limit is 5 per component. |

The skill supports Shiny for Python, R Shiny, [shinychat](https://github.com/posit-dev/shinychat), and [shinyreact](https://github.com/posit-dev/shinyreact). Chat demos use simulated responses and do not call external LLM APIs.

For pull requests and commits in `rstudio/shiny`, `posit-dev/py-shiny`, `posit-dev/shinychat`, or `posit-dev/shinyreact`, the agent checks out that build and demonstrates one visible change.

For changelogs and blog posts, the pipeline creates an editorial video for each feature. Set `style: editorial` in `reel.yaml` and run `stitch_reel.py --reel-dir <directory> --separate`. Outputs include vertical and horizontal videos, thumbnails, chapter markers, and review sheets in `artifacts/series/`.

## Narration

- Local voice: uses the cloned voice `karan` by default. See the [TTS reference](.agents/skills/shiny-component-shorts/references/tts-and-costs.md#use-local-voice-cloning) for setup.
- Gemini: generates audio using the Gemini API when a key is present.
- Existing audio: pass a WAV file or video to reuse an existing recording.
- Silent: times actions against the script without synthesizing speech.

The agent aligns browser interactions to spoken word timestamps and validates transcripts to flag dropped words.

## Visual style

Demos and labels use the [bslib Shiny preset](https://rstudio.github.io/bslib/) (Open Sans, Source Code Pro, and Shiny blue) and GitHub syntax themes for code.

Component recordings follow these layout rules:

- The app occupies the middle 60% of the frame in both orientations.
- Portrait orientation switches to full-frame code cards. Landscape displays code beside the app.
- The Shiny logo appears in the top-left for the first 5 seconds, then fades out.
- Recordings include at least three inputs or clicks with visible updates.
- A syntax-highlighted code card shows exact source with the primary line highlighted, filename, and line numbers.
- Colors stay within the official Shiny palette.

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

- **Missing selectors in preflight**: update the selector in `actions.yaml` to match the current app markup.
- **Shiny Client Errors panel appears**: the app raised an unhandled client error. Fix the app before recording.
- **Horizontal version looks cramped or empty**: use fluid widths and center the layout so the app fits both dimensions.
- **App fails to start**: check the printed terminal output for missing dependencies.
- **`ffmpeg` not found**: install `ffmpeg` and ensure both `ffmpeg` and `ffprobe` are in `PATH`.
- **Port in use**: the recorder assigns an open port automatically.

## Cost

Each run generates a cost summary. Gemini token usage is recorded in `artifacts/narration.usage.json`. Cloned local voice, supplied audio, and silent runs cost $0 in API fees.

## Paparazzi capture for R Shiny

To capture R Shiny apps using [Paparazzi](https://posit-dev.github.io/paparazzi/), set `capture: paparazzi` in `actions.yaml`. Install the R dependencies in a dedicated library and set `R_LIBS_USER` for recording commands. See the [recording contract](.agents/skills/shiny-component-shorts/references/recording-contract.md#paparazzi-capture-for-r-shiny) for details and browser verification tests.

## Editorial production

For release and blog videos, use the [editorial starter](.agents/skills/shiny-component-shorts/assets/editorial-starter/) and follow the [production workflow](.agents/skills/shiny-component-shorts/references/editorial-production.md). The tooling includes `prepare_editorial.py` to format captures and code excerpts, `stitch_reel.py` to assemble videos with chapter markers, and `validate_editorial.py` to verify output files.

## Versioned releases

[GitHub releases](https://github.com/karangattu/shiny-component-shorts/releases) provide packaged skill archives with checksums. The bootstrap script (`bootstrap_skill.py --project-dir <production>`) downloads and pins verified skill releases into `.video-skill/` using `skill-lock.json`. See [version management](.agents/skills/shiny-component-shorts/references/version-management.md).

Maintainers publish releases by tagging a commit with `vMAJOR.MINOR.PATCH`. GitHub Actions tests the build, packages tracked files, and attaches release assets.

## Component production checks

The [component production guide](.agents/skills/shiny-component-shorts/references/component-production.md) describes dry-run previews, source extraction, and validation checks. Previews test interactions and layout fit without generating audio or rendering full video.
