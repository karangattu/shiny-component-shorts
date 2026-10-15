# CLAUDE.md

This repo creates short Shiny component demo apps and 30-second video concepts.

When asked for Shiny component demos, use the `/shiny-component-shorts` skill.

Defaults:
- Prefer official Shiny documentation.
- Prefer Python Shiny Express unless the user asks for R.
- Demo targets are Shiny for Python, R Shiny, shinychat, and posit-dev/shinyreact (React UI with a Python or R server); a chat demo never calls a real LLM.
- A pull request, commit URL, or commit SHA is a valid request: demo one user-facing change from it.
- One video = one feature. A changelog reel (the new features of the unreleased or a named release) is the exception: one segment per feature, separated by animated feature cards.
- Keep apps tiny, visual, and recordable.
- Reserve the top 20% and bottom 20% of the frame for branding and fill the middle band's horizontal space.
- Every recording shows the Shiny wordmark in the top-left for its first 5 seconds, then fades it out, sized to read on a phone; the recorder adds it, so never put a logo in the app.
- Use only the official Shiny preset palette with accessible light- or dark-mode text.
- Write every voiceover script with the `simple-english` skill for meaning-level clarity (one thought per sentence, active voice, one name per thing, no hedges or filler), keeping contractions so it sounds spoken; sentence rhythm and texture come from the speech-texture pass.
- Do not include laughing, giggling, chuckling, or other non-speech narration sounds.
- Every generated video ships in both orientations (vertical and horizontal) from the same actions and narration; build apps that fill the frame in both.
- In horizontal videos, show code beside the live app rather than over it.
