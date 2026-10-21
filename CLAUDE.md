# CLAUDE.md

This repo creates short Shiny component demo apps and 30-second video concepts.

When asked for Shiny component demos, use the `/shiny-component-shorts` skill.

Defaults:
- Prefer official Shiny documentation.
- Prefer Python Shiny Express unless the user asks for R.
- Demo targets are Shiny for Python, R Shiny, shinychat, and posit-dev/shinyreact (React UI with a Python or R server); a chat demo never calls a real LLM.
- A pull request, commit URL, or commit SHA is a valid request: demo one user-facing change from it.
- Keep apps tiny, visual, and recordable.
- For standalone component recordings, reserve the top 20% and bottom 20% of the frame for branding and fill the middle band's horizontal space.
- Every recording shows the Shiny wordmark in the top-left for its first 5 seconds, then fades it out, sized to read on a phone; the recorder adds it, so never put a logo in the app.
- Use only the official Shiny preset palette with accessible light- or dark-mode text.
- Write every voiceover script with the `simple-english` skill for meaning-level clarity (one thought per sentence, active voice, one name per thing, no hedges or filler), keeping contractions so it sounds spoken; sentence rhythm and texture come from the speech-texture pass.
- Narration sounds like a developer explaining something to a coworker, never like an ad: no hype words, pitch questions, exclamation marks, or calls to action.
- Do not include laughing, giggling, chuckling, or other non-speech narration sounds.
- Every generated video ships in both orientations (vertical and horizontal) from the same actions and narration; build apps that fill the frame in both.
- In horizontal videos, show code beside the live app rather than over it.

Release, changelog, and blog requests default to one detailed editorial video per point, with real evidence, hard cuts, about 5% margins, and no feature-card interstitials. Combine points only when explicitly requested. Use `style: editorial` and `stitch_reel.py --separate`.

Use bslib Shiny typography (Open Sans and Source Code Pro) and palette for added graphics and new demos. All displayed code uses GitHub light/dark syntax highlighting. Preserve native captured app styles.
