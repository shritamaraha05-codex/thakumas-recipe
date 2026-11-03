# Thakuma's Recipe (ঠাকুমার রান্না): project pack

Voice-first recipe capture for Bengali home cooking. A cook narrates a recipe with vague measures ("ek muthi chal, ek chimti nun, jol ta jemon lage"). The system produces steps, converts each vague measure into an **honest range** (never fake-precise grams), lets each person **calibrate their own hand**, and cooks hands-free. Built for Gnani AI's Great Indian AI Internship Challenge (deadline **Tue 10 Nov 2026, 11:59 PM IST**). Team of two: **Mrinmoy** and **Shritama**.

## How to use this pack
1. Give your coding agent `AGENTS.md` first (copy it to `CLAUDE.md` / `GEMINI.md` / `.cursorrules` as your tool expects), then the docs in the order below.
2. Work by **task ID** from `docs/12_TASKS.md` (M-x = Mrinmoy, S-x = Shritama, J-x = joint).
3. Log your own work in `contributions/LEDGER.md` the same day (see `docs/14_CONTRIBUTIONS.md`).

## Read order
| File | What it settles |
|---|---|
| docs/00_CONTEXT.md | Challenge rules, constraints, what is verified vs not |
| docs/01_PRODUCT.md | Vision, feature IDs, priorities, acceptance criteria |
| docs/02_ARCHITECTURE.md | Components, repo layout, flows, config |
| docs/03_DATA_MODEL.md | SQLite schema |
| docs/04_API.md | REST and WebSocket contract (+ `docs/fixtures/`) |
| docs/05_PARSER_SPEC.md | Parsing pipeline, LLM contract, ambiguity, test cases |
| docs/06_UNITS_REFERENCE.md | Unit table, hand profiles, interval maths |
| docs/07_GNANI_INTEGRATION.md | Verified Gnani API facts, chunking, budget |
| docs/08_LLM_PROVIDERS.md | Gemini / Ollama / Evon-on-Kaggle, fallback chain |
| docs/09_UI_UX.md | Kantha design system, screens, motion, a11y |
| docs/10_EVAL_PLAN.md | How we measure accuracy honestly |
| docs/11_PRIVACY_CONSENT.md | Consent, data handling |
| docs/12_TASKS.md | Day-by-day plan and ownership |
| docs/13_DEMO_AND_POST.md | Demo script, posts, submission checklist |
| docs/14_CONTRIBUTIONS.md | Contribution tracking format and git rules |

## Also included
- `prototype_v0/`: the first rough prototype (rule parser + tiny UI). Useful as a starting point for `parse/` and tests. **Not** the architecture to keep; refactor per `02_ARCHITECTURE.md`.
- `contributions/`, `scripts/contrib_report.py`, `.github/`: contribution tracking, CODEOWNERS, PR template.
- `kaggle/`: notes for the optional Evon-on-Kaggle experiment.

## Things nobody has verified yet (do not treat as facts)
- Every gram value in the unit table (they are starting estimates).
- Gnani's live API behaviour: the docs were read, nothing was run against the live service.
- Whether Evon can be served on Kaggle's free GPUs (2-hour timebox, see `08_LLM_PROVIDERS.md`).
- The exact wording of the challenge's contribution and submission requirements (re-read the registration page and form).
- Dates assume today is Tue 3 Nov 2026. If not, shift the days; the deadline does not move.
