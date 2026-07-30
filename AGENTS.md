# AGENTS.md

## Project purpose

This repo generates short Shiny component demo apps and 30-second video concepts.

## Defaults

- Prefer official Shiny documentation as the source of truth.
- Prefer Python Shiny Express for short demos unless the user asks for R.
- Demo targets are Shiny for Python, R Shiny, and shinychat; a chat demo never calls a real LLM.
- A pull request, commit URL, or commit SHA is a valid request: demo one user-facing change from it.
- Keep demo apps small enough to understand in one screen.
- Every video idea must focus on one hidden behavior, not a full component tutorial.
- Reserve the top 20% and bottom 20% of each video frame for branding; fill the middle band's horizontal space with the app.
- Every recording is stamped with the Shiny wordmark in the top-left, sized to read on a phone; the recorder adds it, so never put a logo in the app.
- Use only the official Shiny preset palette, with accessible light- or dark-mode text colors.
- Never include laughing, giggling, chuckling, or other non-speech vocalizations in narration.
- In horizontal videos, show code beside the live app rather than over it.
- Use the `shiny-component-shorts` skill when creating component video ideas or mini-apps.
