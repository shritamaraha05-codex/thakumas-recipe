# 12 Tasks and schedule

Day 1 = **Tue 3 Nov 2026** (assumed today; shift if wrong). Deadline **Tue 10 Nov, 11:59 PM IST**. Target submit **Mon 9 Nov**; the 10th is buffer only. Demo post goes live **Sat 7 Nov** so it has ~3 days of engagement.

Owners: **M** = Mrinmoy (backend, parsing, quantities, LLM, Kaggle). **S** = Shritama (frontend, design, evaluation, demo). **J** = joint. Swap owners if skills differ, then update `.github/CODEOWNERS` and `14_CONTRIBUTIONS.md`.

## Milestones
| End of | Must be true |
|---|---|
| Day 1 | Scaffold runs; API contract agreed; FE renders the fixture; Gnani key works for 1 STT + 1 TTS call; Kaggle gates decided |
| Day 3 | narration -> parse -> ranges -> review screen works end to end in mock mode |
| Day 4 | **All P0 done**: record -> steps -> save -> cook mode -> card export |
| Day 5 | Demo recorded in the morning; posted in the evening |
| Day 6 | P1 items that are green; **feature freeze at night** |
| Day 7 | Bug bash, README, ledger and statement final; **submit** |
| Day 8 | Buffer only |

## Mrinmoy
| ID | Task | Day | Depends | Done when |
|---|---|---|---|---|
| M1 | Repo scaffold, config, health, pytest + ruff | 1 | | `uvicorn` runs; `/api/health` ok; CI-lite script passes |
| M2 | Gnani gateway: STT (lock, retry), TTS, mock mode, `api_usage`, **measure credit cost per call** | 1-2 | M1 | 5 test calls logged; credits per second/char written in `07` |
| M3 | DB schema + repo layer | 1-2 | M1 | `03_DATA_MODEL.md` schema applied; CRUD tests |
| M10 | **Kaggle-Evon timebox (2 h)** | 1 | | Decision row added in `08` decision log |
| M4 | Parser refactor from prototype + lexicon growth | 2-3 | M1 | 25 spec cases pass, >=60 total |
| M5 | LLM chain: Gemini, Ollama, Evon, cache, replay, breaker | 2-3 | M1 | Falls back to rules when all fail; replay works offline |
| M6 | Ambiguity engine + `/api/parse/resolve` | 3 | M4 | Each trigger in `05` produces a clarification and resolves |
| M7 | Quantity engine: `reference.yaml`, hand profiles, intervals, scaling, start-low | 3-4 | M3 | Unit tests per `06`; unverified rows flagged |
| M8 | Recipes/library/pantry/collections endpoints | 4 | M3 | Contract tests vs `04` |
| M9 | Cook endpoints: command, rescue, `/ws/cook` (P1) | 4-5 | M2, M5 | Command recognised from a 3 s clip; WS after reading Gnani doc |
| M11 | Consent/delete backend | 5 | M3 | Cascade tests |
| M12 | Hardening: error codes, rate limits, logging, `tts_text` | 6 | all | No raw upstream errors reach the UI |

## Shritama
| ID | Task | Day | Depends | Done when |
|---|---|---|---|---|
| S1 | FE scaffold, kantha tokens, layout, stitch line | 1-2 | | Fixture recipe renders with stitch + range bars |
| S2 | Capture UI: record/upload, WAV chunking (reuse prototype), transcript editor, consent modal | 2-3 | M2 | 3-min recording merges into one transcript (mock + live) |
| S3 | Recipe view: steps, bands, grain pour, clarification cards | 3-4 | M6 | All ambiguity kinds answerable |
| S4 | Hand wizard + servings scaler UI | 4 | M7 | Band tightens after a weighing |
| S5 | Cook mode: ring, steam, timers, commands, wake lock | 4-5 | M9 | Two timers + voice next/back work |
| S6 | Library UI, search, collections | 5 | M8 | Filter + pantry search |
| S7 | Share: card PNG, PDF print css, audio player | 5-6 | | 1080x1350 PNG with correct Bengali |
| S8 | **Eval**: collect weighings, harness, report, accuracy page | 2-6 | M7 | `eval/report.md` generated; page shows results |
| S9 | Demo video, posts, README polish, submission form | 5-7 | P0 done | Posted Day 5; submitted Day 7 |

## Joint
| ID | Task | Day |
|---|---|---|
| J1 | Kickoff: agree `04_API.md` + fixture, split folders, set up git identities and CODEOWNERS | 1 |
| J2 | Integration pass (FE on live BE) | 4 |
| J3 | Bug bash, cross-review of each other's P0 code | 6 |
| J4 | Demo rehearsal + interview prep (see `14`) | 6-7 |
| J5 | Submission checklist (see `13`) | 7 |

## Cut line
If M4-M7 are not done by end of Day 3: drop M9 realtime (COK-2), LIB-2/3, SHR-3 to P2. If S3 is not done by Day 4: ship range bars without the grain pour. Never cut: ranges, hand profiles, eval report, consent, card export, mock/offline demo path.

## Daily ritual (15 min)
Standup (what shipped, what blocks), both push, each writes **their own** ledger entry (`contributions/LEDGER.md`), run `pytest -q`, tick the task row here.

## Risks
| Risk | Mitigation |
|---|---|
| Gnani live behaviour differs from docs | Test the live API on Day 1; mock mode; Gemini/rules fallback |
| Credits run out | Measure cost Day 1; cache TTS; budget guard |
| Bengali speech accuracy low | Keyterms, review editor, test on real audio early; report honestly |
| Kaggle fails | 2-hour timebox; Gemini/Ollama |
| Scope too big | Cut line above; P2 is optional |
| One person blocked by the other | Fixture-first frontend; contract tests |
