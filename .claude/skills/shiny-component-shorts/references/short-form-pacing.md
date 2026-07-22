# Short-form pacing patterns

Use these patterns when creating or editing a recorded short. They are derived from the user's reel references, but must be adapted to the Shiny demo. Do not download, reuse, or imitate another creator's footage, branding, or exact copy.

## Retention stack

Layer information so the viewer always knows two things:

1. **Why to care:** A short problem-led hook in narration or later editing, not baked into the app UI.
2. **What is happening now:** The app state and narration captions make the current action clear.

Do not render the hook as an in-app eyebrow, series label, or oversized headline. Let the component occupy that space.

Use `Reveal`, `Proof`, `Code`, and `Payoff` only as planning labels in the storyboard and edit timeline. Do not show those labels, numbered state chips, or a beat rail in the video.

Add narration captions separately in the lower-middle safe zone. Use one or two lines, usually 2–7 words per caption card. Captions support the narration; they do not repeat the persistent headline.

## Hook pattern

Call out a precise Shiny frustration or desired outcome before naming the component.

Weak:

> Did you know Shiny has update functions?

Stronger:

> Still stacking the same notification five times?

Then reveal the component behavior that solves it. The first visible state change must begin by second 2.

## Visual rhythm

Use a stable composition with frequent information changes:

- Keep the Shiny app as the hero in the center height band and stretch it across the available horizontal space between 3–5% side gutters.
- Make each app state change visually self-explanatory.
- Cut or punch in on the affected UI region after a meaningful action.
- Use a compact Shiny-branded code card sized by reading time (typewriter animation + a hold computed from character count); keep the live app visible.
- Return to the full app for the payoff.
- Make one visual change every 1.5–3 seconds: interaction, reaction, crop, or caption.

Do not add motion that competes with the component. Pointer movement alone is not a visual change.

## Frame composition

Design for the final orientation from the start.

- Record vertical video at 1440×2560 and horizontal video at 2560×1440.
- Compose against the logical 720×1280 or 1280×720 viewport; Chromium renders that layout at native 2× HiDPI resolution.
- Leave the top 20% and bottom 20% visually empty for later branding. Put the app in the middle 60% height band and let it occupy all available horizontal space except 3–5% side gutters.
- Use one primary card or panel; avoid desktop sidebars and wide multi-column dashboards.
- Make controls large enough for a phone screen and keep labels short.
- Verify the first, middle, code, and final frames at actual phone size.

In horizontal mode, show the code and live app side-by-side during the code beat: keep the app on the left and the Shiny-branded code panel on the right. Never place the code panel over the app in horizontal mode. In vertical mode, the code card sits in the lower half of the frame, anchored just above the bottom branding band, so the component stays visible above it; compose the app toward the top of the middle band.

All framing and editing elements must stay in the Shiny preset palette. Use Shiny blue `#007BC2` for primary emphasis, `#FFFFFF`/`#F8F8F8` with `#1D1F21` text for light treatments, and `#1D1F21`/`#202020` with `#FFFFFF` and `#CDD4DA` text for dark treatments.

## Suggested 30-second edit rhythm

| Time | Beat | Retention treatment |
| ---: | --- | --- |
| 0–2 | Pain | Spoken hook begins; first action starts |
| 2–7 | Reveal | App reacts; first caption supports the change |
| 7–14 | Proof | Second state; punch in on the changing region |
| 14–19 | Contrast | Reverse or reset to strengthen the proof |
| 19–23 | Code | Vertical: compact card over the app. Horizontal: app and code side-by-side |
| 23–30 | Payoff | Strongest interaction, full app, short takeaway |

## Editing restraint

- Use Shiny blue `#007BC2` as the default accent; introduce another Shiny semantic color only when it communicates state.
- Use one caption style; do not add a display headline inside the app.
- Prefer hard cuts or quick 120–220 ms scale moves; avoid novelty transitions.
- Keep captions and the code card from overlapping.
- Never show all overlay layers at once. Show either a caption or the code card over the app.
