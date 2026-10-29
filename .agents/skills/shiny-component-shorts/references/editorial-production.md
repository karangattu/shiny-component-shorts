# Reproduce the natural editorial style

First run [automatic production setup](version-management.md) and use the returned pinned skill for all commands below.

Use this guide for release, changelog, and blog videos. The goal is a coworker explaining real software: useful content from the first frame, a working example, readable source details, and a verified result. Keep the existing component recording workflow for component shorts.

## Start from the shared tools

Copy the files in `assets/editorial-starter/` into one generated feature directory. Create the actual example, save clean captures under `sources/`, and write the complete narration envelope from the creative playbook to `artifacts/narration.txt`. The starter contains no invented app or test results; its file names and cues must be replaced with your evidence and spoken words.

Use a dedicated environment for the intended release. Install `<skill>/requirements.txt` first, then install the exact target Shiny version in that disposable environment. Keep the PyAV constraint `av<14` with the current faster-whisper dependency; newer versions can fail at transcript ranking with `metadata_errors`. Run from the generated project directory, not the framework checkout: the current directory can shadow the installed package even with an explicit interpreter. Record the imported `shiny.__version__` and `shiny.__file__` before testing or capture. Do not change global dependencies.

For each claim, identify what a viewer can inspect: the actual app state, a verbatim code excerpt, a source figure, a saved successful/failing run, or a documented limit. Verify selectors, actions, and environmental conditions before expensive production. A page query is not necessarily forwarded to its WebSocket session. Test mode flags and session identifiers directly instead of assuming routing or state preservation. Never claim behavior your local host cannot demonstrate.

## Plan one complete explanation per point

Start around 60–120 seconds for a detailed feature. Let the example set the length. Show a useful result, then explain the decisive code and prove it with an actual run. Include a caveat only when it changes how someone uses the feature. New points need new narration; extending an old 22-second clip does not add detail.

Build the story around a specific user goal: show the problem in the running app, the action and result, then the decisive code, why it works, and any practical limit. Open the overview with that problem, not a list of features. Prefer a believable task with meaningful data over a bare test fixture, while retaining small examples and clearly identifying simulated work. Verify the new example against the intended Shiny environment before recording.

## Follow one observable story

- Plan each point as one connected task: show the starting state and problem, the actual action, and its visible result. Keep the same app, selected values, and session across cuts when the explanation depends on them. Label separate runs or a reset when needed; never imply continuity between independent captures. Explain a before/after comparison using real runs.
- Record enough context for a person to follow the interaction: let the macOS-style pointer approach the intended control, click, and pause for the real response. Use original-speed footage and avoid needless cursor movement, clicks, loops, or staged activity. Continue the shot through the result where it remains readable.
- Prefer showing the result in the app first. Return to the same visible result after showing a short, complete source excerpt explaining it. Use a separate evidence-backed summary, comparison, or timeline only when it clarifies something the app cannot show clearly; preserve exact results and provenance. Do not replace an understandable app reaction with a redundant full-screen summary.
- Give each excerpt enough time to read, but vary shot lengths for the thought being explained. Move briskly through familiar setup, pause on the consequential state or subtle result, and cut when the subject changes. No fixed activity quota, automatic motion, equal-length shot rule, or artificial time pressure applies to editorial videos.
- Write narration as observations a developer makes while demonstrating the task. Name the action and the visible consequence in the order the viewer sees them, then explain the relevant code and limitation. For example, if the verified recording shows these exact states: “I start the West report, then switch to East. The page responds, and the report still finishes with West.” Describe only what the capture proves; preserve necessary qualifications and avoid turning the explanation into an API list. When remaking a video, reuse its narration only if it still matches the new edit; otherwise regenerate and realign it with the existing local voice workflow.

Choose the visual form that makes each claim immediately understandable:

- **Compare together:** Show real before/after runs, or two meaningful states, side by side when readable. For timing comparisons, use the real measured durations and an elapsed-time indicator tied to the recording or saved measurement. Identify independent runs and unequal conditions; do not imply separately recorded runs occurred simultaneously. In portrait, stack the views or alternate matched close views if side-by-side would make them unreadable.
- **Connect app and code:** In landscape, place a short verbatim, GitHub-highlighted excerpt beside the relevant live app action when both remain readable. Highlight only the responsible line. In portrait, cut between a readable excerpt and the same app state, then show its outcome. Preserve source order and indentation and never simulate typing.
- **Explain invisible behavior:** A concise timeline, sequence, or other diagram may clarify async scheduling, reactive boundaries, or data flow. Derive each event, order, and displayed duration from the verified run or authoritative source. Reveal events only when their evidence and narration support them; distinguish conceptual diagrams from live recordings and label simulated data. Do not invent timings, imply that a diagram is the actual application, or add decorative motion.
- **Vary framing with purpose:** Fill the frame with the relevant evidence using approximately 5% margins; remove unused space without cropping context or errors. Alternate close app views, comparisons, code, diagrams, and results when each advances the story. Cut on a change of idea and leave readable code and results on screen long enough to understand them. Recompose each orientation rather than shrinking a desktop frame.

When an app interaction or changing state supports a spoken point, record the real interaction as video in both orientations, including its visible result. Plan and time the action to the narration; hold or cut to a readable still only when needed for a code or evidence reading pause. Keep capture at original speed, preserve the clean recording, and do not loop footage or animate screenshots to imply a real interaction. Static code, figures, and results remain appropriate when they explain the point best. Do not add motion just to fill time.

Minimize text added outside the evidence. Omit repeated explanatory footers and routine source labels from the frame; record provenance and any capture qualifications in the production index instead. Add a short on-screen qualification when it is necessary to avoid misleading the viewer, and retain attribution when required. Narration or optional accurate captions carry the explanation. When captions are supplied or requested, derive them from the actual narration and measured word timing, correct technical terms against the verified transcript, and save an editable sidecar (for example, SRT). Reserve space in each orientation; use short, readable phrases with adequate contrast and never cover code, controls, a key app state, or an essential qualification. Review timing and spelling against the audio where listening is available. If not, disclose that listening was unavailable. The editorial renderer does not automatically add captions; use a separate captioned edit or provide the sidecar, preserving the clean export.

Treat each visible header, footer, annotation, and graphic as audience-facing content, including text baked into captures and custom assets as well as shot labels. Do not add production notes such as “runnable example,” “working sample,” “exact source,” “uniform indent removed,” “verified app captures,” or internal verification and capture details. A code excerpt is not a complete runnable app: do not imply viewers can run it or access the full source unless it is actually provided. Omit decorative or boilerplate footers. If a qualification affects interpretation, make it short and meaningful, such as “Simulated query” or “Sample data”; keep verification details in the production index. Retain necessary attribution, filenames, captions, and source text when they help the viewer or are required. Preserve third-party source captures faithfully; do not conceal an essential limitation or attribution.

Do not add explanatory or production footers to skill-created demo apps, diagrams, screenshots, or video overlays. This includes notes like “Simulated I/O: an async wait. Background result arrives after 0.5 seconds.” State the simulation and timing in narration or captions when relevant; keep test setup and verification in the production index. If the viewer needs a visible qualification to interpret a shot, use a short label beside the evidence at the relevant moment, not a recurring footer. Before capturing, inspect the actual app at every planned state in both orientations, including text inside cards and beneath controls. Before delivery, inspect every encoded shot and transition in both orientations. Any unwanted footer is a blocking defect: correct the authored app, graphic, or overlay, recapture or rebuild affected shots, and repeat the review. Keep clean recordings and prior exports separate. Never remove or hide a client error, required attribution, or essential limitation. Preserve user-provided apps and third-party captures; if the unwanted footer is part of one, explain the limitation rather than modifying or obscuring it without authorization.

An overview is a separate edit, created only when requested. Reuse verified source captures from the detailed videos and write a fresh short explanation of each point. Do not concatenate their full narrations or squeeze the detailed videos into the overview's time budget.

Keep the chosen brand system consistent across these editorial videos: Open Sans for prose and explanatory result summaries, Source Code Pro for code and literal console output, GitHub syntax highlighting, Shiny blue emphasis, and restrained light surfaces. Preserve native app styling and source figures. No fake editor windows, simulated typing, decorative animation, feature-card interstitials, or progress ornaments. Use hard cuts and one static highlight at a time. Captured countdowns held as stills must be labelled as captured stills, not presented as a ticking clock.

## Format explanatory results

When the viewer needs the meaning of observed results rather than the exact bytes of a log, turn verified evidence into a concise editorial summary. Use readable proportional text, descriptive grouping or short bullets, and selective bold or Shiny-blue emphasis on the values or comparison the narration explains. Do not add code-style line numbers, terminal chrome, or monospace to prose. Compose for phone-size readability in each orientation and let the result remain visible long enough to read. Preserve numbers, units, ordering, conditions, and limitations exactly; do not add unsupported claims or imply the summary is a literal console capture. Record the underlying saved output, source paths, and transformation in the production index so it can be checked.

For example, a verified log stating `Input during read: 10 → 10` can be summarized as “Input during the read: **10 → 10**.” Keep a real log, test output, or stack trace verbatim when its exact content or formatting is the evidence. Keep code verbatim, syntax-highlighted, and in monospace. Do not reformat third-party captures in a way that obscures their source or essential context.

The current `prepare_editorial.py` `kind: output` panel renders exact saved output in a code-style block; it does not render Markdown as formatted prose. Do not place Markdown markup there expecting it to become bold text. Instead, create an honest, separately labeled summary as an authored graphic or a rendered document capture, keep its original evidence, and reference the generated asset as an image shot. Continue to use `kind: output` for literal output when fidelity is essential.

## Build readable evidence shots

Write `source-shots.yaml` and run:

```bash
<python> <skill>/scripts/prepare_editorial.py --project-dir <feature>
```

Replace `<python>` with the explicit project interpreter and `<skill>` with this installed skill directory. All commands below use the same interpreter.

Each shot quotes a narration `cue`, an optional `chapter` title, and `panels`. Omit the optional visible `source` label unless it is necessary for attribution or an essential qualification. A panel reads a local `file`:

Before rendering, review all authored panel `label` and shot `source` fields and text in custom graphics and demo UI using the audience-facing rule above. Inspect the final encoded frames in both orientations for leftover production notes, not just the configuration; remove or revise the authored text at its source.

- `kind: code`: exact source, inferred language or explicit `language`, optional inclusive `lines: [first, last]`, and one optional `highlight` source line number.
- `kind: output`: exact saved output in a monospace face, with no fabricated terminal chrome. Use this when the literal output is the evidence; use an authored, evidence-backed summary image for formatted explanatory results.
- `kind: text`: verbatim source prose or a saved explanation. Keep quotations short and retain attribution.
- `kind: image`: an actual clean capture or source figure. Crop deliberately before supplying it; never cut out an error or a relevant limitation.

Common panels reflow independently in the two orientations. For different captures or excerpts, set `views.vertical.panels` and `views.horizontal.panels` explicitly. Keep excerpts short. The builder refuses vertical overflow and horizontal scrolling rather than shrinking code until it fits. The optional per-view `font_size` is in logical pixels (default 26 portrait, 32 landscape); do not lower it to rescue an overloaded shot.

The builder creates both PNGs and inspectable HTML under `artifacts/editorial-sources/`, computes highlight rectangles, records hashes of the original evidence, and writes `editorial.yaml`. It replaces only its own generated configuration. Edit `source-shots.yaml`, not generated screenshots or configuration. If you already authored `editorial.yaml` by hand, keep that workflow; the builder is optional. Videos still use hand-authored views with `file`, `fit`, and an optional original-speed `in` point as described in [changelog-reel.md](changelog-reel.md).

Inspect the stills at phone size before narration or final encoding. Break crowded shots into shorter excerpts; compose the two orientations separately. Preserve clean captures and edited outputs separately.

## Select narration before cutting

Use the saved local voice workflow in [tts-and-costs.md](tts-and-costs.md). Apply the simple-English meaning pass and speech-texture pass. Run `check_narration_voice.py`. Keep natural speed and planned pauses; no time stretching or removal of speech pauses to hit a duration.

Generate and rank three takes with `batch_process.py --phase takes --dirs <feature>`. This does not pin a take. Review `artifacts/narration-takes/ranking.json`, then run a separate selection command:

```bash
<python> <skill>/scripts/batch_process.py --phase takes --dirs <feature> --select-take take-1.wav
<python> <skill>/scripts/batch_process.py --phase narration --dirs <feature>
```

Choose the actual best take, not always take 1. Review every transcript difference, especially API names, numbers, and limits. A recognizer can mishear a proper name or invent a word near a pause. If uncertain, independently transcribe that short span with another available local recognizer or audition it. Regenerate when a content error is confirmed; do not repeatedly synthesize identical cached takes to repair a decoder/library failure. Preserve the original and selected audio. When listening is unavailable, report that limitation; transcript checks do not establish naturalness.

## Render, validate, and deliver

For one feature, use the starter's `reel.yaml`. For a series, list one directory per point and pass `--separate`. For an explicitly requested combined overview, use one overview narration/shot directory or shorter per-feature narrations, and omit `--separate`.

```bash
<python> <skill>/scripts/stitch_reel.py --reel-dir <project>
<python> <skill>/scripts/validate_editorial.py --reel-dir <project>
```

For a series, run `stitch_reel.py --reel-dir <series> --separate`, then the same validator on `<series>`. Both orientations are required unless the user requests one; use `--orientation` consistently in both commands in that case.

For an exact duration, add `target_seconds: 50` to the overview's `source-shots.yaml` (or hand-authored `editorial.yaml`). The narration plus its normal final hold must already fit. The renderer extends only the final still, at 30 fps, with no voice speed change, word trimming, or frozen footage. Use that hold for meaningful evidence that needs reading time. If it would become a long empty ending, revise the script and regenerate instead of padding a weak overview.

Add `chapter` to the first shot for each idea. The renderer embeds those chapter titles and phrase-aligned boundaries in the MP4 and writes them to the timing report. No separate chapter/padding script is needed.

The validator fully decodes the declared exports, checks dimensions, 30 fps, audio, frame counts, shot continuity, spoken-phrase offsets, embedded chapter boundaries, and current source/narration hashes. Original source edits invalidate generated stills even if their PNG files have not changed. It ignores caches and preserved comparison renders. Fix every failure before delivery.

Finally inspect each shot and cut in both encoded phone-size review sheets, and watch app footage through its action and result in both orientations. Check that the visible states and narration tell the same continuous story, app results precede supporting summaries, code returns to its outcome, cursor movement supports the action, and reading holds fit the content. Compare the revised video with its predecessor using the opening, visual proof, code-to-result connection, legibility, pacing, and accuracy; document observed improvements and remaining issues. This is a production review, not proof of audience engagement or comprehension. If audience performance is requested, use an actual viewer test or analytics when available and report sample size and limits; do not invent results. Check that text and highlights do not hide evidence or compete with the narration, and audition the merged videos when available. Keep this human review separate from automated validation. Deliver both orientations, thumbnails, review sheets, source/configuration files, and a concise file index. For a series plus overview, retain the detailed videos and put the short overview first in that index. A paid-service cost report is needed only if a paid API was used or the user asks for costs.
