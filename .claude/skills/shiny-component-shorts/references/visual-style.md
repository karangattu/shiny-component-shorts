# Shared visual style

Use the official [bslib Shiny preset](https://github.com/rstudio/bslib/blob/main/inst/builtin/bs5/shiny/_variables.scss) for new demo UI and added video labels:

- Open Sans for body text and headings; Source Code Pro for code and captured output. Embed the bundled fonts for offline rendering.
- Primary `#007BC2`, light surface `#F8F8F8` or white, light-mode text `#1D1F21`, secondary text `#48505F`; dark surfaces use white text.
- Use the preset accent colors only when they explain a state. Keep highlights Shiny blue.

In written explanations, use fenced code blocks with an explicit language tag.

Always show code with GitHub-style syntax highlighting, including editorial excerpts, component code cards, release explainers, and inline code snippets. Use GitHub light on light code surfaces and GitHub dark on dark code surfaces. Syntax token colors are the exception to the Shiny UI palette. Use Source Code Pro in either theme. Do not recolor code tokens with Shiny accents or invent a custom tokenizer.

The offline highlighter and official GitHub themes are bundled in `assets/highlightjs/`. `scripts/code_style.py` exposes `browser_script()`, `stylesheet()`, and `font_css()`. Add its styles and fonts to a page, evaluate `browser_script()`, then call `shinyHighlightLines(source, language)` for escaped, balanced HTML for each source line. Highlight the whole block before laying out lines so multiline strings and comments retain their meaning. For legacy `explainer.yaml`, set `language: r` (or another lexer) when the example is not Python; an adjacent `app.R` also selects R automatically. Preserve all source characters and indentation; choose readable excerpts and explicit wrapping without changing the example.

Keep output and logs faithful, in Source Code Pro; use a plaintext lexer for output. Preserve native app recordings and source figures. When a capture includes code that cannot be read clearly, add a faithful highlighted source excerpt beside it or as the next shot instead of painting over the capture.

The [bslib theming guide](https://rstudio.github.io/bslib/articles/theming/index.html) supports custom themes; the default here is the Shiny preset, rather than one of its illustrative custom themes.
