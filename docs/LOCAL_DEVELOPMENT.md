# Local development: backend + frontend

This guide wires the FastAPI backend and the vanilla HTML/CSS/JS frontend
(built and served by Vite) to talk to each other on your machine. Backend and
frontend environments are **separate**: the backend reads `backend/.env`, the
frontend reads `frontend/.env`.

Nothing here deploys anything. Production differences are listed at the end.

---

## 1. Required software

- **Python 3.11+** and `pip` (backend).
- **Node.js 20+** and `npm` (frontend build/dev server).
- **Git** (to clone the repository).
- Optional: a **Supabase project** (URL + publishable key) — only needed for
  sign-in and recipe storage (`/api/me`, `/api/recipes`).
- Optional: a **Gemini API key** — only needed for `mode="llm"` parsing.

The app works with **no keys at all**: the rules parser and `/api/health` run
offline (`LLM_CHAIN=rules`, `GNANI_MOCK=1`).

---

## 2. Backend environment setup

1. Create and activate a virtual environment from the repository root.

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   (macOS/Linux: `python3 -m venv .venv`, `source .venv/bin/activate`.)

2. Create `backend/.env` from the template.

   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

   (macOS/Linux: `cp backend/.env.example backend/.env`.)

3. Fill in only what you need. `backend/.env` is git-ignored; `backend/.env.example`
   is tracked and holds placeholders only.

### How the backend loads `backend/.env`

`backend/app/config.py` resolves the file from its own source location
(`Path(__file__).resolve().parents[1] / ".env"`), so the settings load the same
way whether Uvicorn is started from the repository root or from another
directory. **Real environment variables always override values in the file**,
so a hosting platform's variables win over local defaults.

### Backend variables (as actually used by the code)

| Variable | Default | Required? | Meaning |
|---|---|---|---|
| `SUPABASE_URL` | empty | for accounts/storage | Supabase project URL, e.g. `https://<ref>.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | empty | for accounts/storage | Public project key (not a secret; not a JWT signing key) |
| `SUPABASE_ANON_KEY` | empty | no | Legacy fallback name; prefer `SUPABASE_PUBLISHABLE_KEY` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | no | Expected `aud` claim on access tokens |
| `SUPABASE_JWKS_CACHE_SECONDS` | `300` | no | How long signing keys are cached |
| `SUPABASE_REQUEST_TIMEOUT` | `10.0` | no | Timeout (seconds) for Supabase calls |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | no | Comma-separated browser origins allowed by CORS |
| `LLM_CHAIN` | `rules` | no | Parser chain; `rules` is the offline floor and must stay last |
| `GEMINI_API_KEY` | empty | for `mode="llm"` | Gemini API key (backend only — never in the frontend) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | no | Gemini model id |

There is **no database password, connection string or service-role key**. Data
requests carry each signed-in user's access token and PostgreSQL RLS enforces
ownership. A service-role key must never be placed in the backend `.env` for
this app or in any `VITE_` variable.

---

## 3. Frontend environment setup

1. Install dependencies and create `frontend/.env`.

   ```powershell
   cd frontend
   npm install
   Copy-Item .env.example .env
   ```

   (macOS/Linux: `cp .env.example .env`.)

2. Fill in `frontend/.env`. Vite loads `frontend/.env` automatically; only
   variables prefixed with `VITE_` are exposed to the browser.

### Frontend variables

| Variable | Example | Meaning |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` | Same project URL as the backend |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | `<publishable-key>` | Same publishable key as the backend |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the FastAPI backend (no trailing slash needed) |

These are read in `frontend/js/config.js` and used by `frontend/js/supabase.js`
(client init) and `frontend/js/api.js` (every backend request). Missing Supabase
values do **not** crash pages: the client is only created when both are present,
and pages that do not need auth still load.

> **Vite embeds `VITE_` values at build time.** Changing them requires a new
> `npm run build`. A production host must receive these variables *before*
> building. Never put a backend secret or a Supabase service-role key in a
> `VITE_` variable.

---

## 4. Start FastAPI

From the repository root:

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- API base: <http://127.0.0.1:8000>
- Interactive docs: <http://127.0.0.1:8000/docs>

---

## 5. Start Vite

From `frontend/`:

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

- App entry: <http://127.0.0.1:5173/>
- Pages: `/login.html`, `/library.html`, `/record.html`,
  `/recipe-detail.html`, `/cook-mode.html`, `/profile.html`

---

## 6. Test `/api/health`

```bash
curl http://127.0.0.1:8000/api/health
```

A valid response has `"ok": true`. The `db.status` field is honest:
`not_configured` (no Supabase URL/key), `unverified`, `ok`, or `unavailable`.
`ok: true` only means the app process is up, not that external providers work.

---

## 7. Test `/api/parse`

```bash
curl -X POST "http://127.0.0.1:8000/api/parse" \
  -H "Content-Type: application/json" \
  -d '{"text": "এক চামচ তেল দাও। তারপর এক মুঠো চাল দাও।", "mode": "rules"}'
```

Expect a `recipe` with ordered `steps` and a `meta.parser_mode` of `rules`.
This makes no external call.

---

## 8. Check CORS

Simulate a browser preflight from the Vite origin:

```bash
curl -i -X OPTIONS "http://127.0.0.1:8000/api/parse" \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```

The response must include:

- `Access-Control-Allow-Origin: http://localhost:5173`
- `Access-Control-Allow-Headers` containing `authorization`
- `Access-Control-Allow-Methods` containing `POST`

The default `FRONTEND_ORIGINS` covers both `http://localhost:5173` and
`http://127.0.0.1:5173`. Add your deployed origin through the environment
variable for production; credentials are enabled, so a wildcard `*` is not used.

---

## 9. Verify authenticated requests

The full chain is:

```text
login form -> Supabase JS client -> Supabase Auth -> session -> access token
   -> frontend/js/api.js -> Authorization: Bearer <token>
   -> FastAPI auth dependency -> Supabase JWT verification
   -> verified user identity -> RLS-scoped data access
```

Manual check with a real test account (do not create accounts without
permission, and never paste tokens into shared logs):

1. Sign in at `http://127.0.0.1:5173/login.html`.
2. Open browser DevTools → Application → Local Storage and confirm a Supabase
   session exists (`sb-<ref>-auth-token`). Reload a page; the session persists.
3. In DevTools → Network, confirm requests to `/api/me` and `/api/recipes` carry
   `Authorization: Bearer <token>` and return `200`.
4. Confirm the backend never receives a `user_id`/`owner_user_id` from the
   client; ownership comes from the verified token `sub`.
5. Log out (`/profile.html`) and confirm the session is cleared and protected
   pages redirect to `/login.html`.

Without a valid token, `/api/me` and `/api/recipes` return `401 UNAUTHORIZED`;
an unreachable Supabase auth/JWKS endpoint returns `503 UPSTREAM_BUSY`.

### Offline smoke test

With both servers running, this script checks reachability, health, the rules
parser, unauthenticated behaviour and CORS. It needs no Supabase credentials,
never calls Gemini and changes no data:

```bash
python scripts/check_local_integration.py
```

Optional overrides: `THAKUMA_BACKEND_URL`, `THAKUMA_FRONTEND_ORIGIN`.

---

## 10. Common errors and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Frontend shows "The backend server could not be reached." | Backend not running or wrong `VITE_API_BASE_URL` | Start Uvicorn; check `frontend/.env` |
| Browser console: CORS error | Vite origin not in `FRONTEND_ORIGINS` | Add the exact origin to `backend/.env` and restart the backend |
| `GET /api/me` → `401` | Not signed in, or Supabase not configured | Sign in; set the Supabase variables in both `.env` files |
| `GET /api/me` → `503` | Supabase auth/JWKS unreachable | Check network and `SUPABASE_URL` |
| `/api/health` shows `db.status: not_configured` | Supabase URL/key missing | Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` |
| Frontend can't read an env value | Missing `VITE_` prefix, or built before editing `.env` | Rename the variable; rebuild with `npm run build` |
| Settings look ignored | Environment variable overrides the file | Unset the OS variable, or edit that value |
| `npm run dev` port busy | Port 5173 in use | `npm run dev -- --port 5174`, and add that origin to `FRONTEND_ORIGINS` |

---

## 11. Production environment differences

### Local development

- Backend API: `http://127.0.0.1:8000`
- CORS: localhost Vite origins
- Frontend: Vite dev server at `http://127.0.0.1:5173`
- Frontend `VITE_API_BASE_URL`: `http://127.0.0.1:8000`

### Production

Backend environment:

- Real `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- `FRONTEND_ORIGINS` set to the **exact** deployed frontend origin(s).
- Optional `GEMINI_API_KEY` and `GEMINI_MODEL`.

Frontend build environment (must be set **before** `npm run build`):

- `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`.
- `VITE_API_BASE_URL` set to the deployed FastAPI HTTPS URL.

Local `.env` files are **not** uploaded to a hosting platform automatically;
configure the same variables there. Changing a `VITE_` value requires a new
build. No secrets belong in `VITE_` variables, and the publishable key is the
only Supabase key that may appear in the frontend.
