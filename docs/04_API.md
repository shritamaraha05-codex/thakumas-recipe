# 04 API contract

JSON everywhere unless noted. Errors: `{"error":{"code":"...","message":"...","hint":"..."}}` with codes `INVALID_INPUT, AUDIO_TOO_LONG, NO_API_KEY, UPSTREAM_BUSY, UPSTREAM_ERROR, LLM_UNAVAILABLE, CONSENT_REQUIRED, NOT_FOUND`. A sample `ParseResult` lives in `docs/fixtures/parse_result.sample.json`; the frontend builds against it from day 1.

## System
- `GET /api/health` -> `{ok, db:{status,path,note}, gnani:{configured, mock}, llm:{chain:[..], healthy:[..], providers:[{name,configured,healthy,note}]}}`. `ok` means the app process is up, **not** that external providers work. `healthy` lists only providers confirmed on this request (currently `rules`); external providers report `healthy:null` ("not probed") and are never marked healthy just because a key exists.
- `GET /api/llm/status` -> per provider `{name, ok, latency_ms, last_error}`

## Capture and parse
- `POST /api/narrations/transcribe` (multipart: `audio` WAV <=30 s, `language` default `indic-auto`, optional `previous_text`, `keyterms` JSON array) -> `{transcript, detected_language_code, chunk_index?}`. Server serialises calls to Gnani (one active request).
- `POST /api/parse` `{text, mode:"auto|rules|llm", hand_profile_id?, servings?}` -> `ParseResult`
- `POST /api/parse/resolve` `{draft: ParseResult, answers:[{clarification_id, answer}], hand_profile_id?}` -> recomputed `ParseResult` (stateless)

`ParseResult`: `{recipe:{title, language, base_servings, steps:[{idx, text, timer_seconds, quantities:[Quantity]}]}, meta:{parser_mode, llm_provider, replayed, mock, mock_source}}`
`Quantity`: `{id, ingredient, ingredient_class, qty, qty_max, unit, to_taste, raw_phrase, confidence, source, range:{lo,hi,unit,basis}|null, clarification:{id,kind,question,options[]}|null}` where `basis` is `exact|yours|typical`.
`meta.mock` is `true` when the response is fixture/mock data rather than real parser/provider output; `meta.mock_source` names that source (currently the sample fixture). Until the parser exists, `POST /api/parse` returns `meta:{parser_mode:"rules", llm_provider:null, mock:true, mock_source:"docs/fixtures/parse_result.sample.json"}` for all modes; no LLM or Gnani call is made.

## Recipes
- `POST /api/recipes` `{title, draft, cook_person_id?, narrator_person_id?, tags[]}` -> `{id, version}`
- `GET /api/recipes?query=&tag=&collection=` -> list
- `GET /api/recipes/{id}?hand_profile_id=&servings=` -> recipe view, ranges recomputed, with `staged_guidance` for salt-like items when scaled >1.5x
- `PUT /api/recipes/{id}` (creates a new version) / `DELETE /api/recipes/{id}`
- `GET /api/recipes/pantry?items=chal,dal,alu` -> ranked by ingredient overlap
- `POST /api/collections`, `POST /api/collections/{id}/recipes/{recipe_id}`, `GET /api/collections`

## People, consent, hands
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
