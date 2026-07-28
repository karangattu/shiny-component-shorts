# Changeset sourcing

Use this reference when the request starts from a pull request, a commit, or a bare SHA instead of a component name. The goal is unchanged: one video about one behavior a developer would want to know. The changeset only decides which behavior is on the table.

## Supported projects

| Project | Repo | Language | Release notes | Install from source |
| --- | --- | --- | --- | --- |
| R Shiny | `rstudio/shiny` | R | `NEWS.md` | `pak::pak("rstudio/shiny@<sha>")` |
| Shiny for Python | `posit-dev/py-shiny` | Python | `CHANGELOG.md` | `pip install "git+https://github.com/posit-dev/py-shiny@<sha>"` |
| shinychat (Python) | `posit-dev/shinychat` | Python, in `pkg-py/` | `pkg-py/CHANGELOG.md` | `pip install "git+https://github.com/posit-dev/shinychat@<sha>"` |
| shinychat (R) | `posit-dev/shinychat` | R, in `pkg-r/` | `pkg-r/NEWS.md` | `pak::pak("posit-dev/shinychat/pkg-r@<sha>")` |

`posit-dev/shiny` does not exist; R Shiny lives at `rstudio/shiny`. shinychat is one monorepo holding two packages, and its GitHub releases are tagged `py/vX.Y.Z` and `r/vX.Y.Z`. Install its Python package from the repo root, not `#subdirectory=pkg-py`: the `pyproject.toml` lives at the root and points hatchling at `pkg-py/src/shinychat`, so a subdirectory install fails with "does not appear to be a Python project". Only the R package needs the `/pkg-r` suffix.

Other Shiny-ecosystem repos (bslib, shinywidgets, py-htmltools) are acceptable when the user names one; treat their public API the same way. Refuse only when the changeset has no user-visible surface at all.

## Resolving the reference

Accept any of these and normalize to `<owner>/<repo>` plus a PR number or SHA:

| User gives | Resolve with |
| --- | --- |
| PR URL or `owner/repo#123` | `gh pr view 123 --repo owner/repo --json title,body,files,mergeCommit,state,url` |
| PR diff | `gh pr diff 123 --repo owner/repo` |
| Commit URL or full/short SHA | `gh api repos/owner/repo/commits/<sha>` |
| Bare SHA with no repo | Try each supported repo with `gh api repos/<repo>/commits/<sha>`; ask only if more than one matches or none do |
| Release tag | `gh release view <tag> --repo owner/repo` |

Read the changelog or `NEWS.md` entry in the diff before reading the code. That line is the author's own statement of the user-facing change and is usually the video's subject. If the changeset has no changelog entry, that is a signal it may be internal.

Never rely on a summary of the diff. Confirm the exact function, argument, and default value in the changed source at that ref.

## Choosing the behavior

Rank the changed files: public UI functions, server update functions, CSS, and bundled JS outrank docs, tests, type stubs, CI, and dependency bumps.

Reject the changeset for a video when its only changes are internal refactors, typing, packaging, CI, docs, dependency bumps, or performance with no visible difference. Say so plainly and offer the strongest nearby alternative — a released behavior in the same component — rather than manufacturing a demo.

When the changeset does touch behavior, score it with the creative playbook's four feature questions and pick a proof shape:

- New option versus the previous default is a direct comparison: show the same content with the option off, then on.
- A fixed bug is a direct comparison only when the broken state is still reachable, for example through a released version running beside the patched one. If it is not reachable, demo the corrected behavior on its own and let the code card carry the change.
- A new server-side update function is a two-way proof: drive the state by hand, then from the server.

One changeset is one video. If a PR lands several user-facing changes, choose the strongest and list the others as candidates.

## Running an unreleased changeset

The app has to run against the code from the changeset, not the published release, or the demo proves nothing. Check the release notes first: if the behavior already shipped, pin the released version and skip this section.

Build one throwaway environment per changeset and keep the recorder's own dependencies in it, because the recorder serves the app with `sys.executable -m shiny run` — the interpreter that runs the recorder is the interpreter that serves the app.

```bash
python3 -m venv generated/demo-name/.venv
generated/demo-name/.venv/bin/pip install -r requirements.txt
generated/demo-name/.venv/bin/pip install "git+https://github.com/posit-dev/py-shiny@<sha>"
generated/demo-name/.venv/bin/playwright install chromium

generated/demo-name/.venv/bin/python \
  .claude/skills/shiny-component-shorts/scripts/record_demo.py \
  --project-dir generated/demo-name --app-type python --actions actions.yaml
```

For R, install the package build into the library the recorder's `Rscript` will use, then confirm with `packageVersion()`.

Before writing the app, prove the API exists in the installed build instead of trusting the diff:

```bash
generated/demo-name/.venv/bin/python -c "
import inspect, shiny
print(shiny.__version__)
print(inspect.signature(shiny.ui.input_text))"
```

Write the resolved repo, SHA, PR URL, and installed version into `changeset.md` in the demo directory so the recording is reproducible. Do not state a release number in narration unless a changelog or release confirms the behavior shipped in it; an unreleased change is "just landed", not "new in 1.7".

## shinychat specifics

- shinychat's Python and R feature sets drift apart. Confirm the feature exists in the language you are demoing, at the version you installed, before designing the video. As of shinychat 0.6.0 (Python) and 0.4.0 (R/CRAN), attachments, slash commands, `submit_key`, and the history drawer are Python-only.
- shinychat is a dependency of Shiny for Python 1.5.0 and later; `shiny.ui.Chat` re-exports `shinychat.Chat`. Import from `shinychat` in demo apps.
- Never point a demo at a real LLM. Recordings must be repeatable and must not need a key. Use a canned reply or a canned stream:

```python
from shiny.express import ui
from shinychat.express import Chat

chat = Chat(id="review_chat")
chat.ui(placeholder="Ask about this pull request")

@chat.on_user_submit
async def answer(user_input: str):
    await chat.append_message_stream(canned_chunks(user_input))
```

```r
observeEvent(input$review_chat_user_input, {
  chat_append("review_chat", canned_stream(input$review_chat_user_input))
})
```

  `Chat.append_message_stream()` accepts any iterable or async iterable, so a generator yielding short slices with `asyncio.sleep(0.02)` reproduces token streaming exactly. In R, `chat_append()` takes a `coro::async_generator()` result, or a plain string for a non-streaming reply.

- Some features are gated behind a real client rather than an `on_user_submit` handler. Conversation history is one: `Chat(history=...)` raises `ValueError: Chat history requires a client. Pass one to Chat(client=...)`, which also gates message editing and sibling navigation. Keep the demo keyless by subclassing `chatlas.Chat` with a `MagicMock()` provider and overriding `stream_async` to yield canned chunks — the pattern upstream uses in `pkg-py/tests/playwright/`. Expect a harmless server-side `UserWarning` about conversation-title generation, since the fake provider cannot write titles; it never reaches the browser.
- The user's message arrives as `input[f"{id}_user_input"]` in Python and `input$<id>_user_input` in R.
- The chat UI is one custom element, `shiny-chat-container`, with plain classes inside after the React rewrite. Working selectors, confirmed in a browser: `#<id>_user_input .tiptap` (the input is a TipTap contenteditable, not a textarea), `.shiny-chat-btn-send`, `.shiny-chat-user-message`, `.shiny-chat-messages-content`, and `aria-label` buttons such as `Edit message`, `Save and resend`, and `Previous version`. Most of these only exist after the first message or on hover, so declare them with `wait_for` or the recorder's selector pre-check fails the run.
- `chat_ui()` defaults to `width="min(680px, 100%)"` and `fill=True`. For the vertical frame, set `width="100%"` and a fixed `height` so the transcript stays inside the middle 60% band instead of stretching into the reserved top and bottom areas.
- Verified no-key visual candidates: streaming responses, suggestion chips and suggestion cards (`class="suggestion"`, autosubmit via `data-suggestion-submit="true"`), the greeting that clears on first submit (`chat_greeting()`), markdown rendering with a code-block copy button, `enable_cancel`, `chat_clear()` / `await chat.clear_messages()`, live placeholder changes (`update_chat_user_input()` / `chat.update_user_input()`), and `markdown_stream()` / `MarkdownStream` streaming outside a chat.
- Everything else in this skill still applies to a chat demo: the safe area, the Shiny palette, the typography rotation, no visible app title, stable IDs, and a verbatim code card.
