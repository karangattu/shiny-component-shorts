# AGENTS.md

## Project purpose

This repo generates short Shiny component demo apps and 30-second video concepts.

## Defaults

- Prefer official Shiny documentation as the source of truth.
- Prefer Python Shiny Express for short demos unless the user asks for R.
- Demo targets are Shiny for Python, R Shiny, shinychat, and posit-dev/shinyreact (React UI with a Python or R server); a chat demo never calls a real LLM.
- A pull request, commit URL, or commit SHA is a valid request: demo one user-facing change from it.
- Keep demo apps small enough to understand in one screen.
- Every video idea must focus on one hidden behavior, not a full component tutorial.
- For standalone component recordings, reserve the top 20% and bottom 20% of each video frame for branding; fill the middle band's horizontal space with the app.
- Do not add a Shiny wordmark to videos by default. Branding can be added in later editing; add a logo only on explicit request.
- Use only the official Shiny preset palette, with accessible light- or dark-mode text colors.
- Write every voiceover script with the `simple-english` skill for meaning-level clarity (one thought per sentence, active voice, one name per thing, no hedges or filler), keeping contractions so it sounds spoken; sentence rhythm and texture come from the speech-texture pass.
- Narration sounds like a developer explaining something to a coworker, never like an ad: no hype words, pitch questions, exclamation marks, or calls to action.
- Never include laughing, giggling, chuckling, or other non-speech vocalizations in narration.
- Every generated video ships in both orientations (vertical and horizontal) from the same actions and narration; build apps that fill the frame in both.
- In horizontal videos, show code beside the live app rather than over it.
- Use the `shiny-component-shorts` skill when creating component video ideas or mini-apps.

Release, changelog, and blog requests default to one detailed editorial video per point, with real evidence, hard cuts, about 5% margins, and no feature-card interstitials. Combine points only when explicitly requested. Use `style: editorial` and `stitch_reel.py --separate`.

Use bslib Shiny typography (Open Sans and Source Code Pro) and palette for added graphics and new demos. All displayed code uses GitHub light/dark syntax highlighting. Preserve native captured app styles.
