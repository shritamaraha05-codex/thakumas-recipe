# 10 Evaluation plan (TRU-1, TRU-2)

Goal: replace our guesses with measured evidence and publish it honestly, good or bad. This is what makes the project hard to copy.

## Data (owner: Shritama, in a real kitchen)
- 2-3 cooks (a family cook plus the two of us), consent recorded per `11_PRIVACY_CONSENT.md`.
- For each case the cook **says the phrase while taking the amount in hand** ("ek muthi chal"), puts it on a kitchen scale, we log grams. **3 replicates per case**, >=25 cases (target 75 weighings). Cover muthi, chimti, kap/cup, chamoch (tsp and tbsp), bati, glass across rice, dal, flour, salt, sugar, oil/water.
- Store in `eval/cases/cases.csv`: `case_key, person, utterance, ingredient, unit, qty, truth_amount, truth_unit, replicate, date, notes`. Use synthetic or consented data only; no audio committed.
- Also record >=10 real narrations (1-3 min) for the end-to-end check; keep audio local, commit only transcripts.

## Splits (never score on calibration data)
Per (person, unit, ingredient): calibrate with replicate 1 (n=1) and test on replicates 2-3; calibrate with replicates 1-2 (n=2) and test on replicate 3; "typical" baseline uses the reference table only.

## Metrics
- **Coverage**: share of true values inside the predicted interval, for `typical`, `yours n=1`, `yours n=2`.
- **Width**: mean of (hi-lo)/midpoint. Always report with coverage (wide intervals trivially cover).
- **Midpoint error**: median absolute error of the interval midpoint, in grams and %.
- **Parse quality**: item-level precision/recall/F1 for rules, LLM, hybrid on `parse_cases.yaml` plus eval utterances.
- **End-to-end**: parse F1 from real Prisma transcripts vs gold text (shows speech-recognition loss).
- **Silent-wrong rate**: items with a wrong ingredient/unit/qty and no clarification flag.
- Targets: coverage 80-90% after calibration. Do not tune constants on test replicates; tune on a separate split, then freeze.

## Harness (`eval/harness.py`)
`python eval/harness.py --cases eval/cases/cases.csv --out eval/report.md --json eval/latest.json`. Calls `units.ranges` and `parse` directly (no network). Writes `eval_run` rows. The accuracy page reads `/api/eval/latest`.

## Report (`eval/report.md`)
Setup (people, n, dates), table per unit (coverage, width, error, typical vs yours n=1/2), parse P/R/F1 per mode, worst failures with causes, limits ("one household, small n, not generalisable"), and what we changed because of the results.

## Honesty rules
Report failures, n and intervals. Do not claim accuracy beyond the sample. Keep `status` in `reference.yaml` in sync with what was actually measured.
