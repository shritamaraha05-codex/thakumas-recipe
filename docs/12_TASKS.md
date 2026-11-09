# 12 — Execution plan and task board

**Project:** Thakuma's Recipe (ঠাকুমার রান্না)  
**Team:** Mrinmoy (backend / parsing / integrations) + Shritama (frontend / UX / evaluation / demo)  
**Plan starts:** Tuesday, 3 November 2026  
**Target submission:** Monday, 9 November 2026  
**Hard deadline:** Tuesday, 10 November 2026, 11:59 PM IST. The 10th is a recovery/submission buffer, not a development day.

This replaces the previous broad task list. Work from the task IDs below. A task is complete only when its acceptance check passes and its evidence is linked in the PR or commit.

---

## 1. What we are actually shipping

The week is too short to build every feature in `01_PRODUCT.md`. We will ship one complete, believable user journey:

1. User signs in.
2. User enters or reviews a Bengali transcript.
3. Backend parses the recipe.
4. User saves the recipe.
5. Recipe appears in that user's library.
6. User can close and reopen the application.
7. Saved recipe remains available.
8. Another account cannot access that recipe.
9. User can edit, version and delete their own recipes.

That nine-step list is the **minimum release journey and the P0 acceptance gate** for persistence. Cook mode (Day 4) is still demo scope, but it is not required for the persistence gate; the sign-in → transcript → parse → save → library → restart journey must be green first.

**Architecture correction (2026-11-08):** storage is **Supabase PostgreSQL** and accounts are **Supabase Auth** — not SQLite, and no custom password handling anywhere. Frontend is **React** (Vite) with the Supabase Auth client; the frontend never writes to the database directly, it always goes through FastAPI with the user's access token. Schema: `docs/03_DATA_MODEL.md`; API: `docs/04_API.md`. M-18A/M-18B/M-19/M-20 below replace the old SQLite M-18/M-19/M-20.

### Must ship (P0)

- FastAPI app starts and health endpoint works.
- Mock mode works without credentials; no automated test calls an external API.
- Bengali / Roman Bengali normalisation, basic step segmentation, quantities, ingredients and duration extraction.
- Quantity ranges from a reference table; exact metric quantities remain exact; unverified estimates are labelled.
- At least two clarification types: ambiguous `chamoch` (tsp/tbsp) and unknown/uncalibrated `cup` (cup type). A user answer must recompute the result.
- Prisma STT integration for short clips and sequential chunk upload for longer clips; transcript editing before parsing.
- Supabase Auth sign-in/sign-up with session persistence and logout (frontend), verified access tokens on every protected route (backend).
- Recipe save / list / open / version / delete on Supabase PostgreSQL, scoped to the signed-in owner; the saved recipe survives an app restart and is invisible to every other account.
- Cook mode with step navigation, repeat, timers and speech playback/fallback.
- Consent before capturing another person's voice; audio is not retained by default.
- Automated tests, an evaluation note with sample size and limitations, working demo video, public post and submission materials.

### Moved to postponed (2026-11-08 planning correction — do not start until the journey above is green)

- Personal measurement calibration (M-17, S-12; QTY-2) and the weighing repository (M-17).
- Full person / profile / consent management (M-18's original person/consent scope and the people/consent API).
- Recipe scaling, including servings UI and salt-like staged guidance (S-13; QTY-3, QTY-4).
- Pantry search (LIB-2).
- Collections (LIB-3).
- Advanced evaluation dashboard (TRU-2).

**Preserved and not touched by this correction:** the parser (M-05..M-09), the Gemini provider (M-10) and the evaluation harness (M-11) are complete and stay exactly as they are. Rows below are marked `POSTPONED` where their only purpose was postponed work.

### Explicitly not on the critical path (P2 — do not start before P0 works)

- Evon / Kaggle hosting or tunnel, realtime STT WebSocket, two-speaker diarisation, OCR/photo import, nutrition, family tree, voice rescue, sophisticated animations, and a full analytics dashboard.
- If all P0 checks are green by Sunday evening, choose **one** small optional feature. Do not start several half-finished features.

### Scope decisions

- The `prototype_v0/` parser is a starting point, not an architecture to preserve. First run its tests; then move useful logic into `backend/app/parse/` and add tests as it is refactored.
- Build the frontend against `docs/fixtures/parse_result.sample.json` on Day 1. It must not wait for a live backend.
- Build and test against `GNANI_MOCK=1` first. A real Gnani request is a manual smoke test only.
- Use Prisma as the essential Gnani integration. Timbre is included for the cook-mode demo if the live endpoint/credits permit; browser speech is the fallback. Never claim a model worked unless a real call was made and heard/checked.
- The frontend is React (Vite) and uses the Supabase Auth client for sign-in/session. It calls FastAPI for every read and write and never writes to Supabase directly (no bypassing business logic, no privileged keys in `VITE_` variables or the bundle). First useful path: Sign in → Capture/Review → Recipe → Library, then Cook.

---

## 2. Who owns what

| Person | Owns implementation | Does not wait for | Must hand over |
|---|---|---|---|
| **Mrinmoy (M)** | `backend/`, parser, units, Gnani gateway, Supabase PostgreSQL + Supabase Auth, API contracts and backend tests | Frontend; Shritama uses the fixture | OpenAPI/API responses, mock endpoints, test command, known limitations |
| **Shritama (S)** | `frontend/`, UI, capture flow, evaluation data/report, demo assets and user-facing docs | Backend; start with fixture + mock API adapter | Working screens, sample data, evaluation evidence, demo video/post links |
| **Both (J)** | API contract freeze, integration, bug bash, demo rehearsal, contribution and submission checklist | — | A runnable build and accurate individual contribution evidence |

**Folder boundaries:** M owns `backend/**`; S owns `frontend/**` and `eval/**`. Shared changes to `docs/04_API.md`, fixtures, `README.md` and `docs/12_TASKS.md` are agreed in a short joint review. Neither person commits under the other's Git identity.

### Required branch and commit convention

- Mrinmoy: `m/<task-id>-short-name`
- Shritama: `s/<task-id>-short-name`
- Prefix commits `[BE]`, `[FE]`, `[EV]`, `[DOC]` or `[JOINT]` and include the task ID.
- One task or tightly related subtask per PR. Other teammate reviews it. Keep commits attributable; do not squash away individual work.
- Each person updates only their own contribution ledger entry on the day the work is done.

---

## 3. The first 2 hours — do these in this order

This is the answer to “who starts what?” Both people start in parallel after the first 20-minute alignment.

| Time from kickoff | Mrinmoy | Shritama | Joint output |
|---|---|---|---|
| 00:00–00:20 | Join repo, verify Python, inspect `prototype_v0/` | Join repo, inspect `docs/fixtures/` and existing prototype UI | Confirm scope above, deadline, primary Gnani account/credits and each person's Git identity |
| 00:20–00:50 | Run prototype tests; record failures before changing code | Turn fixture into a list of fields the UI must display; sketch Capture / Review / Recipe / Cook states | Freeze the response shape in `docs/04_API.md`; no adding fields casually |
| 00:50–01:30 | Create FastAPI scaffold, config and `/api/health` | Create frontend shell and render the fixture as a recipe | Agree endpoint names and mock behaviour |
| 01:30–02:00 | Add `/api/parse` returning a fixture/mock response; add first contract test | Add manual transcript input and a Parse button that uses fixture/mock data | Both run the same end-to-end fake flow; log blockers and split next tasks |

**Do not spend the first two hours on** Kaggle, Evon, WebSockets, logo polishing, animations, deployment or a complete database. The first visible win must be: enter a sample transcript → click Parse → see a recipe screen populated from the fixture.

### Day 1 exit gate (Tuesday 3 Nov)

- [x] `uvicorn backend.app.main:app --reload` starts. (backend)
- [x] `GET /api/health` returns `ok: true`. (backend)
- [x] `pytest -q` runs without network access. (backend: 36 passed, 5 of them the frozen prototype suite)
- [ ] Frontend opens and renders the fixture correctly. (S)
- [ ] Manual transcript input reaches the mock `/api/parse` endpoint. (needs S-04 UI; endpoint itself verified)
- [ ] Both teammates can identify their next three task IDs without waiting for one another.

If any of these fail, fix them before adding features.

**Backend status (2026-11-03): M-01, M-02, M-03, M-04 done.** `docs/PROTOTYPE_AUDIT.md` records the prototype pass/fail state and reusable functions; `backend/` has an offline FastAPI app with `GET /api/health` and a fixture-backed mock `POST /api/parse` (contract in `docs/04_API.md`). Evidence: `pytest -q` = 36 passed, `ruff check .` clean. Frontend tasks S-01..S-04 and J-02 remain; no live Gemini/Gnani/SQLite work was started.

---

## 4. Daily plan and task cards

Task sizes are intended to be roughly 30 minutes to 3 hours. A task must not be left as “build feature”; its output and check are specified.

### Day 1 — Tue 3 Nov: runnable skeleton + shared contract

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| J-01 | Both | Kickoff, confirm two-person team/primary registrant, check who has the 5,000 credits, verify each Git identity and create branches | — | Both identities verified; team scope agreed |
| M-01 | M | Run `prototype_v0` tests and inspect `app.py`, `core.py`, requirements. Write findings in `docs/PROTOTYPE_AUDIT.md`; do not refactor blindly | J-01 | Existing pass/fail state and reusable parser functions recorded |
| M-02 | M | Create `backend/app/main.py`, `config.py`, package files and dependency list | J-01 | FastAPI starts locally |
| M-03 | M | Add `/api/health`, `/api/parse` mock response and pytest setup | M-02 | Health test and parse contract test pass |
| M-04 | M | Add Pydantic response models matching `docs/fixtures/parse_result.sample.json` | J-01 | Fixture validates; unknown response shape is not invented |
| S-01 | S | Sketch the four screens and interactions in `docs/UI_FLOW.md` | J-01 | Each screen has one primary action and a defined empty/loading/error state |
| S-02 | S | Create `frontend/index.html`, CSS tokens, responsive app shell and navigation/state container | J-01 | Opens locally on desktop and phone width; no build step |
| S-03 | S | Implement fixture loader and recipe renderer (steps, ingredients, ranges, clarification, basis labels) | S-02 | Fixture renders without backend |
| S-04 | S | Add manual transcript textarea + Parse button + sample recipe button | S-02, S-03 | Button shows a fixture result and loading/error states |
| J-02 | Both | Run the first fake end-to-end path together; write any contract changes before proceeding | M-03, S-04 | The UI displays the fixture response from a local mock/API adapter |

### Day 2 — Wed 4 Nov: parsing foundation + real audio capture

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-05 | M | Extract normalisation into `backend/app/parse/normalize.py`: Bengali digits, case, punctuation, spacing and unit aliases | M-04, M-01 | Unit tests cover Bengali digits, decimals, punctuation and Roman Bengali |
| M-06 | M | Extract step segmentation into `parse/segment.py`: sentence/connector boundaries and stable step numbering | M-05 | At least 12 segmentation tests pass; original wording is preserved |
| M-07 | M | Extract number, unit, ingredient and duration lexicons into `parse/lexicon.py` | M-05 | Each alias maps to one canonical value; unknown words are not silently mapped |
| M-08 | M | Implement first deterministic rule parser in `parse/rules.py` and `parse/schema.py` | M-06, M-07 | `ek muthi chal`, `ek chimti nun`, `dui chamoch tel`, `dosh minute` produce expected structured items |
| M-09 | M | Create `backend/tests/parse_cases.yaml` with at least 30 cases now; add a small test runner | M-08 | All starter cases pass; failures are visible by case ID |
| M-10 | M | Make one manual real Prisma STT request and one Timbre TTS request; record model, request settings, latency, credits if dashboard exposes them, and errors in `docs/07_GNANI_INTEGRATION.md` | M-02, J-01 | Smoke-test result recorded honestly; stop after the test, no retry loops |
| M-11 | M | Implement Gnani client wrapper with timeout, one retry for 429/5xx, global request lock and `GNANI_MOCK=1` | M-10 | Mock tests pass; no test reaches the network; missing key returns a useful error |
| S-05 | S | Build capture screen with explicit consent prompt, record/upload controls and manual-text fallback | S-02 | User can deny consent and continue with manual text; no audio is saved locally by the app |
| S-06 | S | Implement browser audio conversion to mono 16 kHz PCM WAV and 25-second chunks | S-05 | A 60-second test file becomes sequential chunks no longer than 25 seconds |
| S-07 | S | Upload chunks sequentially via API adapter; merge transcript responses in order | S-06, M-11 | Mock mode produces one merged transcript; no concurrent STT calls |
| S-08 | S | Add transcript review editor, retry/edit state and keyterm list from corrections | S-07 | User edits transcript and submits the edited text, not the original, to Parse |
| S-09 | S | Create `eval/cases/cases.csv` header, weighing protocol and consent notes; start collecting the first real cases while implementation continues | J-01 | CSV schema and protocol exist; every real measurement has person/case/replicate metadata and consent |
| J-03 | Both | Test full capture → merged transcript → editable transcript → parse in mock mode | M-08, M-11, S-08 | No external service required; transcript can be edited before parsing |

**Backend status (2026-11-04): M-05 done.** `backend/app/parse/normalize.py` implements the normaliser (pure functions, offline); 31 unit tests cover Bengali digits/decimals, Devanagari digits, Roman Bengali, mixed script, punctuation, whitespace, negations, unit aliases and original-text preservation. Evidence: `pytest -q` = 67 passed, `ruff check .` clean.

**Backend status (2026-11-04): M-06 done.** `backend/app/parse/segment.py` segments `NormalizedText` into ordered `Segment`s (sentence punctuation + connectors only; conditionals, commas and negations never split; `conditional`/`connector` metadata preserved). 34 unit tests include a full Chitol Macher Muitha narration regression (`backend/tests/fixtures/chitol_macher_muitha_narration.txt`) verifying meaningful boundaries, source spans, ordering and complete coverage. Evidence: `pytest -q` = 101 passed, `ruff check .` clean.

**Backend status (2026-11-06): M-07 done.** `backend/app/parse/lexicon.py` implements the offline Bengali/Roman-Bengali vocabulary layer (ingredient / measure / number / duration groups, 79 canonical entries) with deterministic exact -> alias -> numeric -> conservative-suffix -> longest-phrase matching, original-surface and source-span preservation, ambiguity metadata (plain `chamoch`, uncalibrated `cup`), and fuzzy candidates exposed only through `suggest` (never applied during a scan). 119 unit tests cover every required group, spelling variants, numeric/spoken ranges, Devanagari case 22, suffix safety (`মুইঠা` is never a handful), unknown-word preservation and the Chitol Macher Muitha narration regression. Evidence: `pytest -q` = 220 passed, `ruff check .` clean.

**Backend status (2026-11-06): M-08 done.** `backend/app/parse/schema.py` defines the internal provenance-rich `IngredientMention` / `Quantity` / `Duration` / `RecipeStep` / `ParseResult` dataclasses (reusing `models.Clarification`, `Source`, `ParserMode`). `backend/app/parse/rules.py` exposes `parse_rules(NormalizedText) -> ParseResult` and `parse_rules_text(str)`; it consumes M-05/M-06/M-07 unchanged, attaches a quantity to an ingredient only on direct adjacency, records durations separately (never converting to seconds), preserves original surfaces and spans, emits deterministic `unit_spoon_N` / `unit_cup_N` clarifications, and never fuzzy-corrects or invents values. 42 tests cover all required quantity kinds, ambiguity, negation/conditional preservation, source spans, determinism and the Chitol Macher Muitha narration. Public `/api/parse` is untouched. Evidence: `pytest -q` = 262 passed, `ruff check .` clean.

**Backend status (2026-11-06): M-09 done.** `POST /api/parse` now runs the real M-08 rules parser instead of returning the sample fixture. New `backend/app/parse/serialize.py` converts the internal result to the public Pydantic models (adding `kind`, `raw_unit`, `classifier`, `orig_start`/`orig_end`, step spans and a `Duration` model, per `docs/04_API.md`); modes are `rules` (implemented), `auto` (resolves to the first implemented provider in `LLM_CHAIN` -> `rules`) and an explicit `llm` which returns `501 LLM_UNAVAILABLE` rather than silently falling back. Whitespace-only text is rejected, `hand_profile_id`/`servings` remain unimplemented-but-accepted, and `docs/fixtures/parse_result.sample.json` is now the verbatim live response for a documented narration (test-enforced). Evidence: `pytest -q` = 277 passed, `ruff check .` clean.

**Backend status (2026-11-07): M-10 done (Gemini provider integration).** Added the first real LLM provider on the official `google-genai` SDK (`requirements.txt`), configured by `GEMINI_API_KEY` and `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). New `backend/app/providers/` holds a replaceable provider protocol plus `gemini.py`; `backend/app/parse/llm_schema.py` is the structured-output schema and `backend/app/parse/llm.py` builds request-local evidence ids from the unchanged M-05/M-06/M-07 pipeline, validates every selected id (existence, category, same-segment, no duplicates) and constructs the existing internal `ParseResult` from verified evidence only. Gemini never supplies wording, numbers, labels or offsets. `mode="llm"` uses Gemini, `mode="rules"` stays fully offline and deterministic, and `mode="auto"` walks `LLM_CHAIN` (e.g. `gemini,rules` selects Gemini first); an explicit `llm` request is never downgraded. Metadata is truthful (`parser_mode`, `llm_provider`, `mock=false`). Missing key -> `503 LLM_UNAVAILABLE`, timeout -> `504 UPSTREAM_BUSY`, rate limit -> `503 UPSTREAM_BUSY`, provider/invalid-output -> `502 UPSTREAM_ERROR`; raw provider messages, keys and transcripts are never exposed. All provider tests run offline with an injected fake provider / mocked SDK. Note: the Day-2 **M-10** row above is the Gnani Prisma/Timbre smoke test; it is a separate task and is not claimed here. Evidence: `pytest -q` = 322 passed, `ruff check .` clean.

Manual Gemini smoke test (not run automatically, no key needed to run the suite): set `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-3.5-flash-lite`, start `uvicorn backend.app.main:app`, then `POST /api/parse` with `{"text": "<chitol macher muitha narration>", "mode": "llm"}` and inspect the JSON for ingredients, quantities, durations, ambiguity and original wording.

**Backend status (2026-11-07): M-11 done (parser evaluation harness).** Added `backend/evaluation/` with a 21-case curated golden dataset (`dataset/recipes.jsonl`, `DATASET_VERSION=1.0.0`), a parser-independent evaluation schema (`schema.py`), a loader that rejects duplicate ids and evidence phrases that are not literal transcript substrings (`loader.py`), metrics (`metrics.py`), JSON + Markdown reports (`report.py`) and a CLI (`runner.py`). `python -m backend.evaluation.runner --provider rules` is fully offline; Gemini evaluation requires `--confirm-live-api`, valid credentials, makes one request per case with no retries, and reports failed cases as not evaluated instead of substituting rules. Metrics cover ingredient P/R/F1, quantity accuracy/association/range/unit/vague/taste, duration recall/value/unit and misattachments, clarification preservation, negative expectations, evidence grounding and unsupported-assertion rate (kept separate from F1). Rules baseline on the golden set: ingredient P/R/F1 = 100%, quantity accuracy 17/18 (94.4%, the miss is the documented `panch-chhoy ta lonka` classifier case), duration recall 100%, clarifications 3/3, negatives 10/10, evidence grounding 100%, unsupported 0/47. No production parser behaviour changed. Evidence: `pytest -q` = 344 passed, `ruff check .` clean. See `docs/15_EVALUATION_HARNESS.md`.

**Backend status (2026-11-08): M-18A, M-18B, M-19 and M-20 done (Supabase auth, persistence and recipe API).** Added `backend/app/auth/` (JWKS verification with cached signing keys, legacy HS256 via Supabase Auth's `/user` endpoint, `get_current_user`, consistent `401 UNAUTHORIZED`), `backend/app/db/` (a per-request `postgrest` client carrying the user's JWT, an owner-scoped `RecipeRepository`, and typed request/response schemas), `backend/app/routers/recipes.py` (`GET /api/me` plus recipe create/list/get/version/delete), and `supabase/migrations/0001_initial_schema.sql` (`profiles`, `recipes`, `recipe_versions`, cascades, indexes, RLS policies, the sign-up profile trigger and atomic RPCs including a `FOR UPDATE` row lock for version numbers). A minimal React + Vite app under `frontend/` wires Supabase Auth (sign-up/in/out, session persistence), parse → save, the personal library, versioned edit and delete. `POST /api/parse` and `GET /api/health` stay public and the parser/provider code is unchanged. Tests use locally generated RSA keys + a mocked JWKS `/user`, an in-memory RPC fake, and static migration checks; no test calls Supabase or Gemini. Evidence: `pytest -q` = 427 passed, `ruff check .` clean, `npm run build` succeeds. Live two-user Supabase verification is documented in the README and is **not yet claimed**.

**Day 2 stop rule:** If live Prisma is not working after the smoke test and one focused fix, keep mock/manual capture working and investigate the upstream issue separately. Do not block parser or UI work on the provider.

### Day 3 — Thu 5 Nov: honest quantity ranges + clarification

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-12 | M | Move quantity estimates into `backend/app/units/reference.yaml`; add `source` and `status` to every row | M-08 | Missing source/status causes a test failure; estimated rows are marked unverified |
| M-13 | M | Implement `units/ranges.py` for exact units and low/high intervals | M-12 | Exact g/kg/ml/litre remain exact; vague units return intervals, never a single fake-precise value |
| M-14 | M | Implement ingredient classes and range lookup fallback | M-12, M-13 | Rice, flour, salt, liquid and unknown ingredient paths have tests |
| M-15 | M | Implement ambiguity detection for spoon and cup, with stable IDs/questions/options | M-08, M-13 | Ambiguous spoon/cup creates clarification rather than choosing a default |
| M-16 | M | Implement `/api/parse/resolve` as a stateless recomputation from draft + answers | M-15 | Selecting tsp/tbsp or cup type changes the parsed result and clears resolved clarification |
| M-17 | M | **POSTPONED** (2026-11-08 correction) hand profile + weighing repository/service; one weighing uses a visibly labelled personal interval | M-13 | Weighing persists; recalculation changes only the matching profile/unit/ingredient range |
| S-10 | S | Build Recipe Review screen: ordered steps, ingredient chips, range bars, raw phrase and `typical/yours/exact` labels | S-03, M-04 | UI displays all fields from response; no frontend-invented quantity values |
| S-11 | S | Build clarification cards with answer options and Resolve action | S-10, M-16 | User answers each clarification and sees updated ranges |
| S-12 | S | **POSTPONED** (2026-11-08 correction) hand calibration wizard (choose unit → enter weighed amount → save → refresh range) | S-10, M-17 | A measurement updates only that user's matching range |
| S-13 | S | **POSTPONED** (2026-11-08 correction) servings control and display scaled low/high interval, preserving unit and rounding | S-10, M-13 | 2x servings doubles both bounds; `start low, taste, add more` appears for scaled salt/spice/chilli |
| S-14 | S | Continue evaluation collection toward the target in `10_EVAL_PLAN.md` (25 cases × 3 replicates); if time/access prevents this, report the actual smaller n as a pilot | S-09 | Measurements include unit, ingredient, cook/person, replicate and date; do not fabricate missing data |
| J-04 | Both | Integrate parser + ranges + clarifications in the real UI (calibration and scaling are postponed) | M-16 | A typed Bengali/Benglish sample becomes editable steps with labelled ranges and answerable ambiguity |

### Day 4 — Fri 6 Nov: Supabase auth + persistence + cook mode + P0 integration

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-18A | M | **DONE 2026-11-08** — Supabase project + database foundation: project configuration (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `FRONTEND_ORIGINS` in `.env.example`), `supabase/migrations/0001_initial_schema.sql` creating `profiles`, `recipes`, `recipe_versions` with foreign keys/indexes, RLS ownership policies, the sign-up trigger and atomic RPCs, plus an honest Data API health report | M-02 | A fresh Supabase database initialises from the migration; tables/relationships verified; RLS policies present; no secrets committed |
| M-18B | M | **DONE 2026-11-08** — Supabase Auth integration: access-token verification (JWKS signature/`kid`/algorithm + `exp`/`iss`/`aud`, legacy HS256 via Supabase `/user`), `get_current_user` deriving identity from `sub`, profile resolution, protected `GET /api/me`, consistent 401 behaviour | M-02, M-18A | A valid access token identifies the correct user; missing/invalid/expired tokens return `401 UNAUTHORIZED`; ids never come from untrusted input; no custom password auth |
| M-19 | M | **DONE 2026-11-08** — User-scoped recipe repository on Supabase PostgreSQL: create, list, get, add version, get version, delete. Each request uses a client carrying the user's JWT and the RPCs check `p_owner_user_id = auth.uid()`; no service-role key. Exact transcript and complete JSONB draft are preserved | M-18A, M-18B | Two users cannot read or modify each other's recipes; versions are retained; deletion cascades; data survives a restart (live check) |
| M-20 | M | **DONE 2026-11-08** — Protected recipe API: `POST /api/recipes`, `GET /api/recipes`, `GET /api/recipes/{id}`, `PUT /api/recipes/{id}`, `DELETE /api/recipes/{id}`, each behind the M-18B auth dependency and owner-scoped, plus a minimal React/Vite auth + library frontend | M-19, M-18B | All endpoints require authentication; every operation is owner-scoped; parser APIs unchanged; save/open/edit/delete journey wired in `frontend/`; live restart check documented |
| M-21 | M | Add `/api/speak` with Timbre client, text/voice/language cache and browser-speech fallback signal | M-11 | Mock TTS returns audio; live TTS result is verified manually or clearly marked unavailable |
| M-22 | M | Add cook command normaliser for keyboard/button commands; keep voice command clips optional | M-08 | `next`, `prev`, `repeat`, `stop` map to stable command names |
| S-15 | S | Supabase Auth + recipe library: sign-in/sign-up screen with the Supabase Auth client (Google login if enabled on the project, email/password otherwise), session persistence across reloads, logout; save recipe flow (title + tags from a parse result), library list, open recipe, delete recipe. The frontend forwards the access token to protected FastAPI routes and never writes to the database directly | S-10, M-20, M-18B | A signed-in user saves a recipe, sees it in the library after closing and reopening the app, opens and deletes it; another account's recipes are never listed or openable |
| S-16 | S | Build Cook Mode: one step at a time, large Next/Back/Repeat buttons, progress indicator and keep-screen-awake attempt | S-15 | Navigation works by touch and keyboard; does not require microphone permission |
| S-17 | S | Add one or more timers with visible countdown and completion alert | S-16 | Two timers can run independently; timer state does not reset on step navigation |
| S-18 | S | Connect step speech playback to `/api/speak`; fall back to browser speech and visible text | S-16, M-21 | A step can be heard or read; failure never leaves a blank screen |
| S-19 | S | Create a clean recipe share-card layout (print CSS first; PNG only if reliable Bengali rendering is available) | S-10 | Recipe title, original phrase, steps and range labels are legible; no false exact numbers |
| J-05 | Both | P0 integration gate: clean install, fresh Supabase database, sign in, mock capture, parse, save, reopen (restart) and cook | M-20, M-18B, S-18 | Entire journey completes on one laptop without manual code edits between steps, and the minimum release journey in §1 is green |

### Day 5 — Sat 7 Nov: evidence + demo + public post

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-23 | M | Add consistent API errors, input validation, file-size/duration checks, timeouts and safe logs | M-11, M-20, M-21 | Invalid input returns documented error envelope; audio transcription is rejected until required consent exists; no secrets/audio/transcripts leak into logs |
| M-24 | M | Add parser regression tests to reach 60+ cases; fix the highest-frequency Bengali/Roman Bengali failures | M-09, M-13, M-16 | 60+ tests run offline and pass; failures are not hidden by broad exception handling |
| M-25 | M | Add API usage logging and a configurable daily budget guard only after actual credit measurement | M-10, M-11 | Usage records capture calls; unknown costs stay `NULL`, not guessed |
| S-20 | S | Implement and run the offline evaluation harness using `eval/cases/cases.csv` and the range/parser functions; produce `eval/harness.py` (or equivalent documented script), `eval/report.md` and `eval/latest.json` | S-09, S-14, M-13 | Report includes n, protocol, coverage, interval width, errors and limitations; no fabricated measurements |
| S-21 | S | Run 5 end-to-end scenarios: Bengali script, Roman Bengali, mixed English, ambiguity, personal calibration | J-05 | Record pass/fail and screenshot/video evidence for each scenario |
| S-22 | S | Finalise 60-second demo storyboard, English subtitles and consent-safe sample narration | S-20, S-21 | Every shown value exists in the running app or actual evaluation output |
| S-23 | S + M | Record the working demo, with a second mock/offline fallback take | J-05, S-22 | Video clearly shows Prisma use if verified, transcript correction, ranges, calibration, cook mode and team contribution |
| J-06 | Both | Publish public LinkedIn or X demo post with required hashtags and Gnani AI tag; save the live URL | S-23 | Post opens when logged out; no bought engagement, pods, swaps or misleading model claims |

**Demo rule:** If a feature is not working live, do not edit the video to imply it is. Show the fallback honestly and state the limitation.

### Day 6 — Sun 8 Nov: hardening + interview readiness

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-26 | M | Fix only P0/P1 bugs from the scenario list; add regression tests for each fix | S-21 | Every fixed bug has a test; no unrelated refactor |
| M-27 | M | Review parser, range maths, schema, Gnani fallback and privacy; prepare a 1-page architecture explanation | M-26 | Mrinmoy can explain each backend decision without notes |
| S-24 | S | Review mobile layout, keyboard accessibility, empty/loading/error states and Bengali font fallback | S-21 | Capture, Review and Cook are usable at phone width |
| S-25 | S | Polish evaluation report and accuracy visual; add limitations and worst failures | S-20 | Report states exact sample count and avoids generalising beyond the sample |
| S-26 | S | Prepare demo narration, UX rationale and the list of what the demo does not prove | S-23 | Shritama can explain design, interaction, evaluation and limitations without notes |
| J-07 | Both | Cross-review the other person's implementation and practise individual interview questions | M-27, S-26 | Each can explain the whole product and accurately identify the other person's work |

**Optional feature gate:** Only after every P0 acceptance check, public demo post and evaluation report are complete may the team select one optional item. Preferred order: push-to-talk cook commands → one useful library improvement. Do not start WebSocket realtime, OCR or Evon this late.

### Day 7 — Mon 9 Nov: release candidate + submission ready

| ID | Owner | Task / exact output | Depends on | Acceptance check |
|---|---|---|---|---|
| M-28 | M | Fresh-clone verification: install, configure mock mode, start app, run tests; fix README backend commands | M-26 | Fresh clone works with no undocumented local file or secret |
| M-29 | M | Final review of API docs, `.env.example`, dependency list and secret scan | M-28 | No `.env`, key, private recording or unconsented data committed |
| S-27 | S | Finalise README screenshots, UI flow, setup steps and honest limitations | S-24, S-25 | New reader can run the project and understand the demo without asking the team |
| S-28 | S | Complete Shritama's own contribution statement/ledger and collect evidence links | S-23, S-27 | Entries map to PRs, commits, files, tests, measurements or demo work |
| M-30 | M | Complete Mrinmoy's own contribution statement/ledger and collect evidence links | M-27, M-29 | Entries map to PRs, commits, files, tests or integration evidence |
| J-08 | Both | Release tag, final demo/post link check, Gnani model/API list, project description and submission form draft | M-29, S-27, M-30, S-28 | All submission fields have verified values and both people agree |
| J-09 | Both | Submit on 9 Nov if form is open and final checks pass; otherwise prepare everything and submit on 10 Nov well before cutoff | J-08 | Submission confirmation is saved; no last-minute unverified edits |

### Day 8 — Tue 10 Nov: buffer only

No feature work. Check that the submitted entry is confirmed, links remain public, and the submission is not left in draft. The hard deadline is **11:59 PM IST**. Do not rely on the last hour.

---

## 5. Definition of done for every task

A task is not “done” because the code was written. It is done when all applicable items are true:

- [ ] Code is in the correct owner's folder and branch.
- [ ] Unit/contract test added or updated; tests run locally.
- [ ] No external API call is made by automated tests.
- [ ] User-visible behaviour has a loading, error and fallback state where appropriate.
- [ ] Related docs/fixture updated when the API or data shape changes.
- [ ] PR opened and reviewed by the other teammate.
- [ ] The task row is ticked only after the acceptance check passes.
- [ ] The owner records their own contribution in `contributions/LEDGER.md` that day.

## 6. Daily operating rhythm

**Start of day — 10 minutes:** each person says (1) the task ID they will finish today, (2) its output, and (3) the one thing that could block it.

**Midday — 5 minutes:** only discuss blockers that prevent the other person's next task. Do not turn this into a broad planning meeting.

**End of day — 15 minutes:** merge reviewed work, run `pytest -q`, open the UI and verify the day's acceptance gate, update task checkboxes and write individual ledger entries.

Every unfinished task must be moved to one of: `next day`, `cut`, or `blocked by <specific task/person>`. Never leave it as vague “in progress”.

## 7. Dependency rules and cut line

1. **Fixture before integration.** Shritama can build the UI from the sample fixture while Mrinmoy builds the backend. Do not block one another on endpoint implementation.
2. **Mock before live.** The entire journey must work in mock mode before live integrations are relied upon.
3. **Rules before LLM.** The deterministic parser and unit maths are the source of truth. LLM extraction is not required for the demo if it threatens reliability; it can be added only after rules pass.
4. **One clarification is better than a silent guess.** If the parser cannot distinguish tsp/tbsp or cup types, ask the user.
5. **Evidence before polish.** Evaluation and demo footage outrank extra animations or P2 features.
6. **If Day 3 slips:** cut servings scaling UI first, then advanced keyterm handling; preserve transcription/manual input, ranges, ambiguity and transcript editing. (Personal calibration is already postponed.)
7. **If Day 4 slips:** cut PNG export and saved-recipe delete; preserve save/open, basic cook mode, ranges and transcript editing.
8. **If Day 5 slips:** no optional features at all. Spend remaining time stabilising, measuring and recording the real working path.
9. **Never cut:** one real Gnani API integration verified in the demo or clearly identified as a verified backend call, mock/manual fallback, privacy consent, honest ranges, Supabase sign-in with owner-scoped storage, test suite, contribution evidence and a truthful public demo.

## 8. Risks and immediate responses

| Risk | Trigger | Response / owner |
|---|---|---|
| Gnani key or endpoint fails | First smoke test errors or no credits | M records exact error and request settings; proceed with mock/manual capture; ask Gnani support only with a minimal reproducible example |
| Frontend blocked by backend | Endpoint not ready at agreed time | S continues on fixture and mock adapter; M publishes a fixture-compatible response before asking for UI changes |
| Parser misses Bengali spelling | Case fails | M adds the phrase to a test first, then improves lexicon/normalisation; do not hard-code one demo transcript |
| Quantity estimates are weak | Few measurements or wide bands | Label as `typical (unverified)`, report n and width, retain original phrase; never invent precision |
| Evaluation sample is too small | Fewer than target cases | Report actual n and limits; don't claim general accuracy |
| Scope expands | New feature proposed before P0 gate | Put it in P2; no work begins without both teammates agreeing P0 is green |
| Team attribution unclear | Shared commits or vague statements | Separate branches/PRs and individual ledger entries; describe assistance truthfully |

## 9. Final release checklist

- [ ] Product journey works on a fresh checkout: sign in (or mock mode where documented), transcript, parse, save, reopen, edit/version, delete.
- [ ] At least one Gnani model/API was genuinely used and is named accurately in the project explanation.
- [ ] Transcript editing, parse, clarification and range display work.
- [ ] Ownership isolation is demonstrated with two accounts: neither can list, open, edit or delete the other's recipes, and saved recipes survive an application restart.
- [ ] Consent is collected before recording another person's voice; audio is not retained by default.
- [ ] No real phone numbers, account numbers, Aadhaar, PAN or private recordings are in the repo/demo.
- [ ] Automated tests pass offline; test command is documented.
- [ ] Evaluation reports exact sample size, protocol, failures and limitations.
- [ ] Demo video shows the actual app working; public post is live on LinkedIn and/or X with `#GnaniAI` and `#GreatIndianAIInternshipChallenge`, and Gnani AI is tagged.
- [ ] Contribution statements accurately separate Mrinmoy's and Shritama's work.
- [ ] README contains setup, configuration, screenshots/video, model/API usage and limitations.
- [ ] Submission includes demo video, project explanation, Gnani model/API list and nominated post link(s).
- [ ] Submission confirmation is saved before 10 Nov 2026, 11:59 PM IST.

---

## 10. First actions to take right now

**Mrinmoy:** start `M-01`, then `M-02` and `M-03`. Your first deliverable is a running FastAPI health endpoint and a fixture-compatible mock parse endpoint. Do not begin Kaggle or Evon.

**Shritama:** start `S-01`, then `S-02`, `S-03` and `S-04`. Your first deliverable is a usable frontend that renders the sample fixture and accepts manual transcript text. Do not wait for the backend or start visual polish.

**Together:** complete `J-01` first, then spend no more than 20 minutes on `J-02` contract alignment. At the end of the first two hours, both people should have a working piece of the product.
