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
  db/      request-scoped Data API repository (the user's JWT, never service-role)
         |
  Supabase Auth (JWKS; legacy /user fallback) + Supabase PostgreSQL Data API (RLS) + Gnani APIs (Prisma, Timbre) + optional LLM endpoints
```

## Decisions and reasons
- **Modular monolith**: two people, one week. Each package has one job and one test folder.
- **React (Vite) frontend with the Supabase Auth client**: sign-in/session state lives in the Supabase client; recipe screens render `ParseResult` fields only. The frontend holds only the publishable anon key and the user's own access token.
- **Supabase Auth, not custom auth**: registration, login, logout, sessions and (if enabled) Google/email-password sign-in belong to Supabase. FastAPI only verifies the token it is handed: signature against the project's signing keys (JWKS), `exp`, `iss` and `aud=authenticated`, and reads the user id from `sub`. Legacy HS256 projects are verified through Supabase Auth's `/user` endpoint; the project's JWT secret is never fetched or stored. No custom password login/signup endpoints, no password storage.
- **Supabase PostgreSQL Data API, not SQLite and not a privileged DB connection**: cloud-hosted, persistent across restarts, with Row Level Security. Each request builds its own `postgrest` client carrying the project's publishable key and the user's verified access token. There is no shared mutable client (so concurrent users cannot overwrite each other's auth header) and no service-role key, so PostgreSQL evaluates `auth.uid()` for every query. Repository methods also pass the verified owner id and the SQL functions check it against `auth.uid()`; ownership is enforced in both application and database layers.
- **Three separate identities** (see `docs/03_DATA_MODEL.md`): the account user, the cook/narrator person, and the measurement profile. They are never merged into one entity.
- **Rules first, LLM second**: rules are the guaranteed floor; the LLM raises recall on unseen phrasing but is validated and optional.
- **Mock everywhere**: `GNANI_MOCK=1` and `LLM_CHAIN=rules` give a fully offline app for tests and the demo. Authentication and storage still require real Supabase credentials.

## Repo layout (implemented)
```
backend/app/{main.py,config.py,models.py,errors.py,dependencies.py}
backend/app/auth/{__init__.py,dependencies.py,verification.py,schemas.py}
backend/app/db/{__init__.py,client.py,repository.py,schemas.py,errors.py}
backend/app/parse/{normalize.py,segment.py,lexicon.py,rules.py,llm.py,llm_schema.py,schema.py,serialize.py}
backend/app/providers/{__init__.py,gemini.py}
backend/app/routers/{health.py,parse.py,recipes.py}
backend/tests/{conftest.py,fakes.py,test_*.py}
backend/evaluation/                 # M-11 harness (unchanged)
supabase/migrations/0001_initial_schema.sql
frontend/{package.json,vite.config.js,index.html,.env.example,src/}
docs/   scripts/   contributions/   prototype_v0/ (frozen reference)
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
| SUPABASE_URL | Project URL. Frontend (Supabase Auth client) and backend (issuer/JWKS URL) |
| SUPABASE_PUBLISHABLE_KEY | Publishable project key. Safe in the browser (Vite: `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY`); not a password and not a JWT signing key |
| SUPABASE_ANON_KEY | Legacy fallback name, read only when `SUPABASE_PUBLISHABLE_KEY` is empty |
| SUPABASE_JWT_AUDIENCE | Expected `aud` claim (default `authenticated`) |
| FRONTEND_ORIGINS | Comma-separated browser origins allowed by CORS (default `http://localhost:5173`) |
| (no service-role key) | Deliberately absent. Ordinary recipe CRUD uses the user's JWT and must not bypass RLS |

## Error policy
Every external call: timeout, one retry with backoff on 429/5xx, then fall back. Errors reach the UI as `{error:{code,message,hint}}`; never show raw upstream errors. Supabase mapping: a missing/invalid/expired token is `401 UNAUTHORIZED`; a recipe that is missing or not owned is `404 NOT_FOUND` (never 403, so ids are not revealed); a Data API timeout is `503 UPSTREAM_BUSY`; any other Data API failure is `502 UPSTREAM_ERROR`. Raw SQL, tokens and connection details never reach the client. Budgets: parse without LLM p95 < 1 s; with LLM < 15 s; TTS cached after first use.

## Testing
pytest with fixtures; parser YAML cases; contract tests against `docs/fixtures/`; no network in tests. Supabase auth is tested with locally generated RSA keys and a mocked JWKS/`/user` endpoint; repository/API tests use an in-memory RPC fake; the migration test checks SQL text only. `frontend` is built with `npm run build` (no test runner wired yet). Live Supabase and Gemini checks are manual and are not claimed by the automated suite.
