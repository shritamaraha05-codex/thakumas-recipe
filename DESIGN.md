# Thakuma's Recipe — Design System & Page Guide

> **Product:** ঠাকুমার রান্না · Thakuma's Recipe  
> **Purpose:** Preserve family recipes in the grandmother's own words, translate informal measures into honest ranges, and help the next generation cook hands-free.

This document describes the visual design and interactions implemented in the refined standalone HTML page, including the current Section 05 recipe-book introduction and food reel.

---

## 1. Design direction

The experience should feel like opening a well-loved Bengali family recipe notebook: warm, tactile, personal, and rooted in home cooking. The page combines editorial typography and modern interface components with familiar kitchen materials and motifs.

**Core principles**

- **Warmth over polish:** use parchment, clay, brass, banana-leaf greens, mustard-gold accents, and soft shadows rather than a cold, generic app aesthetic.
- **Memory before measurement:** preserve the grandmother's original phrasing and present quantities as ranges where appropriate, not false precision.
- **Storytelling through food:** photography, Bengali names, recipe excerpts, and transitions make each dish feel like a family memory.
- **Modern interaction, familiar character:** use responsive cards, sliders, tabs, and motion without losing the handmade, heritage-inspired visual language.
- **Clear hierarchy:** keep headings expressive, supporting copy readable, and primary actions visually distinct.

## 2. Brand palette

The page uses CSS custom properties as its base palette.

| Token | Hex value | Intended use |
|---|---:|---|
| `--cream` | `#FBF1DC` | Main page background |
| `--paper` | `#FFF8EA` | Cards, navigation surface, light panels |
| `--red` | `#B3231B` | Primary actions, active tabs, emphasis |
| `--red2` | `#8E1710` | Deep red text and darker red accents |
| `--green` | `#1F4A37` | Heritage green panels and headings |
| `--gold` | `#E0A526` | Highlights, measures, decorative accents |
| `--ink` | `#3A1E12` | Main body text |

**Supporting tones** include warm beige and parchment gradients, muted brown copy, dark terracotta, leaf green, and translucent cream. The main page background has soft radial glows in pale gold and peach. Dark green panels use cream text; the closing CTA uses a subdued red-toned photographic background so its light text remains prominent.

**Shadow language:** warm brown shadows with broad blur and low opacity. Avoid hard black outlines or heavy, high-contrast drop shadows except where a food photograph needs separation from its background.

## 3. Typography

Google Fonts are loaded for three complementary roles:

| Typeface | Role |
|---|---|
| **Tiro Bangla** | Bengali display headings, dish names, quotations, and heritage-led typography |
| **Hind Siliguri** | Bengali and English interface copy, navigation, buttons, labels, and body text |
| **Playfair Display** | English editorial accents, italic words, numeric values, and small uppercase kickers |

Headings use a restrained serif/calligraphic character. Body copy stays clear and moderately sized. Bengali dish names should retain their original spelling and shaping; do not replace them with transliteration in the UI.

## 4. Layout and page structure

The page is a single scrolling landing page with a centered content width of approximately **1,180px** and a standard horizontal content inset of **22px**. Sections are vertically spaced and use rounded panels, botanical details, and warm surface treatments to create rhythm.

### Header / navigation

- Fixed, pill-shaped navigation surface with a translucent cream background, blur, a fine red-tinted border, and warm shadow.
- Left-aligned Bengali brand mark and wordmark.
- Navigation links for the page's explanatory sections and stories.
- Bengali/English language toggle.
- Red primary action for preserving a recipe.
- Hover underline and subtle button shine/magnetic motion on desktop.

### Hero

- Two-column composition: story-led headline and explanation on the left; warm grandmother-cooking image on the right.
- Large Bengali headline uses green with a red-highlighted phrase and a mustard underline reveal.
- Primary red action and a quieter paper-colored secondary action.
- Three compact benefit statements reinforce preserved wording, honest ranges, and personal hand calibration.
- Organic image silhouette, soft shadow, floating waveform treatment, leaves, and small fish/kitchen motifs create depth.

### Section 01 — Her hand was the measuring cup

- Introduces everyday measures such as **এক মুঠো** (a handful), **এক চিমটি** (a pinch), and **যেমন লাগে** (as much as it feels right).
- Three interactive flip cards explain a measure and its approximate interpretation.
- The section communicates that the system should be honest about uncertainty rather than pretending informal measures are exact.

### Section 02 — From her voice to your kitchen

- Dark forest-green rounded band contrasts with the cream page.
- Three connected cards describe the voice-to-cooking pipeline: she speaks, the system understands, and the user cooks.
- Cream recipe/process cards, arrows, a short Bengali instruction preview, and an animated audio waveform make the process tangible.

### Section 03 — Personal hand calibration

- Two-column section explaining measurement uncertainty alongside an interactive range control.
- A user adjusts a slider to represent their own handful; displayed gram values and the range indicator update with the control.
- Use mustard-to-red range styling and a paper-colored control panel to keep the interaction consistent with the wider palette.

### Section 04 — Three steps and recipe preview

- A centered three-step explanation: record, understand, and cook.
- Numbered circular markers, cream cards, and a connected process flow.
- A dark green feature panel includes a phone-style recipe preview and save/share/offline benefits.

### Section 05 — Not just recipes, but family stories

This section is an interactive recipe showcase. It combines the open recipe journal, a featured dish/story card, food-selection buttons, and a horizontal reel of dish cards.

**Opening state**

1. The section begins with the supplied open Bengali Ilish recipe-book illustration centered in the stage.
2. No dish button is selected while the book is being introduced.
3. When the stage enters the viewport, the book holds for **3 seconds**.
4. A layered cooking-steam/smoke effect rises over the stage; the book fades, blurs, and lifts away.
5. The featured food/story presentation appears after the book leaves. The initial featured dish is **ইলিশের ঝোল**.

**Food selection and rotation**

- Eight Bengali dish buttons are available: **ইলিশের ঝোল**, **আলু পোস্ত**, **চিংড়ি মালাইকারি**, **লাবড়া**, **চিতল মাছের মুইঠ্যা**, **কচু বাটা**, **মুড়ি ঘন্ট**, and **কচি পাঁঠার ঝোল**.
- Each dish maps to its own supplied food image and a Bengali memory/quote.
- The featured presentation updates its image, Bengali dish heading, quote, and position indicator together.
- After the book introduction, the featured dish advances automatically at **4-second intervals**.
- Selecting a dish button or reel card changes the featured dish and restarts the automatic rotation cycle.
- Dish transitions use a short smoke treatment and blurred/fading movement; the featured content then rises and settles into place.

**Featured food/story card**

- Two-column desktop composition: food photograph on one side, Bengali story and dish title on the other.
- The food image sits inside a warm, pale frame with a rounded edge and soft shadow.
- A small dish number indicator appears over the photograph.
- Bengali quote styling uses Tiro Bangla with a mustard vertical rule.
- The current responsive overrides stack the photograph and copy on narrower viewports.

**Rolling food reel**

- Eight image-and-name cards form a horizontal track below the featured story.
- Four cards are visible at desktop widths; two are visible at narrower widths.
- The track shifts to keep the selected dish in view, with a selected border, warmer background, and small floral marker.
- The image aspect ratio follows the supplied portrait food-card artwork so the vessel, food, and Bengali nameplate remain visible together.
- Bengali card labels may wrap on very narrow screens rather than being cut off.

### Closing CTA and footer

- The CTA is a large rounded, full-width photographic panel with a muted red overlay and cream/gold typography.
- The background image remains visible but is intentionally subdued to keep the message readable.
- A gold action button provides the visual endpoint.
- Footer content closes the page with compact navigation and brand acknowledgement.

## 5. Components and interaction language

| Component | Visual behavior | Interaction |
|---|---|---|
| Primary button | Deep red gradient, rounded pill, warm shadow, subtle shine | Hover emphasis; magnetic pointer movement on desktop |
| Secondary button | Paper surface with a fine ink outline | Quiet alternative to the primary action |
| Flip card | Rounded paper card with image and title | Hover or tap flips to explanatory back face |
| Process card | Paper surface over deep green band | Subtle lift/tilt on hover |
| Measure selector | Rounded segmented controls | Active segment changes the displayed range |
| Calibration slider | Native range input with red accent | Updates quantity/range display |
| Recipe tab | Rounded pill with light paper default | Active dish uses red fill and white text |
| Food reel card | Portrait image, Bengali label, soft shadow | Selects dish and moves track to reveal it |
| Smoke layer | Soft, blurred white/cream radial clouds | Appears during book exit and food transitions |

## 6. Motion and timing

Motion should feel like steam, a turning page, or a memory returning—not like a fast product dashboard.

| Motion | Current timing / behavior |
|---|---|
| Recipe-book hold | 3 seconds after Section 05 enters the viewport |
| Book exit | Opacity and blur transition with upward movement, scale, and slight rotation |
| Smoke | Multiple staggered blurred clouds rise and fade |
| Featured food reveal | Approximately 0.85-second entrance animation |
| Automatic dish rotation | Every 4 seconds after the book has exited |
| Food reel movement | Approximately 1-second eased horizontal translation |
| Food card rolling accent | Approximately 0.72-second entrance effect |
| Scroll reveals | GSAP/ScrollTrigger fades and lifts `.rv` elements into view |
| Decorative motion | Waveform bars, floating leaf/illustrative elements, particle canvas, and spoon cursor |

Respect `prefers-reduced-motion`: the stylesheet suppresses CSS animations and disables key Section 05 transitions/animations for visitors who request reduced motion. Keep the interaction usable without relying on motion alone to communicate selection.

## 7. Responsive behavior

The main responsive breakpoint is **860px**, with additional refinements at **480px** and **420px**.

- Multi-column hero, calibration, phone, story, card, step, and process layouts collapse to a single column below 860px.
- Desktop navigation links are hidden at the tablet/mobile breakpoint; the language control remains available.
- Section 05 recipe tabs align to the start of the row on smaller screens and can wrap.
- The food reel changes from four visible cards to two visible cards.
- The featured photo and story copy stack vertically on smaller screens.
- The recipe-book image is constrained by viewport height so it remains inside the opening stage.
- At very narrow widths, the featured photo frame and reel-card padding/radii reduce, and Bengali names can wrap onto multiple lines.

## 8. Imagery and asset handling

- Use warm, realistic Bengali food photography and traditional serving pieces: terracotta, brass, stone grinders, banana leaves, and rustic wooden surfaces.
- The Section 05 open recipe-book illustration is the opening visual; the food images are the individual dish artwork used in the featured card and reel.
- Maintain each dish's full visual composition, especially the vessel and its illustrated Bengali nameplate. Avoid `object-fit: cover` where it crops those nameplates; the final reel styles use the artwork's portrait aspect ratio.
- The refined HTML embeds its image assets as Base64 data URLs, so those images travel with the HTML file rather than requiring a separate local image directory.

## 9. Accessibility and usability notes

- Recipe buttons and reel cards use native `<button>` elements.
- Selected recipe buttons expose `aria-pressed` state, and image `alt` text is updated to match the selected dish.
- Focus-visible outlines use mustard gold to remain visible against paper surfaces.
- Preserve legible contrast between dark red/green text and cream surfaces; keep the closing CTA overlay strong enough for its text to remain readable.
- Do not make automatic selection the only way to navigate recipes; manual selection must remain available.
- Motion reduction should not hide content or prevent recipe selection.

## 10. Implementation notes

- **Format:** single standalone HTML document with inline CSS and JavaScript.
- **Fonts:** Google Fonts (`Hind Siliguri`, `Tiro Bangla`, `Playfair Display`).
- **Scroll animation:** GSAP 3.12.5 and ScrollTrigger are loaded from cdnjs.
- **Section 05 state:** dish data is stored in a JavaScript `recipeFoods` array; the selected dish drives the featured image, quote, heading, counter, and selected reel card.
- **Automatic sequence:** an `IntersectionObserver` starts the 3-second book hold when the story stage enters view; the book exit then reveals the first dish and starts the 4-second rotation.
- **No build step:** open the HTML file in a modern browser. Internet access is needed for the externally loaded fonts and GSAP scripts; embedded photographs themselves do not need separate files.

## 11. Content and naming reference

| Index | Bengali dish name |
|---:|---|
| 01 | ইলিশের ঝোল |
| 02 | আলু পোস্ত |
| 03 | চিংড়ি মালাইকারি |
| 04 | লাবড়া |
| 05 | চিতল মাছের মুইঠ্যা |
| 06 | কচু বাটা |
| 07 | মুড়ি ঘন্ট |
| 08 | কচি পাঁঠার ঝোল |

**Content rule:** keep Bengali dish names and grandmother-style memory quotes in Bengali as the primary emotional content. English can support navigation and explanation, but should not replace the Bengali story voice.

---

*This document records the current refined HTML design. Update it when the page's design tokens, section structure, assets, or interaction timings change.*
