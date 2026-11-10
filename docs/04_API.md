# 04 API contract

JSON everywhere unless noted. Errors: `{"error":{"code":"...","message":"...","hint":"..."}}` with codes `INVALID_INPUT, AUDIO_TOO_LONG, NO_API_KEY, UPSTREAM_BUSY, UPSTREAM_ERROR, LLM_UNAVAILABLE, CONSENT_REQUIRED, NOT_FOUND, UNAUTHORIZED, FORBIDDEN`. HTTP mapping: `401 UNAUTHORIZED` = missing/invalid/expired access token; `403 FORBIDDEN` = authenticated but explicitly denied; `404 NOT_FOUND` = resource does not exist or is not owned by the caller (ownership is never leaked through 403); `422 INVALID_INPUT` = invalid request. A sample `ParseResult` lives in `docs/fixtures/parse_result.sample.json`; the frontend builds against it from day 1.

## System
- `GET /api/health` -> `{ok, db:{status,configured,reachable,note}, gnani:{configured, mock}, llm:{chain:[..], healthy:[..], providers:[{name,configured,healthy,note}]}}`. `ok` means the app process is up, **not** that external providers work. `db.status` is `not_configured` (no Supabase URL/key), `unverified` (configured but no probe ran), `ok` (the Data API answered) or `unavailable` (the probe failed). `db.reachable` is `null` until a probe actually runs, so configuration is never reported as healthy. No URL, key or connection string is returned. `healthy` lists only providers confirmed on this request (currently `rules`); external providers report `healthy:null` ("not probed") and are never marked healthy just because a key exists.
- `GET /api/llm/status` -> per provider `{name, ok, latency_ms, last_error}`

## Authentication (Supabase Auth)

All recipe-management endpoints require a valid Supabase access token. The parser and speech endpoints stay public.

- Supabase Auth owns registration, login, logout, session management, and (if enabled on the project) Google and email/password sign-in. The frontend uses the Supabase client for all of this; **this API has no custom password signup/login endpoints and we never store passwords.**
- After sign-in the frontend sends the token on every protected request: `Authorization: Bearer <access_token>`.
- The backend verifies the token before any repository work (M-18B):
  - **asymmetric signature**: verified against the project's JWKS (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`), including the key id (`kid`) and algorithm; keys are cached, never hard-coded;
  - **legacy HS256 projects**: verified by calling Supabase Auth's `GET /auth/v1/user` with the user token (and the publishable key as `apikey`). The project's JWT secret is never requested, read or stored;
  - **expiry**: `exp` is in the future;
  - **issuer**: `iss` equals the project's auth URL (`https://<project-ref>.supabase.co/auth/v1`);
  - **audience**: `aud` is `authenticated`.
  - Missing, malformed, expired or invalid tokens return `401 UNAUTHORIZED`; an unreachable auth/JWKS endpoint returns `503 UPSTREAM_BUSY`.
- The authenticated identity is the token's `sub` claim. **Never trust a user id supplied in the request body or query parameters** — a client-supplied `owner_user_id`/`user_id` is rejected or ignored, and `owner_user_id` for new recipes is always derived from the verified token.
- Failures: missing, malformed or expired token -> `401 UNAUTHORIZED`; a valid token that does not own a resource -> `404 NOT_FOUND` on that resource (not 403, to avoid revealing another user's recipe ids).
- `GET /api/me` -> `{id, display_name, created_at}` — the authenticated user's basic application profile (`profiles` row; created on first use/sign-up if missing). `401 UNAUTHORIZED` without a valid token. No token, password or secret is ever returned.
- `GET /api/me/hand-calibration` -> `{profile_id, weighings, ranges}` for the authenticated account's hand profile.
- `POST /api/me/hand-calibration/weighings` `{unit, ingredient, amount, amount_unit:"g|ml"}` -> save a weighing and return refreshed calibration.
- `DELETE /api/me/hand-calibration/weighings/{weighing_id}` -> delete an owned weighing and return refreshed calibration.

Calibration range entries are grouped by canonical unit, case-insensitive ingredient, and output unit. A single reading `x` yields `[0.85x, 1.15x]`; two or more yield `[0.95 × min, 1.05 × max]`. Responses carry `basis:"yours"`. These ranges are available to the UI; `/api/parse` does not consume them yet.

## Capture and parse
- `POST /api/narrations/transcribe` (authenticated multipart: `audio` mono 16 kHz PCM16 WAV <=30 s, `language` default `indic-auto`, required `consent=true`, optional `previous_text`) -> `{transcript, detected_language_code, mock}`. Audio is handled in memory and is never stored. Server serialises calls to Gnani (one active request). The browser sends clips <=30 s as one request; longer recordings are converted in full, cut at quiet frames into sequential <=25 s requests, and use v3.0 `previous_text` context. `mock=true` means no real speech was processed; mock mode returns the labelled synthetic fixture on the first clip and an empty transcript on following clips.
- `POST /api/parse` `{text, mode:"auto|rules|llm", hand_profile_id?, servings?}` -> `ParseResult`. Runs the deterministic rules parser (M-08) locally, or the Gemini provider (M-10) when selected.
- `POST /api/parse/resolve` `{draft: ParseResult, answers:[{clarification_id, answer}], hand_profile_id?}` -> recomputed `ParseResult` (stateless). Not implemented yet (M-16).

### Parser modes (`POST /api/parse`)
- `mode="rules"`: run the deterministic offline parser. Makes no external call. This is fully implemented.
- `mode="auto"` (default): use the first **implemented** parser in the configured `LLM_CHAIN`, walked in order (e.g. `LLM_CHAIN=gemini,rules` selects Gemini first; `LLM_CHAIN=rules` stays offline). `rules` is the documented floor. Auto does not fall back after a provider is chosen: that provider's failure is reported as a documented error.
- `mode="llm"`: an explicit request for the **Gemini** provider (`GEMINI_MODEL`, default `gemini-3.5-flash-lite`). It is never silently downgraded to `rules`; any failure returns a documented error.
- `hand_profile_id` and `servings` are accepted for contract compatibility but are **not used** by parse. Account-owned personal weighings and intervals can be managed through `/api/me/hand-calibration`; automatic recipe quantity resolution and scaling do not consume them yet.
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
- Not implemented yet: applying gram/millilitre ranges to parsed quantities, recipe scaling, yield/servings inference, and a second LLM provider. Personal hand weighings/intervals are available via the calibration endpoints above.

Example request: `{"text": "এক চামচ তেল দাও। তারপর এক মুঠো চাল আর এক চিমটি নুন দাও, স্বাদমতো নুন। দশ মিনিট ঢিমে আঁচে রান্না করো।", "mode": "rules"}`. The actual response is `docs/fixtures/parse_result.sample.json`, which `backend/tests/test_fixture.py` verifies is byte-for-byte the live response for exactly this request.

### Manual Gemini smoke test (real key, not run by pytest)
1. Set `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-3.5-flash-lite` in `.env` (never commit it).
2. Start the backend: `uvicorn backend.app.main:app --reload`.
3. Submit the Chitol Macher Muitha narration with `mode="llm"`, e.g. `POST /api/parse` with `{"text": "...", "mode": "llm"}` from `/docs`.
4. Inspect the JSON: ingredients, quantities, duration, ambiguity (`unit_spoon_*`/`unit_cup_*`) and that every `raw_phrase`/`orig_*` is an exact slice of the submitted text, with `meta.parser_mode="llm"`, `meta.llm_provider="gemini"`.

## Recipes

All routes below require `Authorization: Bearer <access_token>` (see Authentication). The backend derives `owner_user_id` from the verified token's `sub`; the client must not send any ownership id. A missing/invalid token is `401 UNAUTHORIZED`; a recipe that does not exist or belongs to another user is `404 NOT_FOUND` for every read, update and delete, so recipe ids are never revealed.

- `POST /api/recipes` `{title, original_transcript, draft, tags[]?, cook_person_id?, narrator_person_id?}` -> `201 {id, version}` with `version: 1`.
  - `title` is required and must not be blank; `original_transcript` is required and stored **verbatim**; `draft` is the complete public `ParseResult` JSON and is stored as one JSONB value.
  - `tags` defaults to `[]`. `cook_person_id` / `narrator_person_id` exist for forward compatibility but person management is postponed: any non-null value returns `422 INVALID_INPUT` explaining that linking is not implemented. They are never silently dropped.
  - Unknown fields are rejected (`extra="forbid"`), including a client-supplied `owner_user_id`.
- `GET /api/recipes?query=&tag=&limit=&offset=` -> `{items:[...], total}` for **the authenticated user's recipes only**. `query` is a case-insensitive title substring; `tag` matches one tag; results are newest-first with a stable id tie-break. `limit` is 1–100 (default 50), `offset` >= 0. Items contain only metadata: `{id, title, tags, version, created_at, updated_at}` — never the draft or transcript.
- `GET /api/recipes/{id}` -> the latest version if the authenticated user owns it, else `404 NOT_FOUND` (also for malformed/nonexistent ids; malformed UUIDs get `422 INVALID_INPUT`). Shape: `{id, title, version, original_transcript, draft, tags, created_at, updated_at}`. The draft is returned exactly as saved; the parser is never re-run.
- `PUT /api/recipes/{id}` `{title?, tags?, original_transcript, draft}` -> `{id, version}` with the **new** version number. This always creates a new immutable `recipe_versions` row; previous versions are never overwritten. Omitted `title`/`tags` keep the existing recipe metadata. Only the owner may update, else `404 NOT_FOUND`.
- `DELETE /api/recipes/{id}` -> `{id, deleted: true}`. Owner only, else `404 NOT_FOUND`. Deleting a recipe cascades to all its versions.
- `GET /api/recipes/{id}/translation` -> `{translations: string[]}` in recipe-step order. Owner only. Uses the configured Gemini provider on demand; it sends only step text and does not save generated translations. If Gemini is unavailable, returns `503 LLM_UNAVAILABLE` and the client keeps the original Bengali visible.

Versions are sequential per recipe (1, 2, 3, …); `unique(recipe_id, version_number)` and a locked recipe row in the `add_recipe_version` RPC prevent collisions. The latest version is the default view. `hand_profile_id`/`servings` are not part of the recipe endpoints (automatic calibration resolution and scaling remain unavailable).

### Postponed recipe endpoints (not in this release)

Kept for the record; they return `501` / are absent until their tasks are re-opened.

- `GET /api/recipes/pantry?items=chal,dal,alu` (pantry search) — postponed.
- `POST /api/collections`, `POST /api/collections/{id}/recipes/{recipe_id}`, `GET /api/collections` (collections) — postponed.

## People and consent — POSTPONED

Multi-person profile and consent management (M-18's original scope) remains postponed. Voice-capture consent in the UI (S-05) still applies. The person-scoped routes below are not implemented; account-owned hand calibration has separate routes above.

- `POST /api/persons` `{name, relationship}`; `DELETE /api/persons/{id}` (cascades)
- `POST /api/persons/{id}/consents` `{scope}`; `DELETE /api/consents/{id}` (revoke)
- `POST /api/persons/{id}/profiles` `{label}`; `GET /api/profiles/{id}`
- `GET /api/profiles/{id}/suggest?recipe_id=` -> top-3 weighings that would tighten the recipe most

## Voice
- `POST /api/narrations/transcribe` (multipart: `audio`, `language`, `consent`, optional `previous_text`) accepts mono 16 kHz PCM16 WAV or ADTS AAC; consent is required. Each request must contain a valid clip of at most 30 seconds. The browser passes ADTS AAC through without decoding and splits longer AAC recordings at complete frame boundaries into sequential clips of at most 25 seconds; WAV recordings are mixed/resampled and split at low-energy boundaries. Audio is processed in memory and discarded after transcription.
- `POST /api/speak` `{text, language, voice?, speed?}` -> `audio/wav` (cached by hash of text+voice+language+speed). Applies `tts_text` number-to-words first.
- `GET /api/recipes/{id}/audio?language=` -> full recipe audio (`audio/wav`)
- `POST /api/cook/command` (multipart: `audio` <=4 s, `language`) -> `{transcript, command:"next|prev|repeat|stop|timer|null", args}`
- `POST /api/cook/rescue` `{recipe_id, step_idx, problem_text}` -> `{advice, caveats[]}` (LLM; always labelled advice)
- `WS /ws/cook` (P1, **draft** until Gnani's realtime STT doc is read): client sends JSON `{type:"start", recipe_id, language}`, then binary PCM16 mono 16 kHz frames (100-200 ms), `{type:"tts_state", playing}`, `{type:"stop"}`. Server sends `{type:"ready"}`, `{type:"partial", text}`, `{type:"final", text}`, `{type:"command", command, args}`, `{type:"error", ...}`.

## Evaluation
- `GET /api/eval/latest` -> latest `eval_run` plus per-unit coverage/width for the accuracy page.
