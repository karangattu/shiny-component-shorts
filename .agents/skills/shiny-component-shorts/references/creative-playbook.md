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
- Use Mona Sans throughout the app UI and controls. Load `https://fonts.googleapis.com/css2?family=Mona+Sans:wght@400;500;600;700&display=swap` and retain `system-ui, sans-serif` as the fallback stack.
- Do not put a visible app title, page title, eyebrow, kicker, series label, or oversized marketing headline above the component. The app should begin directly with the component or a realistic field/task label; keep the problem-led hook in narration, storyboarding, or later editing.
- Reserve the top 20% and bottom 20% of the frame for later branding. Center the app in the middle 60% band, use 3–5% side gutters, and stretch its primary card or panel across the available horizontal space; do not use a narrow desktop `max-width` that creates dead space.
- Use realistic task content: notes, ticket tags, chart colors, filters, or status changes.
- Keep state labels concrete: `5 lines`, `2 selected`, `Mode: dark`, not `Output updated`.
- End on the state that best communicates the feature, not an empty reset.

Use this CSS geometry as the baseline, adapting only when the component needs more room:

```css
html, body { min-height: 100%; }
body { box-sizing: border-box; margin: 0; padding: 20vh 4vw; }
.app-shell { width: 100%; max-width: none; }
```

## Shiny brand system

Use only colors from the official Shiny Bootstrap preset. Keep one consistent treatment within a video instead of mixing unrelated accents.

- Primary brand color: Shiny blue `#007BC2`.
- Supporting brand and semantic colors: indigo `#4B00C1`, purple `#74149C`, pink `#BF007F`, red `#C10000`, orange `#F45100`, yellow `#F9B928`, green `#00891A`, teal `#00BF7F`, and cyan `#03C7E8`.
- Light mode: `#FFFFFF` or `#F8F8F8` surfaces, `#1D1F21` primary text, `#48505F` secondary text, and `#007BC2` for interactive emphasis.
- Dark mode: `#1D1F21` or `#202020` surfaces, `#FFFFFF` primary text, `#CDD4DA` secondary text, and `#007BC2` or another accessible Shiny semantic color for emphasis.
- Keep normal text at WCAG AA contrast. In particular, do not use cyan, yellow, or orange as small text on a light surface; use them as fills with `#1D1F21` foreground when needed.

## Series visual variety

Build a recognizable series through the same Shiny palette, typography, spacing, pacing, cursor treatment, and code cards—not by repeating the same dark or light canvas in every installment.

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
Synthesize this as a natural, curious tech explainer for a 30-second Shiny component video.

Audio profile:
A clear developer voice. Brisk, precise, warm, and not salesy.

Scene:
[One sentence describing the visible demo.]

Director's notes:
Keep the pace fast enough for a short video. Use small pauses before reveals. Emphasize the surprising behavior. Do not laugh, giggle, chuckle, or add any non-speech vocalization. Do not sound like a corporate tutorial. Read only the transcript below.

Transcript:
[60–85 spoken words with 3–6 intentional pacing or emphasis cues.]
```

The envelope is required even when no TTS call will be made. It makes the timing target explicit and keeps the file ready for later audio generation.

## Rejection checklist

Choose a different concept when:

- the app needs unrelated buttons to reach three interactions;
- narration explains a change that cannot be seen;
- the code overlay contains setup rather than the decisive line;
- the final frame looks like an ordinary component with no evidence of the trick;
- the demo teaches several parameters;
- the component occupies a small part of a mostly empty canvas or leaves avoidable horizontal dead space.
