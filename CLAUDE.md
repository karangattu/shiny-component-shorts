# CLAUDE.md

This repo creates short Shiny component demo apps and 30-second video concepts.

When asked for Shiny component demos, use the `/shiny-component-shorts` skill.

Defaults:
- Prefer official Shiny documentation.
- Prefer Python Shiny Express unless the user asks for R.
- Demo targets are Shiny for Python, R Shiny, and shinychat; a chat demo never calls a real LLM.
- A pull request, commit URL, or commit SHA is a valid request: demo one user-facing change from it.
- One video = one feature.
- Keep apps tiny, visual, and recordable.
- Reserve the top 20% and bottom 20% of the frame for branding and fill the middle band's horizontal space.
- Every recording is stamped with a small Shiny wordmark in the top-left, painted in Shiny blue; the recorder adds it, so never put a logo in the app.
- Use only the official Shiny preset palette with accessible light- or dark-mode text.
- Do not include laughing, giggling, chuckling, or other non-speech narration sounds.
- In horizontal videos, show code beside the live app rather than over it.
