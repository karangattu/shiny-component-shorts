# Short-form pacing patterns

Use these patterns when creating or editing a recorded short. They are derived from the user's reel references, but must be adapted to the Shiny demo. Do not download, reuse, or imitate another creator's footage, branding, or exact copy.


## Editorial release and blog pacing

For new release/changelog/blog videos, follow the editorial workflow in
[changelog-reel.md](changelog-reel.md). Give each point its own complete video, starting around 60–120 seconds and extending as needed. Show context, a working example, decisive details, a real result, and a useful caveat. Do not squeeze points into 15–25-second segments or reuse the 45-second component template. Start with meaningful source content,
use a small title over the opening shot, and cut directly between evidence.
Keep a source figure, code excerpt, or result still for as long as the spoken
thought needs. A quiet reading hold is useful; it does not need a state change
every few seconds. Highlight only the detail being discussed. No decorative
motion, typewriter effects, numbered feature cards, or novelty transitions.
Use about 5% margins and frame each orientation for legibility rather than
reserving 40% of the frame. Preserve the captured UI's appearance.

Follow the same app task across the problem, real action, visible result, code,
and return to that result. Let the pointer reach the control and show its real
response. Keep familiar setup moving; hold a key result or code for the time
it needs. Vary shot length with the thought instead of using equal holds or
inventing activity. Prefer the app's own result to a duplicate summary; use a
comparison or diagram only when it makes the point clearer. Narration should
describe the visible actions and consequences in their actual order.

The action cadence, code-card requirements, and middle-band layout below apply
to standalone component shorts, not editorial segments.

## Standalone component shorts

## Retention stack

Layer information so the viewer always knows two things:

1. **Why to care:** A short, plainly stated problem in the narration (or a later edit), not baked into the app UI and not phrased as a pitch.
2. **What is happening now:** The app state and narration captions make the current action clear.

Do not render the hook as an in-app eyebrow, series label, or oversized headline. Let the component occupy that space.

Use `Reveal`, `Proof`, `Code`, and `Payoff` only as planning labels in the storyboard and edit timeline. Do not show those labels, numbered state chips, or a beat rail in the video.

Captions belong to a later edit, never to the browser recording: `actions.yaml` has no caption actions. If an edit adds them, place them just above the bottom branding band, use one or two lines of 2–7 words, and never show one while the code card is on screen. Captions support the narration; they do not repeat a headline.

## Hook pattern

State a precise Shiny problem plainly, the way you'd mention it to a coworker, before naming the component.

Weak:

> Did you know Shiny has update functions?

Also weak (sounds like an ad):

> Still stacking the same notification five times?

Stronger:

> Every time this button runs, Shiny stacks another notification on top of the last one.

Then reveal the component behavior that solves it. The first visible state change must land during the hook sentence — anchor it with a `cue` to a word about 1.5–3 s into the narration so the pointer has time to travel.

## Visual rhythm

Use a stable composition with frequent information changes:

- Keep the Shiny app as the hero in the center height band and stretch it across the available horizontal space between 3–5% side gutters.
- Make each app state change visually self-explanatory.
- Keep the full app in frame; state changes must be legible without camera moves.
- Show a static source excerpt while explaining it, with complete text visible immediately and a quiet reading pause. Return to the app to prove the result. No fake editor chrome, cursor, or typing.
- Return to the full app for the payoff.
- Aim for a visible app change every 1.5–3 seconds, from interactions and their reactions. The validator rejects any gap over 8 seconds while narration plays.

Do not add motion that competes with the component, and never crop, zoom, or punch in. Pointer movement alone is not a visual change.

## Frame composition

Design for the final orientation from the start.

- Record vertical video at 1440×2560 and horizontal video at 2560×1440.
- Compose against the logical 720×1280 or 1280×720 viewport; Chromium renders that layout at native 2× HiDPI resolution.
- Leave the top 20% and bottom 20% visually empty for later editing; do not add a logo unless the user requests one. Put the app in the middle 60% height band and let it occupy all available horizontal space except 3–5% side gutters.
- Use one primary card or panel; avoid desktop sidebars and wide multi-column dashboards.
- Make controls large enough for a phone screen and keep labels short.
- Verify the first, middle, every code block, and final frames at actual phone size.

In horizontal mode, place the app and a readable static source excerpt side by side. In portrait, give code the full frame. Keep the filename, exact line numbers, and GitHub highlighting; no simulated editor controls. Prefer 4–7 relevant lines, and use separate excerpts for separate functions.

All framing and editing elements must stay in the Shiny preset palette. Use Shiny blue `#007BC2` for primary emphasis, `#FFFFFF`/`#F8F8F8` with `#1D1F21` text for light treatments, and `#1D1F21`/`#202020` with `#FFFFFF` and `#CDD4DA` text for dark treatments.

## Suggested 45-second edit rhythm

These are the same beats and times as the story table in `SKILL.md`; the times are targets, and the measured narration sets the real ones.

| Time | Beat | Retention treatment |
| ---: | --- | --- |
| 0–4 | Problem | Spoken hook begins; the first action is underway |
| 4–12 | Reveal | The app reacts; the changing readout carries the beat |
| 12–27 | Proof | Repeat, reverse, or contrast the behavior |
| 27–40 | Code | Portrait: full-frame static source. Landscape: app and code side-by-side |
| 40–45 | Payoff | Strongest result, full app, short takeaway |

## Editing restraint

- Use Shiny blue `#007BC2` as the default accent; introduce another Shiny semantic color only when it communicates state.
- Use one caption style; do not add a display headline inside the app.
- Prefer hard cuts in any later edit; do not add scale moves, punch-ins, or novelty transitions. Static source excerpts also use hard cuts.
- Keep captions and the code card from overlapping: show either a caption or the code card, never both.

## Natural narration

Keep the voice at natural speed and preserve normal pauses. For a rushed local voice, add pause tags or split long sentences so the engine pauses more, then shorten the script if it runs long, and regenerate instead of accepting the fast take; Qwen stays at `speaking_rate` 1.0 because its speed control time-stretches the audio. Create pace through concise writing and purposeful on-screen actions. Generate the narration first, measure its word timing, and anchor each reaction and the code reveal to the phrase that describes it with a `cue`. Shorten and regenerate an overlong script; never speed up the voice or cut its pauses to meet a target length. Review the merged video with sound before delivery whenever listening is available.
