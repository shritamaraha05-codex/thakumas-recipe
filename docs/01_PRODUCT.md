# 01 Product

## Problem
Home recipes are passed on by voice with measures that are not numbers: *muthi, chimti, ek kap, jemon lage*. Writing them down loses the meaning; converting them to grams invents precision that does not exist. A grandchild in another city cannot cook "ek muthi chal" the way she does.

## Users
- **The documenter**: a grandchild/relative recording a family cook narrating while cooking.
- **The cook**: wants to follow a recipe hands-free with sticky hands.
- **The interviewer/judge**: wants real engineering and honest evidence.

## Principles
1. Honest ranges. 2. Ask, don't guess. 3. Her words stay beside our numbers. 4. Your hand is not my hand (hand profiles). 5. Works without the LLM. 6. Consent first.

## Feature catalogue
Priority: **P0** demo-critical, **P1** makes it complete, **P2** stretch (drop first). Area: BE backend (Mrinmoy), FE frontend (Shritama), EV eval/demo (Shritama).

| ID | Feature | Pri | Area | Acceptance criteria |
|---|---|---|---|---|
| CAP-1 | Record/upload long narration, chunked to <=25 s WAV, sequential STT | P0 | FE+BE | 3-min recording yields one merged transcript; no chunk >30 s; one active Gnani request at a time |
| CAP-2 | Transcript review editor; corrections feed keyterm list | P0 | FE+BE | Edited words saved and sent as `keyterms` on next request |
| CAP-3 | Interview mode: app asks follow-ups aloud to fill gaps | P1 | BE+FE | Missing quantity/time triggers a spoken question; answer merges into the step |
| CAP-4 | Two-speaker capture (grandchild asks, cook answers) | P1 | FE+BE | Speaker labels on lines; only cook lines become steps |
| CAP-5 | Handwritten recipe photo via optional vision model | P2 | BE | Photo -> text, then same pipeline |
| UND-1 | Rule parser (lexicon, spelling tolerance, Bengali/Roman/Devanagari) | P0 | BE | Passes `parse_cases.yaml` (>=60 cases) |
| UND-2 | LLM extractor via provider chain, schema-validated | P0 | BE | Invalid/ungrounded output rejected; chain falls back to rules |
| UND-3 | Ambiguity engine + clarification Q&A | P0 | BE+FE | Each ambiguity has question + options; answer recomputes ranges |
| UND-4 | Synonym/regional tables, self-correction ("na na dui chamoch") | P1 | BE | Spec cases 12, 20, 21, 22 pass |
| UND-5 | Nutrition and allergen ranges derived from quantity ranges | P2 | BE | Ranges propagate; labelled estimate |
| QTY-1 | Sourced reference table (`reference.yaml`) | P0 | BE | Every row has `source`, `status`; unverified rows shown as "typical (unverified)" |
| QTY-2 | Hand profiles + calibration wizard | P0 | BE+FE | 1 weighing narrows range (+-15%); >=2 uses observed spread |
| QTY-3 | Servings scaling on intervals | P0 | BE+FE | Scaled ranges = base x factor, rounded sensibly |
| QTY-4 | "Start low, taste, add more" for salt-like items | P0 | BE+FE | Salt/spice/chilli show staged guidance when scaled >1.5x |
| QTY-5 | Unit converter; "which weighing tightens this recipe most?" | P1 | BE+FE | Suggestion ranks (unit, ingredient) by width x occurrences |
| LIB-1 | SQLite library, versions, tags, attribution | P0 | BE+FE | CRUD + version; original transcript retained |
| LIB-2 | Voice pantry search ("chal, dal, alu ache") | P1 | BE+FE | Recipes ranked by ingredient overlap |
| LIB-3 | Collections ("Thakuma's recipes") | P1 | BE+FE | CRUD + filter |
| LIB-4 | Family recipe tree | P2 | FE | Lineage view from attribution |
| COK-1 | Hands-free cook mode: read steps, multiple timers, voice commands | P0 | FE+BE | next/back/repeat/stop by voice and keys; >=2 concurrent timers |
| COK-2 | Realtime listening (no button) via Prisma WebSocket | P1 | BE+FE | Commands recognised within ~2 s while TTS is not playing |
| COK-3 | Numbers spoken as words in TTS | P1 | BE | No raw digits sent to TTS; "2.5" -> "arai" / "আড়াই" |
| COK-4 | Kitchen rescue by voice ("nun beshi hoye gelo") | P1 | BE | LLM answer with guardrails, flagged as advice |
| COK-5 | Offline PWA cook mode with cached audio | P2 | FE | Works with network off after first load |
| SHR-1 | Recipe card PNG export (stitched border, her words + ranges) | P0 | FE | 1080x1350 PNG with Bengali text rendered correctly |
| SHR-2 | PDF export | P1 | FE | Print stylesheet -> PDF |
| SHR-3 | "Thakuma reads it to you" audio recipe | P1 | BE+FE | Timbre audio of the full recipe, cached |
| SHR-4 | Cloned-voice reading (Gnani voice cloning) | P2 | BE | Only with `voice_clone` consent + verification phrase |
| TRU-1 | Evaluation harness + dataset | P0 | EV | `eval/report.md` generated from data |
| TRU-2 | In-app "How accurate is this?" page | P1 | FE+EV | Shows coverage/width from latest run |
| TRU-3 | Consent and privacy | P0 | BE+FE | See `11_PRIVACY_CONSENT.md` |
| PLT-1 | LLM provider chain, cache, replay | P0 | BE | Chain order configurable; replay works offline |
| PLT-2 | Gnani gateway, budget log, mock mode | P0 | BE | `api_usage` rows written; `GNANI_MOCK=1` works |
| PLT-3 | Evon-on-Kaggle experiment | P1 | BE | Decision recorded within the timebox |

## Non-goals
Accounts/auth, mobile app, social network, nutrition accuracy claims, medical or allergen advice, dialects beyond Bengali/Hindi/English.

## Success measures (targets, not claims)
Post-calibration range coverage 80-90% on our own weighing set with width reported; parser item F1 on the case set; end-to-end demo works offline from fixtures; every P0 acceptance criterion demonstrated.
