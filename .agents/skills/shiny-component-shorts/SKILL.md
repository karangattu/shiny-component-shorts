---
name: Shiny Component Shorts
description: Create tiny Shiny Python or R mini-apps and 30-second "Did you know?" video concepts for Shiny components. Use when the user provides a Shiny component, component docs URL, or asks for a short video/demo around a Shiny UI feature.
---

# Shiny Component Micro-App Video Factory

## Mission

Create tiny Shiny mini-apps and 30-second video concepts for individual Shiny components.

The goal is not to explain the whole component. The goal is to find the one surprising behavior, hidden option, or overlooked interaction that makes the component worth showing in a short video.

Each output should feel like:

> "Wait, that component can do that?"

## Inputs to accept

The user may provide:

- A Shiny component name
- A Shiny docs URL
- A language: Python, R, or both
- A target audience
- A desired number of video ideas
- Whether they want storyboard only, code only, or both

If the user gives no language, default to Python Shiny Express for short demos unless the component is only available or clearer in R.

## Core rule

One video = one trick.

Do not create a full tutorial. Do not list every parameter. Pick one visual behavior that can be demonstrated in under 30 seconds.

Good tricks include:

- A component that looks decorative but behaves reactively
- A compact UI feature that replaces a messier layout
- A component that stores user state
- A component that prevents a common app bug
- A component that can be updated from the server
- A tiny parameter that changes the whole user experience

## Research process

For each component:

1. Inspect the official Shiny docs URL if provided.
2. Identify:
   - The function name
   - The basic purpose
   - The most visual variation
   - Any update function
   - Any reactive value exposed to the server
   - Any surprising layout behavior
3. Ignore anything that cannot be shown clearly on screen.
4. Choose the strongest "I didn't know Shiny could do that" feature.
5. Build a tiny app around that feature.

## Output format

For every component, produce:

### Component

Name and language.

### Best video angle

One sentence describing the hidden feature.

### Hook

A short opening line for the video.

### Mini-app concept

A tiny app idea that makes the feature obvious.

### Variations

Provide 3 to 5 variations:

| Variation | What changes | Why it is video-worthy |
|---|---|---|

### 30-second storyboard

| Time | Visual | Narration |
|---:|---|---|
| 0-3 sec | Show the boring/default pattern | Short pain-point line |
| 3-8 sec | Reveal the feature | "Did you know..." line |
| 8-20 sec | Interact with the mini-app | Show the feature changing state |
| 20-27 sec | Highlight the key code line | Explain only the important line |
| 27-30 sec | End on result | Memorable takeaway |

### Code

Generate a runnable Shiny mini-app.

For Python:
- Prefer Shiny Express for short demos.
- Use Shiny Core only when the layout needs clearer structure.
- Keep dependencies minimal.

For R:
- Use shiny and bslib.
- Add packages only when needed.
- Keep the app small enough to understand from one screen.

### Recording notes

Include:

- What to click
- What changes on screen
- Where to zoom
- Which line of code to highlight
- What the final visual should look like

## Style rules

Use a recurring "Did you know?" framing, but avoid generic titles.

Bad:
- "Did you know Shiny has tooltips?"

Good:
- "Did you know a tooltip can trigger server logic?"
- "Did you know a table can become an input?"
- "Did you know a notification can update itself instead of stacking?"

## Quality checks

Before finalizing, verify:

1. The idea is visually understandable in 30 seconds.
2. It is specific to this component.
3. There is one code line worth zooming into.
4. It reveals behavior, not just appearance.
5. A Shiny user would say, "Oh, I could use that."

## Avoid

- Full component tutorials
- Long parameter tours
- Apps that require too much data setup
- Purely cosmetic changes unless the visual result is dramatic
- Multiple tricks in one video
- Abstract reactivity explanations without visible interaction
