# 14 Contribution tracking

The programme interviews teammates separately and expects each person's contribution to be clear. **I have not seen the exact form wording; match this format to it.** The goal: anyone can verify, from evidence, who built what.

## Ownership map
| Area | Primary | Secondary (reviewer) |
|---|---|---|
| backend/ (gnani, parse, llm, units, db, routers), kaggle/ | Mrinmoy | Shritama |
| frontend/, design system | Shritama | Mrinmoy |
| eval/ (data, harness, report, accuracy page) | Shritama | Mrinmoy |
| docs/ API + parser + units + LLM + Gnani | Mrinmoy | Shritama |
| docs/ UI/UX, eval, demo, post | Shritama | Mrinmoy |
| contributions/, README, submission | both write their own part | |

## Rules
1. **Own identity.** Each person commits from their own GitHub account (`git config user.name/email` must match). No shared accounts, no committing as the other person.
2. **Branches and PRs.** `m/<task>` and `s/<task>`; PR per task using the template; the **other** person reviews. Do not squash-merge (keeps attribution).
3. **Commit prefixes.** `[BE] [FE] [EV] [DOC] [JOINT] M4: message`. Pair work: add `Co-authored-by:` trailers.
4. **Ledger daily.** Each person records their own work in `contributions/LEDGER.md` the same day, with evidence links. Never write the other person's entries.
5. **AI-assist disclosure.** Mark `AI-assisted: yes/no` and the tool. You must be able to explain every line you claim.
6. **Be exact.** Log help as "assist", not ownership. Do not inflate. The git report (`python scripts/contrib_report.py`) is supporting evidence; lines of code are a weak signal.

## Ledger columns
`Date | Person | Task ID | What I did (1 line) | Evidence (PR/commit/file/screenshot) | Reviewed by | AI-assisted | Hours (optional)`

## Evidence that counts
PR and commit links, files you authored, tests you wrote, screenshots of your UI, eval data you collected, recordings of your demo role, review comments you left.

## Interview preparation (answer without notes)
**Mrinmoy**: why rules first and LLM second; "LLM suggests, code decides"; the interval maths and why ranges; how fallback and replay work; chunking and the one-request lock; schema design; what fails and how you would measure it; what Kaggle/Evon taught you.
**Shritama**: the kantha design decisions; how range maps to the grain pour; capture UX and WAV chunking; accessibility choices; the evaluation protocol, results and limits; what the demo does not show.
**Both**: what the product does and why not exact grams; how the other's half fits; the three biggest limitations; what you would do with another month.

## Files
`contributions/LEDGER.md`, `contributions/daily/TEMPLATE.md`, `contributions/SUBMISSION_STATEMENT.md`, `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `scripts/contrib_report.py`.
