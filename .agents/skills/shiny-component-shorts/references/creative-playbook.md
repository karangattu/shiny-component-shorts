# Creative playbook

Use this reference before selecting a component feature or designing the mini-app.

## The proof rule

A short succeeds when the viewer can infer the behavior from the screen before hearing the explanation. Every concept must use one of these proof shapes.

### Direct comparison

Show the same realistic content in two states where one small component option creates an obvious difference.

Reference pattern: the textarea demo places an auto-resizing field beside a fixed-height field. Typing the same notes makes one grow while the other scrolls. Clearing the first field reverses the effect.

Use direct comparison when:

- an option changes layout, validation, formatting, or input behavior;
- the default behavior provides a useful control state;
- both states fit without shrinking the app below phone-readable size.

Do not create a fake “before” panel when the default component already supplies the comparison.

### Two-way proof

Drive the same component through two legitimate paths and show that its state remains reactive.

Reference pattern: the checkbox-group demo lets the viewer select swatch labels by hand, then uses `ui.update_checkbox_group()` to drive those same checkboxes from the server. Clear and rebuild actions prove the behavior works both ways.

Use two-way proof when:

- the component exposes a reactive server value and an update function;
- user interaction and server control visibly affect the same state;
- resetting or reversing the state makes the causal relationship clearer.

Avoid adding a server-update button when server updates are unrelated to the hidden feature.

## Choosing the feature

Score candidate features on four questions:

1. Can the first visible reaction begin by second 2?
2. Can the feature produce three meaningful actions without filler?
3. Can the viewer see the contrast or two-way proof in one composition?
4. Is there one short, exact code line that explains the result?

Reject a feature if any answer is no. A visually modest but instantly provable behavior is better than a powerful feature that needs a lecture.

Strong candidates include:

- a default behavior versus one surprising option;
- user state that the server can read or update;
- a control embedded where users expect its effect;
- validation that prevents an observable mistake;
- a component that replaces repeated or stacking UI;
- an accessibility or keyboard behavior that is visible in a recording.

## App composition

- Make the component the largest meaningful object on screen.
- Use one card unless the comparison requires two adjacent or stacked states.
- Do not put an eyebrow, kicker, series label, or oversized marketing headline above the component. The app should begin with the component or a realistic task label; keep the problem-led hook in narration, storyboarding, or later editing.
- Reserve top and bottom space for short-form overlays in vertical recordings.
- Use realistic task content: notes, ticket tags, chart colors, filters, or status changes.
- Keep state labels concrete: `5 lines`, `2 selected`, `Mode: dark`, not `Output updated`.
- End on the state that best communicates the feature, not an empty reset.

## Series visual variety

Build a recognizable series through consistent typography, spacing, pacing, cursor treatment, and code cards—not by repeating the same dark or light canvas in every installment.

Before implementing a series, write a compact visual-direction matrix with one row per video and these columns:

| Video | Backdrop mode | Palette | Composition | Realistic setting |
| --- | --- | --- | --- | --- |

For a series of three or more:

- Include both light and dark or color-led backdrop treatments.
- Avoid letting any one backdrop treatment dominate more than about half the series unless the user requests a fixed brand system or the demonstrated behavior needs a specific mode.
- Vary at least two visual dimensions across adjacent videos: backdrop, palette, component placement, density, or setting.
- Keep phone readability and the component's proof stronger than the desire for variety.

Do not count a recolor as a distinct hidden behavior. Visual variety supports the selected ideas; it does not replace behavioral variety.

## Interaction arc

Plan at least three action → reaction beats. These names are internal production labels for the storyboard and timing plan; they must not appear as on-screen labels or progress indicators in the recorded video.

| Beat | Purpose | Example |
| ---: | --- | --- |
| 1 | Reveal | Type a second line; the field grows |
| 2 | Prove | Add more lines; it keeps growing |
| 3 | Reverse or contrast | Clear it or fill the fixed field |

Opening a menu is setup, not proof. Pointer travel is explanation, not a meaningful action. Each counted beat must change content, selection, layout, focus behavior, validation, or server state.

## Hooks

Lead with the precise frustration or desired outcome. Name the component after the viewer knows why to care.

Weak:

> Did you know Shiny has text areas?

Strong:

> Why is your Shiny text box three lines tall, with a scrollbar doing all the work?

Keep the hook short enough to speak while the first action begins.

## Narration

- Write for a coworker at their desk, not a conference audience.
- Use contractions and varied sentence lengths.
- Describe exact visible labels and values.
- Use at most one metaphor or aphorism.
- Let a plain ending win when it is clearer: “That’s the whole change.”
- Avoid `game-changer`, `seamless`, `powerful`, `unlock`, `elevate`, `dive in`, `let’s explore`, `effortlessly`, and `supercharge`.
- Avoid “It’s not just X, it’s Y” and tidy rule-of-three constructions.

For every recorded workflow, including a silent recording, write `artifacts/narration.txt` with this complete timing envelope:

```text
Synthesize this as a natural, curious tech explainer for a 30-second vertical video.

Audio profile:
A clear developer voice. Brisk, precise, lightly amused, and not salesy.

Scene:
[One sentence describing the visible demo.]

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[60–85 spoken words with 3–6 light delivery tags.]
```

The envelope is required even when no TTS call will be made. It makes the timing target explicit and keeps the file ready for later audio generation.

## Rejection checklist

Choose a different concept when:

- the app needs unrelated buttons to reach three interactions;
- narration explains a change that cannot be seen;
- the code overlay contains setup rather than the decisive line;
- the final frame looks like an ordinary component with no evidence of the trick;
- the demo teaches several parameters;
- the component occupies a small part of a mostly empty canvas.
