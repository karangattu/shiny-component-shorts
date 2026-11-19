# Social vertical shorts: captions, styles, and structure

Use this guide for every vertical (9:16) video meant for social media. Many viewers watch with the sound off, so every vertical deliverable needs readable captions, and a series needs visual variety.

## Captions are required

- Burn captions into a separate, captioned copy with `scripts/burn_captions.py`. The clean export stays as it is.
- Build captions from the measured word timing in `artifacts/narration-timing.json`, never from retyped text. The script keeps the transcript's casing and punctuation when its word count matches the aligner's, and restores sentence casing when it does not.
- Write the SRT sidecar too. Platforms that accept uploaded captions can use it instead of the burned-in copy.
- Captions stay in the lower band of the frame, above the bottom 18–20% that social apps overlay with their own controls. Never cover code, a control, or a key app state. Check each caption frame at phone size.
- Use short phrases: two lines maximum, seven words or fewer per caption, broken at punctuation and long pauses. The script does this automatically.
- Do not caption the end card. Captions follow the narration, and the card has none. When a gallery episode speaks its closing line over the card, pass `--stop-at` with the first words of that line plus `--reel-json artifacts/reel.json` (and `--cut-lead 0.2`), so the last cue ends strictly before the end card cuts in.
- Preserve exact technical names (`shinywidgets`, `RDKit`, `MDTraj`, `rioxarray`, `py-shinywidgets`) and cardinal numbers (`1,797`, `183`) by normalizing tokens with `align_narration.normalize_tokens` and `assets/pronunciations.yaml`.

```bash
python3 .claude/skills/shiny-component-shorts/scripts/burn_captions.py \
  --video artifacts/series/<name>/reel.mp4 \
  --timing <feature>/artifacts/narration-timing.json \
  --style series \
  --accent "#03C7E8" \
  --reel-json artifacts/series/<name>/reel.json \
  --out-video artifacts/series/<name>/reel-captioned.mp4 \
  --out-srt artifacts/series/<name>/reel.srt
```

## Caption styles

| Style | Look | Best with |
| --- | --- | --- |
| `series` | Dark-glass translucent box with white words highlighting in `--accent` | Cohesive multi-episode series branding |
| `clean` | White text on a translucent black box | Dense explanations |
| `pill` | White text on a Shiny-blue pill | Short, punchy narration |
| `karaoke` | Outlined text; each spoken word fills yellow as it is said | Interactive demos, where the word and the click line up |
| `outline` | Heavy white text with a black outline, no box | Bright or busy app footage |
| `card` | Dark text on a white card | Light code cards |
| `bar` | Two-line caption bar across the lower frame | Longer sentences |

## Keep caption branding cohesive across a series

For a multi-episode series (such as showcase integration episodes), keep ONE cohesive caption container (`series`) across every episode and vary the Shiny `--accent`, `hook_style`, `code_theme`, and beat `order` via `look.py`:

1. Keep captions unified in `series` dark glass for integration series, or rotate `clean`/`pill`/`karaoke`/`outline`/`card`/`bar` when a standalone ad-hoc series needs distinct caption containers.
2. Vary the opening (`outcome-first`, `scale-lead`, `two-way`, `direct-action`). Never open every video with `"I <verb> ..."` or the same title card.
3. Vary the code card theme (`code_theme: dark` or `light`) so the series does not look like one template.
4. Vary the beat order (`integration-code` vs `code-integration`) and Shiny accent color.
5. Record the chosen style, accent, hook style, order, and theme for each video in `look.yaml` and the production index.

Visual variety should come from these choices, not from decorative motion, animated backgrounds, or interstitial cards. The rules in [editorial production](editorial-production.md) still apply.

## Show the integration, not the install

Do not spend time on install commands or setup. Viewers who want to try the app can find it in the repository. Open with the code or the app, and go straight to what the integration does:

- Name the package and the shinywidgets link in the first sentence, such as "Altair charts run in Shiny through shinywidgets."
- Show one real interaction, then the decisive line of code, then the result.
- End on what the viewer can now do, in one or two plain sentences, with no call to action (the end card carries that).

Install walkthroughs are optional. Include an install card only when the user asks for one.

## Open on an integration poster

Every vertical short opens on a poster before any footage, so a viewer knows what the video is about in the first second. The one exception is a [gallery integration episode](widget-integration-episodes.md): it opens on the interaction itself, names the package in its third beat, and keeps the poster as the thumbnail.

- Title: the integration's name as the website lists it, followed by "in Shiny", such as "Altair in Shiny", "ipycanvas in Shiny", "K3D in Shiny". Use the exact capitalization from the integration's page under `website/widgets/`.
- Summary: one line stating what the demo shows, taken from that page's description where it fits.
- Evidence: a clean frame from the recorded app, supplied through `context.captures` so the poster shows the real app, not a stock graphic.
- Timing: the poster is the first shot, cued to the first narration sentence. Footage begins after that sentence, so the poster holds for the first sentence and the title overlay on footage never starts before three seconds.
- The first narration sentence names the same integration as the poster title.

Keep the poster in both the captioned and clean exports. The end card stays the closing call to action.
