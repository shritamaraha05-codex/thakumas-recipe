# 04 API contract

JSON everywhere unless noted. Errors: `{"error":{"code":"...","message":"...","hint":"..."}}` with codes `INVALID_INPUT, AUDIO_TOO_LONG, NO_API_KEY, UPSTREAM_BUSY, UPSTREAM_ERROR, LLM_UNAVAILABLE, CONSENT_REQUIRED, NOT_FOUND, UNAUTHORIZED, FORBIDDEN`. HTTP mapping: `401 UNAUTHORIZED` = missing/invalid/expired access token; `403 FORBIDDEN` = authenticated but explicitly denied; `404 NOT_FOUND` = resource does not exist or is not owned by the caller (ownership is never leaked through 403); `422 INVALID_INPUT` = invalid request. A sample `ParseResult` lives in `docs/fixtures/parse_result.sample.json`; the frontend builds against it from day 1.

## System
- `GET /api/health` -> `{ok, db:{status,path,note}, gnani:{configured, mock}, llm:{chain:[..], healthy:[..], providers:[{name,configured,healthy,note}]}}`. `ok` means the app process is up, **not** that external providers work. `healthy` lists only providers confirmed on this request (currently `rules`); external providers report `healthy:null` ("not probed") and are never marked healthy just because a key exists. (M-18A replaces the local-file `db.path` with a Supabase connectivity report; the response keeps this shape until then.)
- `GET /api/llm/status` -> per provider `{name, ok, latency_ms, last_error}`

## Authentication (Supabase Auth)

All recipe-management endpoints require a valid Supabase access token. The parser and speech endpoints stay public.

- Supabase Auth owns registration, login, logout, session management, and (if enabled on the project) Google and email/password sign-in. The frontend uses the Supabase client for all of this; **this API has no custom password signup/login endpoints and we never store passwords.**
- After sign-in the frontend sends the token on every protected request: `Authorization: Bearer <access_token>`.
- The backend verifies the token before any repository work (task M-18B):
  - **signature**: verified against the project's signing keys (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` for asymmetric signing keys; a pre-signing-key project uses its legacy HS256 JWT secret instead — confirm which the project uses before implementing, and load keys from the JWKS URL, not from a hard-coded copy);
  - **expiry**: `exp` is in the future;
  - **issuer**: `iss` equals the project's auth URL (`https://<project-ref>.supabase.co/auth/v1`);
  - **audience**: `aud` is `authenticated`.
- The authenticated identity is the token's `sub` claim. **Never trust a user id supplied in the request body or query parameters** — a client-supplied `owner_user_id`/`user_id` is rejected or ignored, and `owner_user_id` for new recipes is always derived from the verified token.
- Failures: missing, malformed or expired token -> `401 UNAUTHORIZED`; a valid token that does not own a resource -> `404 NOT_FOUND` on that resource (not 403, to avoid revealing another user's recipe ids).
- `GET /api/me` -> `{id, display_name}` — the authenticated user's basic application profile (`profiles` row). `401 UNAUTHORIZED` without a valid token.

## Capture and parse
- `POST /api/narrations/transcribe` (multipart: `audio` WAV <=30 s, `language` default `indic-auto`, optional `previous_text`, `keyterms` JSON array) -> `{transcript, detected_language_code, chunk_index?}`. Server serialises calls to Gnani (one active request).
- `POST /api/parse` `{text, mode:"auto|rules|llm", hand_profile_id?, servings?}` -> `ParseResult`. Runs the deterministic rules parser (M-08) locally, or the Gemini provider (M-10) when selected.
- `POST /api/parse/resolve` `{draft: ParseResult, answers:[{clarification_id, answer}], hand_profile_id?}` -> recomputed `ParseResult` (stateless). Not implemented yet (M-16).

### Parser modes (`POST /api/parse`)
- `mode="rules"`: run the deterministic offline parser. Makes no external call. This is fully implemented.
- `mode="auto"` (default): use the first **implemented** parser in the configured `LLM_CHAIN`, walked in order (e.g. `LLM_CHAIN=gemini,rules` selects Gemini first; `LLM_CHAIN=rules` stays offline). `rules` is the documented floor. Auto does not fall back after a provider is chosen: that provider's failure is reported as a documented error.
- `mode="llm"`: an explicit request for the **Gemini** provider (`GEMINI_MODEL`, default `gemini-3.5-flash-lite`). It is never silently downgraded to `rules`; any failure returns a documented error.
- `hand_profile_id` and `servings` are accepted for contract compatibility but are **not used**: personal measurement calibration and recipe scaling are postponed by the 2026-11-08 planning correction, so nothing is calibrated or scaled.
- Validation: empty or whitespace-only `text`, an unknown `mode`, and non-positive `servings` return `422 INVALID_INPUT`.
- Gemini errors (never exposing raw provider messages, keys or the transcript):
  - missing/rejected credentials -> `503 LLM_UNAVAILABLE`;
  - timeout -> `504 UPSTREAM_BUSY`;
  - rate limit -> `503 UPSTREAM_BUSY`;
  - provider failure or structured output that fails evidence validation -> `502 UPSTREAM_ERROR`. An invalid or cross-segment evidence id can never produce a fabricated recipe.

### Response structure
`ParseResult`: `{recipe:{title, language, base_servings, steps:[{idx, text, orig_start, orig_end, timer_seconds, durations:[Duration], quantities:[Quantity]}]}, meta:{parser_mode, llm_provider, replayed, mock, mock_source}}`
`Quantity`: `{id, ingredient, ingredient_class, qty, qty_max, unit, raw_unit, classifier, kind, to_taste, raw_phrase, confidence, source, orig_start, orig_end, range:{lo,hi,unit,basis}|null, clarification:{id,kind,question,options[]}|null}` where `kind` is `exact|range|vague|taste|unresolved` and `basis` is `exact|yours|typical`.
`Duration`: `{raw_phrase, value, value_max, unit, kind, orig_start, orig_end}` where `unit` is `minute|hour|second`.

- `raw_phrase` is always an exact substring of the submitted transcript; `orig_start`/`orig_end` index the original transcript (steps and quantities alike). `ingredient` is the canonical name and `ingredient_class` is one of `grain|flour|salt|sugar|spice|liquid|produce|herb`.
- `kind` preserves the distinction the rules parser made: `exact` (one stated value), `range` (explicit range), `vague` (no number), `taste` (to-taste instruction), `unresolved` (a measure with no number). `qty_max` is set only for a stated range.
- `range` is `null` until the units stage exists (M-12/M-13): the parser never converts a traditional measure to grams/millilitres. `timer_seconds` is likewise `null`; a spoken duration stays in `durations` in the cook's own unit.
- Ambiguity: plain `চামচ`/`chamoch` yields `clarification.kind="unit_spoon"` (options `tsp`,`tbsp`); uncalibrated `কাপ`/`cup` yields `clarification.kind="unit_cup"` (options `tea cup`,`measuring cup`,`my cup`). Ids are deterministic (`unit_spoon_1`, `unit_cup_1`, ...). Resolved compounds `ছোট চামচ`/`বড় চামচ` do not trigger a question.
- Metadata is truthful: `meta.parser_mode="rules"`/`"llm"` matches the parser that answered, `meta.llm_provider` is `"gemini"` only when Gemini produced the result (otherwise `null`), and `meta.mock=false` for real parser/provider output. `language` and `base_servings` stay `null` because they are not inferred. Each `Quantity.source` is `rules` or `llm` accordingly.
- Gemini structured output: the model may only select request-local evidence ids built from the M-07 lexicon matches. The backend validates every id (existence, category, same-segment, no duplicates) and constructs all canonical names, quantities, surface forms and source spans from that verified evidence. The model never supplies wording, numbers or offsets.
- Not implemented yet: gram/millilitre ranges, personal hand calibration, recipe scaling, yield/servings inference, and a second LLM provider. (Calibration and scaling are postponed, not dropped for ever; see `docs/12_TASKS.md`.)

Example request: `{"text": "এক চামচ তেল দাও। তারপর এক মুঠো চাল আর এক চিমটি নুন দাও, স্বাদমতো নুন। দশ মিনিট ঢিমে আঁচে রান্না করো।", "mode": "rules"}`. The actual response is `docs/fixtures/parse_result.sample.json`, which `backend/tests/test_fixture.py` verifies is byte-for-byte the live response for exactly this request.

### Manual Gemini smoke test (real key, not run by pytest)
1. Set `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-3.5-flash-lite` in `.env` (never commit it).
2. Start the backend: `uvicorn backend.app.main:app --reload`.
3. Submit the Chitol Macher Muitha narration with `mode="llm"`, e.g. `POST /api/parse` with `{"text": "...", "mode": "llm"}` from `/docs`.
4. Inspect the JSON: ingredients, quantities, duration, ambiguity (`unit_spoon_*`/`unit_cup_*`) and that every `raw_phrase`/`orig_*` is an exact slice of the submitted text, with `meta.parser_mode="llm"`, `meta.llm_provider="gemini"`.

## Recipes

All routes below require `Authorization: Bearer <access_token>` (see Authentication). The backend derives `owner_user_id` from the verified token's `sub`; the client must not send any ownership id. A missing/invalid token is `401 UNAUTHORIZED`; a recipe that does not exist or belongs to another user is `404 NOT_FOUND` for every read, update and delete, so recipe ids are never revealed.

- `POST /api/recipes` `{title, original_transcript, draft, cook_person_id?, narrator_person_id?, tags[]}` -> `{id, version}`. `draft` is the complete `ParseResult` JSON; `original_transcript` is stored verbatim on version 1. `cook_person_id` / `narrator_person_id` are optional attribution for the cook/narrator *person* (a family member need not have an account); person management is postponed, so they are accepted and stored with the version but not yet resolved to person rows. `title` and `tags` may be empty (`tags` defaults to `[]`).
- `GET /api/recipes?query=&tag=` -> list of **the authenticated user's recipes only** (title substring match for `query`, tag match for `tag`), newest first.
- `GET /api/recipes/{id}` -> the saved recipe (newest version by default) if the authenticated user owns it, else `404 NOT_FOUND`. `hand_profile_id` and `servings` remain accepted for contract compatibility but are **not used**: personal calibration and recipe scaling are postponed, so nothing is calibrated, scaled and no `staged_guidance` is produced yet.
- `PUT /api/recipes/{id}` `{title?, tags?, original_transcript, draft}` -> creates a **new** `recipe_versions` row (previous version retained); only the owner may update, else `404 NOT_FOUND`.
- `DELETE /api/recipes/{id}` -> owner only, else `404 NOT_FOUND`. Deleting a recipe cascades to its versions.

### Postponed recipe endpoints (not in this release)

Kept for the record; they return `501` / are absent until their tasks are re-opened.

- `GET /api/recipes/pantry?items=chal,dal,alu` (pantry search) — postponed.
- `POST /api/collections`, `POST /api/collections/{id}/recipes/{recipe_id}`, `GET /api/collections` (collections) — postponed.

## People, consent, hands — POSTPONED

Person/profile/consent management (M-18's original scope) is moved off the critical path by the 2026-11-08 planning correction; the schema is documented as deferred in `docs/03_DATA_MODEL.md`. Voice-capture consent in the UI (S-05) still applies. These routes are not implemented this release:

- `POST /api/persons` `{name, relationship}`; `DELETE /api/persons/{id}` (cascades)
- `POST /api/persons/{id}/consents` `{scope}`; `DELETE /api/consents/{id}` (revoke)
- `POST /api/persons/{id}/profiles` `{label}`; `GET /api/profiles/{id}`
- `POST /api/profiles/{id}/weighings` `{unit, ingredient, amount, amount_unit}`; `DELETE /api/weighings/{id}`
- `GET /api/profiles/{id}/suggest?recipe_id=` -> top-3 weighings that would tighten the recipe most

## Voice
- `POST /api/speak` `{text, language, voice?, speed?}` -> `audio/wav` (cached by hash of text+voice+language+speed). Applies `tts_text` number-to-words first.
- `GET /api/recipes/{id}/audio?language=` -> full recipe audio (`audio/wav`)
- `POST /api/cook/command` (multipart: `audio` <=4 s, `language`) -> `{transcript, command:"next|prev|repeat|stop|timer|null", args}`
- `POST /api/cook/rescue` `{recipe_id, step_idx, problem_text}` -> `{advice, caveats[]}` (LLM; always labelled advice)
- `WS /ws/cook` (P1, **draft** until Gnani's realtime STT doc is read): client sends JSON `{type:"start", recipe_id, language}`, then binary PCM16 mono 16 kHz frames (100-200 ms), `{type:"tts_state", playing}`, `{type:"stop"}`. Server sends `{type:"ready"}`, `{type:"partial", text}`, `{type:"final", text}`, `{type:"command", command, args}`, `{type:"error", ...}`.

## Evaluation
- `GET /api/eval/latest` -> latest `eval_run` plus per-unit coverage/width for the accuracy page.
