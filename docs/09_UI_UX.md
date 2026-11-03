# 09 UI/UX: the kantha design system

**Concept.** *Kantha* is Bengal's stitched textile: layers of cloth held together by running stitch. The interface is a cloth; steps hang on a stitch line; every vague measure is shown as a band of uncertainty. The memorable element is the **grain pour**; everything else stays quiet.

## Tokens
| Token | Hex | Use |
|---|---|---|
| --cloth | #14204A | page background |
| --cloth-2 | #1E2E63 | raised panels, inputs |
| --thread | #F2EAD8 | primary text, stitch lines |
| --haldi | #E9B224 | primary action, "yours" basis, active stitch |
| --madder | #C2452D | uncertainty band, warnings (**never as text on --cloth**) |
| --leaf | #5C8F5A | confirmed / calibrated |
| --mist | #AAB4D4 | secondary text |
Type: **Tiro Bangla** (display, step text in cook mode), **Hind Siliguri** (UI/body), fallback `"Noto Sans Bengali", system-ui`. Scale 14/16/18/24/32/48/72; line-height 1.65 for Bengali body. Sentence case, no all-caps labels, no decorative eyebrows.
Radius: 6 px inputs/buttons, none on the stitched cloth edges. Spacing 4-px base. Hit targets >= 48 px in cook mode.

## Signature components
1. **Stitch line**: one SVG `<path pathLength="1">` down the left of the steps; `stroke-dasharray` for the running stitch; the drawn portion follows scroll (`stroke-dashoffset`), and in cook mode advances per finished step.
2. **Grain pour** (canvas 2D, ~120 particles, simple gravity): grains fall into a bowl for a quantity. The pile's settled width/height spans `lo` to `hi`; a translucent madder band marks the uncertainty. `basis:"yours"` turns the band haldi and narrows it. Reduced motion: static pile + band.
3. **Range bar**: thin track 0..1.4xhi with band lo..hi, value text "about 33-44 g", basis tag (`typical`, `typical (unverified)`, `yours`, `exact`).
4. **Hand wizard**: pick unit -> pick ingredient -> heap it in your hand -> weigh on a scale -> enter grams; the band tightens live; list of weighings with remove.
5. **Recipe card** (1080x1350 PNG, drawn via SVG -> canvas): stitched border, title, two columns ("her words" left, ranges right), footer "Narrated by <name>, <date>. Ranges are estimates." Wait for `document.fonts.ready` before drawing so Bengali renders.
6. **Cook mode**: full-screen, one step at a time in Tiro Bangla 48-72 px, steam wisps while a timer runs, listening ring that pulses on speech, big Back/Repeat/Next, multiple timer chips, Screen Wake Lock.

## Screens
Home/Library, Capture (record/upload + review editor + clarification cards), Recipe (steps + bands + servings + hand picker + "tighten this recipe"), Hand profiles, Cook mode, Share (card/PDF/audio), Accuracy page (TRU-2), Consent modal, Settings (language, voice, LLM badge).

```
Recipe screen
| title                     servings [-4+]  hand [Thakuma v]    |
| :  step 1 text                                                |
| :  ek chamoch tel  about 5-15 ml  [====....] typical  [tsp/tbsp?]
| :  step 2 text      [grain pour canvas]                       |
| :  ...                         [Cook hands-free] [Share]      |
```

## Behaviour and copy
Plain verbs ("Weigh your muthi", "Make steps"), no marketing. Errors say what happened and what to do. Empty states invite the action. Clarification cards ask one question with big option buttons.

## Accessibility and quality floor
`prefers-reduced-motion` respected (no pour animation, static stitch); contrast >= 4.5:1 for text; visible focus rings (3 px thread colour); keyboard: arrows/space/Esc in cook mode; `lang="bn"` on Bengali text; responsive from 360 px; no layout shift when fonts load.

## Don'ts
No cream-and-terracotta recipe-blog look, no card grids with identical rounded corners and soft shadows, no gradient washes, no scatter of animations. Spend motion on the stitch and the grain pour only.
