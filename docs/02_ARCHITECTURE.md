# 02 Architecture

```
React (Vite) frontend
  record/upload -> WAV 16 kHz chunks (<=25 s)      cook mode: mic, timers, TTS playback
  Supabase Auth client: sign-in/out, session, access token
         |  REST + WebSocket  (Authorization: Bearer <access_token>)
         v                                                    ^
FastAPI modular monolith (backend/app)
  auth/    access-token verification (JWKS signing keys), current-user dependency
  gnani/   stt, tts, realtime relay, budget log, mock mode
  parse/   normalize -> segment -> rules -> llm_extract -> merge/validate -> ambiguity
  llm/     provider chain (rules | gemini | ollama | evon_kaggle), cache/replay
  units/   reference table, hand profiles, interval maths, scaling
  db/      owner-scoped Supabase PostgreSQL repo layer
         |
  Supabase Auth (JWKS) + Supabase PostgreSQL (RLS) + Gnani APIs (Prisma, Timbre) + optional LLM endpoints
```

## Decisions and reasons
- **Modular monolith**: two people, one week. Each package has one job and one test folder.
- **React (Vite) frontend with the Supabase Auth client**: sign-in/session state lives in the Supabase client; recipe screens render `ParseResult` fields only. The frontend holds only the publishable anon key and the user's own access token.
- **Supabase Auth, not custom auth**: registration, login, logout, sessions and (if enabled) Google/email-password sign-in belong to Supabase. FastAPI only verifies the token it is handed: signature against the project's signing keys (JWKS), `exp`, `iss` and `aud=authenticated`, and reads the user id from `sub`. No custom password login/signup endpoints, no password storage.
- **Supabase PostgreSQL, not a local SQLite file**: cloud-hosted, persistent across restarts, with Row Level Security. Because FastAPI connects with privileged server credentials (which bypass RLS), repository methods enforce ownership in application code on every read, update and delete. The service-role key never appears in frontend config or bundles.
- **Three separate identities** (see `docs/03_DATA_MODEL.md`): the account user, the cook/narrator person, and the measurement profile. They are never merged into one entity.
- **Rules first, LLM second**: rules are the guaranteed floor; the LLM raises recall on unseen phrasing but is validated and optional.
- **Mock everywhere**: `GNANI_MOCK=1` and `LLM_CHAIN=rules` give a fully offline app for tests and the demo. Authentication and storage still require real Supabase credentials.

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
**Narration to recipe**: browser chunks audio -> `POST /api/narrations/transcribe` per chunk (server holds one global Gnani lock) -> merged transcript in review editor -> `POST /api/parse` -> steps with ranges + clarifications -> user answers -> `POST /api/recipes` with the user's access token (owner derived from the token).
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
| SUPABASE_URL | Project URL. Frontend (Supabase Auth client) and backend (token verification issuer/JWKS URL) |
| SUPABASE_ANON_KEY | Publishable anon key. **Frontend only** (Vite: `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`) |
| SUPABASE_DB_URL | PostgreSQL connection string. **Backend only** — never reaches the browser |
| (no service-role key) | Deliberately absent. If the architecture ever needs one it stays backend-only and is never exposed via `VITE_` variables |

## Error policy
Every external call: timeout, one retry with backoff on 429/5xx, then fall back. Errors reach the UI as `{error:{code,message,hint}}`; never show raw upstream errors. Budgets: parse without LLM p95 < 1 s; with LLM < 15 s; TTS cached after first use.

## Testing
pytest with fixtures; parser YAML cases; contract tests against `docs/fixtures/`; no network in tests.
