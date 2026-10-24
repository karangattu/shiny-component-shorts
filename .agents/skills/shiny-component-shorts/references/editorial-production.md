# Reproduce the natural editorial style

Use this guide for release, changelog, and blog videos. The goal is a coworker explaining real software: useful content from the first frame, a working example, readable source details, and a verified result. Keep the existing component recording workflow for component shorts.

## Start from the shared tools

Copy the files in `assets/editorial-starter/` into one generated feature directory. Create the actual example, save clean captures under `sources/`, and write the complete narration envelope from the creative playbook to `artifacts/narration.txt`. The starter contains no invented app or test results; its file names and cues must be replaced with your evidence and spoken words.

Use a dedicated environment for the intended release. Install `<skill>/requirements.txt` first, then install the exact target Shiny version in that disposable environment. Keep the PyAV constraint `av<14` with the current faster-whisper dependency; newer versions can fail at transcript ranking with `metadata_errors`. Run from the generated project directory, not the framework checkout: the current directory can shadow the installed package even with an explicit interpreter. Record the imported `shiny.__version__` and `shiny.__file__` before testing or capture. Do not change global dependencies.

For each claim, identify what a viewer can inspect: the actual app state, a verbatim code excerpt, a source figure, a saved successful/failing run, or a documented limit. Verify selectors, actions, and environmental conditions before expensive production. A page query is not necessarily forwarded to its WebSocket session. Test mode flags and session identifiers directly instead of assuming routing or state preservation. Never claim behavior your local host cannot demonstrate.

## Plan one complete explanation per point

Start around 60–120 seconds for a detailed feature. Let the example set the length. Show a useful result, then explain the decisive code and prove it with an actual run. Include a caveat only when it changes how someone uses the feature. New points need new narration; extending an old 22-second clip does not add detail.

An overview is a separate edit, created only when requested. Reuse verified source captures from the detailed videos and write a fresh short explanation of each point. Do not concatenate their full narrations or squeeze the detailed videos into the overview's time budget.

Keep the chosen brand system consistent across these editorial videos: Open Sans for prose, Source Code Pro for code/output, GitHub syntax highlighting, Shiny blue emphasis, and restrained light surfaces. Preserve native app styling and source figures. No fake editor windows, simulated typing, decorative animation, feature-card interstitials, or progress ornaments. Use hard cuts and one static highlight at a time. Captured countdowns held as stills must be labelled as captured stills, not presented as a ticking clock.

## Build readable evidence shots

Write `source-shots.yaml` and run:

```bash
<python> <skill>/scripts/prepare_editorial.py --project-dir <feature>
```

Replace `<python>` with the explicit project interpreter and `<skill>` with this installed skill directory. All commands below use the same interpreter.

Each shot quotes a narration `cue`, an optional `source` label, an optional `chapter` title, and `panels`. A panel reads a local `file`:

- `kind: code`: exact source, inferred language or explicit `language`, optional inclusive `lines: [first, last]`, and one optional `highlight` source line number.
- `kind: output`: exact saved output in a monospace face, with no fabricated terminal chrome.
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

Finally inspect each shot and cut in both encoded phone-size review sheets, check that highlights and labels do not hide evidence, and audition the merged videos when available. Keep this human review separate from automated validation. Deliver both orientations, thumbnails, review sheets, source/configuration files, and a concise file index. For a series plus overview, retain the detailed videos and put the short overview first in that index. A paid-service cost report is needed only if a paid API was used or the user asks for costs.
