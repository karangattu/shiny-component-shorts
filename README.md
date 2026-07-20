# Shiny Component Shorts

A small repo for generating 30-second videos about Shiny components.

## Skill workflow at a glance

![Skill workflow at a glance](assets/process.jpg)

## How we ensure quality

![Quality gate loop](assets/quality_gate_loop.jpg)

## Example finished short

https://github.com/user-attachments/assets/71058600-9228-41d7-99f8-a410ae47c643

## What this repo does

This repo contains agent skills for creating:

* Short Shiny mini-apps
* 30-second video storyboards
* Narration scripts
* Recording notes
* Python or R examples

The focus is not full tutorials. Each video should reveal one useful, surprising behavior in a component.

You can also point the skill at an existing R Shiny or Shiny for Python app to find one fascinating behavior and create a video without modifying the original app.

## Setup

Install the Python dependencies and Playwright's Chromium browser:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Recording and validation also require `ffmpeg` and `ffprobe` on `PATH`.

## Using with Google Antigravity

Open the repository root as the workspace. Antigravity discovers the skill from `.agents/skills/shiny-component-shorts/SKILL.md`.

Then prompt Antigravity:

```text
Use the shiny-component-shorts skill to create a narrated vertical video about Shiny's date range selector in Python.
```

## Using with Claude Code

Run:

```text
/shiny-component-shorts toolbar-select in Python
```

Example:

```text
/shiny-component-shorts Create 5 did-you-know video ideas for Shiny data grid. Include runnable mini apps.
```

## Using with Codex

Run:

```text
Use $shiny-component-shorts to create 5 mini-app video ideas for Shiny toolbar-select in Python.
```

Requests for multiple videos use the dedicated series workflow. A series contains at most five videos about one component, and every video must demonstrate a distinct hidden behavior. The skill returns fewer ideas when the component does not have enough strong, visual behaviors.

For example:

```text
Use $shiny-component-shorts to create a multi-video series for Shiny data grid in Python. Create up to 5 videos, each focused on a distinct hidden behavior, and include a runnable mini-app for each one.
```

## Using with OpenCode

This repo includes the skill in both `.agents` and `.claude`. Disable Claude-compatible skill discovery when launching OpenCode so it loads the `.agents` copy without a duplicate name:

```bash
OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 opencode
```

Then prompt OpenCode:

```text
Use the shiny-component-shorts skill to create a multi-video series for Shiny data grid in Python. Create up to 5 videos, each focused on a distinct hidden behavior, and include a runnable mini-app for each one.
```

## Video format

Each idea should include:

* Hook
* Hidden feature
* Mini-app concept
* Variations
* 30-second storyboard
* Runnable code
* Recording notes

The skills require at least three meaningful interactions and three visible state changes per 30-second recording. Long idle waits and static code cards are rejected; the recording should reveal, contrast, and replay or reset the same hidden behavior.

Recorded shorts default to a true 9:16 composition with the app as the hero. `Problem → Reveal → Proof → Code → Payoff` organizes the storyboard and timing, but those planning labels are not shown in the video. The browser deliverable stays clean: no beat rail, numbered state chips, or planning labels over the app. The detailed pacing rules live in each skill's `references/short-form-pacing.md` file.

Every composition reserves the top 20% and bottom 20% for later branding while the app stretches across the available width in the middle band. Horizontal recordings present the live app and code side-by-side during the code beat. App UI, cursor effects, and code cards use the official Shiny preset palette, including Shiny blue `#007BC2`, accessible `#1D1F21` text on light surfaces, and `#FFFFFF` text on dark surfaces.

The shared Claude and Codex recorders use the same VS Code-style, syntax-highlighted code card. A code action can show dimmed real source context with `before` and `after`, keep honest gutter numbers with `start_line`, and animate only the decisive focused line.

Narration uses speech only. Laughing, giggling, chuckling, and other non-speech vocalizations are prohibited by the prompt contract and rejected by validation.

## Gemini 3.1 TTS

Install the official Gemini SDK and expose the key to the shell that launches Codex or Claude:

```bash
python3 -m pip install google-genai
export GEMINI_API_KEY="your-key"
```

When narration audio is requested, the skill writes `artifacts/narration.txt` and uses Gemini 3.1 Flash TTS Preview to create `artifacts/narration.wav`. You can also run it directly:

```bash
python3 .agents/skills/shiny-component-shorts/scripts/generate_tts.py \
  --input demo-name/artifacts/narration.txt \
  --output demo-name/artifacts/narration.wav \
  --usage-output demo-name/artifacts/narration.usage.json
```

Claude Code can use `.claude/skills/shiny-component-shorts/scripts/generate_tts.py`. `GOOGLE_API_KEY` is also supported; if both variables are set, the Google SDK gives `GOOGLE_API_KEY` precedence. Never commit either key.

The TTS script writes exact Gemini token usage and a paid-tier list-price estimate to `narration.usage.json`. At the end of every artifact-generating workflow, the skill also reports the active Claude Code or Codex usage when the harness exposes it. Subscription usage, unavailable usage, and list-price estimates are labeled separately so a partial estimate is never presented as a complete bill.
