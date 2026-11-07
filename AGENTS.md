# AGENTS.md: instructions for the coding agent

## Mission
Build "Thakuma's Recipe" as specified in `docs/`. Read `docs/00`–`docs/14` before writing code. The human who directs you owns the work and must be able to explain every line.

## Golden rules
1. **Ranges, not points.** A vague unit becomes `{lo, hi, unit, basis}`. Never output a single gram value for a vague measure. `basis` is one of `exact | yours | typical`.
2. **The LLM suggests, code decides.** LLMs extract `{ingredient, qty, unit, raw_phrase}` only. All unit maths, ranges, scaling and storage happen in deterministic code. An LLM output whose `raw_phrase` is not a substring of the transcript is discarded.
3. **Ask, don't guess.** Ambiguity (e.g. `chamoch` = tsp or tbsp) creates a `clarification`, not a silent default.
4. **Never invent facts.** Do not add gram values, API parameters or endpoints that are not in the docs. If unsure, write `TODO(verify)` and tell the human. Unit-table rows carry `source` and `status`.
5. **Her words stay.** Keep the original narrated text next to every parsed step.
6. **Privacy by default.** Never store audio unless a consent record allows it. No real personal data in tests or fixtures. Only transcript text goes to LLM providers, with names stripped.
7. **The app must work without the LLM and without Gnani.** Rule parser + mock mode are the floor (`GNANI_MOCK=1`, `LLM_CHAIN=rules`).

## Stack and commands
- Backend: Python 3.11+, FastAPI, pydantic v2, Supabase PostgreSQL (via `SUPABASE_DB_URL`) with Supabase Auth token verification, `requests`/`httpx`, pytest, ruff.
- Frontend: React (Vite) with the Supabase Auth client; the frontend never writes to the database directly — all reads/writes go through FastAPI with the user's access token. No secrets or service-role keys in `VITE_` variables.
- Run: `uvicorn backend.app.main:app --reload`; test: `pytest -q`; lint: `ruff check .`
- Tests must never call Gnani or any LLM. Use fixtures and mocks.

## Workflow
- Pick a task ID from `docs/12_TASKS.md`; stay inside its owner's folders (see `.github/CODEOWNERS`).
- Small commits with prefix `[BE]`, `[FE]`, `[EV]`, `[DOC]`, `[JOINT]`. One topic per PR. Do not squash-merge (it erases per-commit attribution).
- Update the relevant doc in the same PR when you change a contract.
- Add or update tests with every behaviour change (parser changes need new cases in `backend/tests/parse_cases.yaml`).

## Contribution integrity (important)
- Commit under the **human's** identity, never a bot identity. Add `Assisted-by: <tool>` as a commit trailer when you generated substantial code.
- Do **not** write entries in `contributions/LEDGER.md`. The humans write their own, truthfully, including "AI-assisted: yes".
- Do not touch the other person's folders without a note in the PR.

## Definition of done
Code + tests passing + docs updated + task row marked done in `docs/12_TASKS.md` + human has read and understood the diff.

## Never
Hard-code API keys; commit `.env`; commit audio recordings; add a dependency without saying why; claim a feature works without running it; present estimates as measurements.
