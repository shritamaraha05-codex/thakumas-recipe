# Parser evaluation report (M-11)

- Dataset version: 1.0.0
- Evaluated at: 2026-11-07T23:00:45+00:00
- Parser: rules
- Provider: n/a
- Model: n/a
- Cases: 21 total, 21 evaluated, 0 not evaluated

## Metrics

| Metric | Value |
|---|---|
| Ingredient precision | 100.0% |
| Ingredient recall | 100.0% |
| Ingredient F1 | 100.0% |
| Ingredient TP / FP / FN | 35 / 0 / 0 |
| Quantity accuracy (full match) | 17/18 (94.4%) |
| Quantity association accuracy | 17/18 (94.4%) |
| Numeric quantity correct | 13/14 |
| Explicit range correct | 1/2 |
| Unit correct | 17/18 |
| Vague quantity preserved | 2/2 |
| Taste quantity preserved | 2/2 |
| Duration recall (value + unit) | 3/3 (100.0%) |
| Duration value correct | 3/3 |
| Duration unit correct | 3/3 |
| Durations wrongly attached to ingredients | 0 |
| Clarifications preserved | 3/3 (100.0%) |
| Ambiguity violations | 0 |
| Negative expectations preserved | 10/10 (100.0%) |
| Evidence grounding | 64/64 (100.0%) |
| Unsupported assertions | 0/47 (0.0%) |

## Per-case failures

### c21_range_classifier_chilli_roman (roman)
- Transcript: panch-chhoy ta lonka
- Expected ingredients: chilli
- Actual ingredients: chilli
- Quantity: chilli: expected kind=range qty=5.0 qty_max=6.0 unit=None; observed no-quantity


## Reading this report

This is a small, manually curated golden set. A high score here shows that the documented cases are handled; it does not prove that every Bengali dialect, spelling variant or cooking style is supported.
