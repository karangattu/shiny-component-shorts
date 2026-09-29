# shinyreact demos

Use this reference for [posit-dev/shinyreact](https://github.com/posit-dev/shinyreact). It connects a React frontend to a Shiny server in Python or R. It is distinct from Appsilon's `shiny.react`. Focus a short on one visible input, output, or message behavior.

## Sources and runtime

Read the official [Python guide](https://github.com/posit-dev/shinyreact/blob/main/pkg-py/README.md), [R guide](https://github.com/posit-dev/shinyreact/blob/main/pkg-r/README.md), and [client hooks](https://posit-dev.github.io/shinyreact/articles/hooks.html). Confirm APIs in the installed version: upstream main can be ahead of a release.

- Prefer Python Express with `set_react_page()`. Core and R use `page_react()`; explicit HTML templates can use `page_react_html()` when supported by the chosen version.
- Keep `app.py` or `app.R` as the server entry point. Record using `--app-type python` or `--app-type r`; React is the frontend, not a third server runtime.
- For tiny new demos, use plain `www/ui.js` and `www/ui.css` with the package's `window.shinyreact.React` and `ReactDOM`. This avoids a frontend build and duplicate React instances. Do not put JSX or TypeScript directly in a browser script.
- For an existing JSX/TSX app, inspect its manifest and build commands, build its assets first, and keep its original source and layout. The recorder starts only Shiny; it does not start Vite. Retain the frontend source for code-card validation.
- Apply the Shiny palette, readable type, stable DOM IDs, and middle 60% recording area in the frontend CSS. Do not assume Bootstrap classes are available. The recorder supplies the wordmark.

## Installation

Keep shinyreact optional and out of the shared `requirements.txt`. Create a demo-local venv, install the baseline first, and then install shinyreact there:

```bash
python3 -m venv generated/demo-name/.venv
generated/demo-name/.venv/bin/python -m pip install -r requirements.txt
generated/demo-name/.venv/bin/python -m pip install shinyreact
generated/demo-name/.venv/bin/python -m pip check
```

For a changeset, replace the shinyreact install with `pip install "git+https://github.com/posit-dev/shinyreact@<sha>"`. Install from the repo root. Run the recorder with this same interpreter. Do not reinstall the baseline afterward: its Shiny pin can downgrade a required dependency. Record the resolved package versions; resolve dependency conflicts before recording.

For R, create and export a demo-local `R_LIBS_USER` directory before `pak::pak("posit-dev/shinyreact/pkg-r@<sha>")` (omit `@<sha>` for development main). Check `.libPaths()` and the installed version, then keep that environment when launching the recorder. Follow [changeset-sourcing.md](changeset-sourcing.md) for both languages and for rebuilding shared JS changes.

## Minimal structure and proof

```text
generated/demo-name/
├── app.py or app.R
├── www/
│   ├── ui.js
│   └── ui.css
└── actions.yaml                 # only when recording is requested
```

Connect a frontend input through `useShinyInput`, compute a result with server `reactive_output`, and display it with `useShinyOutputValue`. Check the installed hook signatures, initial values, and server registration conventions before implementing. Use `useShinyOutputStatus` for a loading-state idea only if available. Server messages should demonstrate a visible client reaction, not just console output.

Choose one proof: two controls staying synchronized, a server calculation responding to edits, or a result's loading state. Exercise three meaningful changes, including a reversal or reset. Check server output as well as the local React state so a disconnected client cannot pass as a working demo. Use canned data; a chat-shaped UI must still never call a real LLM.

## Recording and code cards

Use the existing preflight, recording, validation, narration, and review workflows. `--app-dir` points to the directory containing the server entry point, even when the highlighted code is under `www/` or `src/`.

For a frontend trick, set `source_file: www/ui.js` (or the actual JSX/TSX path) on the `code` action. Copy the focus and surrounding context verbatim from that file. The validator checks only the selected file; `title` changes the label, not the source. JavaScript and TypeScript syntax highlighting is inferred from the source extension. For a server trick, keep the ordinary `app.py` or `app.R` card. See [recording-contract.md](recording-contract.md#frontend-code-cards-shinyreact).

Before acceptance, exercise the React controls, verify the server response and stable selectors, check browser/server errors, and run the standard recorder preflight. For built clients, confirm the served bundle reflects the source shown in the code card. No client error panel may appear in the recording.
