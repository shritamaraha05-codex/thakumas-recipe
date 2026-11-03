# 02 Architecture

```
Browser (vanilla ES modules)
  record/upload -> WAV 16 kHz chunks (<=25 s)      cook mode: mic, timers, TTS playback
        |  REST + WebSocket                                  ^
        v                                                    |
FastAPI modular monolith (backend/app)
  gnani/   stt, tts, realtime relay, budget log, mock mode
  parse/   normalize -> segment -> rules -> llm_extract -> merge/validate -> ambiguity
  llm/     provider chain (rules | gemini | ollama | evon_kaggle), cache/replay
  units/   reference table, hand profiles, interval maths, scaling
  db/      SQLite repo layer
        |
  SQLite file + Gnani APIs (Prisma, Timbre) + optional LLM endpoints
```

## Decisions and reasons
- **Modular monolith**: two people, one week. Each package has one job and one test folder.
- **Vanilla frontend, no build step**: execution-reliable; Canvas/SVG cover the animations. Deploy = static files served by FastAPI.
- **SQLite**: single file, zero ops. Audio is never stored by default.
- **Rules first, LLM second**: rules are the guaranteed floor; the LLM raises recall on unseen phrasing but is validated and optional.
- **Mock everywhere**: `GNANI_MOCK=1` and `LLM_CHAIN=rules` give a fully offline app for tests and the demo.

## Repo layout
```
backend/app/{main.py,config.py}
backend/app/gnani/{stt.py,tts.py,realtime.py,budget.py,tts_text.py}
backend/app/llm/{base.py,providers.py,chain.py,cache.py,prompts.py}
backend/app/parse/{normalize.py,lexicon.py,rules.py,llm_extract.py,merge.py,ambiguity.py,schema.py}
backend/app/units/{reference.yaml,reference.py,hands.py,ranges.py,scale.py}
backend/app/db/{schema.sql,repo.py}
backend/app/routers/{narrations.py,recipes.py,profiles.py,cook.py,library.py,health.py}
backend/tests/{parse_cases.yaml,test_*.py}
frontend/{index.html,css/,js/{app.js,api.js,state.js,views/,components/},assets/}
eval/{cases/,harness.py,report.py}   kaggle/   scripts/   docs/   contributions/
```

## Key flows
**Narration to recipe**: browser chunks audio -> `POST /api/narrations/transcribe` per chunk (server holds one global Gnani lock) -> merged transcript in review editor -> `POST /api/parse` -> steps with ranges + clarifications -> user answers -> `POST /api/recipes`.
**Cook mode**: `GET /api/recipes/{id}` -> UI plays step audio (`/api/speak`, cached) -> mic to `/ws/cook` (P1) or short clips to `/api/cook/command` (P0).

## Configuration (`.env`)
| Var | Meaning |
|---|---|
| GNANI_API_KEY | Gnani key; empty means mock mode only |
| GNANI_MOCK | `1` returns canned transcripts/audio |
| GNANI_STT_MODEL, GNANI_TTS_MODEL, GNANI_VOICE | defaults `prisma-v3.0`, `timbre-v3.0`, `Shivani` |
| LLM_CHAIN | comma order, e.g. `gemini,ollama,evon_kaggle,rules` (rules is always the last fallback) |
| GEMINI_API_KEY, GEMINI_MODEL | check current model names; do not hard-code |
| OLLAMA_BASE_URL, OLLAMA_MODEL | default `http://localhost:11434/v1` |
| EVON_BASE_URL, EVON_API_KEY | Kaggle tunnel URL + bearer token |
| LLM_REPLAY_ONLY | `1` serves only cached LLM responses (label it in the UI) |
| DB_PATH | SQLite file path |

## Error policy
Every external call: timeout, one retry with backoff on 429/5xx, then fall back. Errors reach the UI as `{error:{code,message,hint}}`; never show raw upstream errors. Budgets: parse without LLM p95 < 1 s; with LLM < 15 s; TTS cached after first use.

## Testing
pytest with fixtures; parser YAML cases; contract tests against `docs/fixtures/`; no network in tests.
