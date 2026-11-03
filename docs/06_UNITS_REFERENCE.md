# 06 Units reference and hand profiles

## Status: **nothing below is sourced yet**
The numbers are starting estimates from the prototype. Every row in `reference.yaml` must carry `source` and `status` (`unverified | measured | published`). The UI labels unverified rows "typical (unverified)". Task M7 and eval S8 turn them into measured/published rows.

## Row format
```yaml
- unit: muthi          # canonical unit
  class: grain         # grain|flour|salt|sugar|spice|liquid|produce|herb|*
  lo: 30
  hi: 50
  out: g               # g or ml
  status: unverified
  source: "prototype estimate; replace with own weighing (n>=5)"
```

## Starting table (unverified)
| unit | class | lo | hi | out |
|---|---|---|---|---|
| muthi | grain / flour / herb / * | 30 / 25 / 5 / 25 | 50 / 45 / 15 / 50 | g |
| chimti | salt / spice / sugar / * | .3 / .2 / .5 / .3 | 1 / .8 / 1.5 / 1 | g |
| cup | grain / flour / sugar / * | 120 / 90 / 150 / 150 | 200 / 130 / 220 / 240 | g (ml for `*`) |
| spoon (unspecified) | liquid / * | 5 / 3 | 15 / 15 | ml / g |
| tsp | liquid / * | 4 / 2 | 6 / 6 | ml / g |
| tbsp | liquid / * | 12 / 8 | 15 / 18 | ml / g |
| bowl (bati) | liquid / * | 150 / 120 | 250 / 220 | ml / g |
| glass | liquid / * | 200 / 150 | 300 / 220 | ml / g |
| poa | liquid / * | 220 | 250 | ml / g |
| chhatak | liquid / * | 55 | 62 | ml / g |
| ser | liquid / * | 930 | 1000 | ml / g |
Exact units: g, kg (x1000), ml, litre (x1000).

Reference points to verify (not facts we have checked): metric teaspoon 5 ml, tablespoon 15 ml, US cup 240 ml, metric cup 250 ml; traditional *ser* about 80 tola (~933 g), *poa* a quarter ser, *chhatak* a sixteenth. Candidate sources to check: USDA FoodData Central portion weights for household measures; Indian national nutrition institute publications; our own weighing.

## Hand profile resolution
For (person, unit, ingredient) use the first that exists:
1. Weighings for `unit|ingredient` -> basis `yours`.
2. Weighings for the same unit with another ingredient in the same class -> basis `yours`, flagged lower trust.
3. Reference row `(unit, class)` then `(unit, *)` -> basis `typical`.

Personal interval (heuristic, to be tuned by eval): n=1 -> value x [0.85, 1.15]; n>=2 -> [min x 0.95, max x 1.05].

## Interval maths
- Item: `lo = qty_lo x unit_lo`, `hi = qty_hi x unit_hi` (`qty_hi = qty_max or qty`).
- Totals across items: sum of lows and sum of highs (worst case, honest and simple).
- Scaling by factor f: multiply both ends. Rounding for display: <1 g -> 0.1; <10 -> 0.5; <100 -> 1; <1000 -> 5; >=1000 -> 50.
- Display: "about 33-44 g" plus basis tag. Never a single number for a vague unit.

## Start-low rule (QTY-4)
Classes `salt`, `spice` (including chilli): when f > 1.5, show "start at {lo x f}, taste, add up to {hi x f}" instead of one scaled range.

## "Tighten this recipe" (QTY-5)
For each distinct (unit, ingredient) in the recipe with zero weighings: `impact = (hi - lo) x qty x occurrences`. Return the top 3 by impact with a sentence: "Weigh one muthi of rice: it narrows 4 steps."
