# Prototype audit (`prototype_v0/`)

- **Task:** M-01
- **Owner:** Mrinmoy
- **Date:** 2026-11-03
- **Method:** read `prototype_v0/{README.md,app.py,core.py,requirements.txt,tests/test_core.py}` and `docs/05_PARSER_SPEC.md`; ran the existing tests; ran the prototype parser against the 25 required cases in `docs/05_PARSER_SPEC.md` (read-only probe, no files changed).
- **Verdict:** the prototype's **rule parser (`core.py`) is worth reusing as a reference and as raw material**. The web app (`app.py`) is not; it is replaced by the new `backend/` structure.

This file records facts. It does not refactor the prototype. `prototype_v0/**` is untouched.

---

## 1. Test state (measured, not estimated)

Command run from the repository root:

```
python -m pytest prototype_v0/tests/test_core.py -q
```

Result:

```
.....                                                                    [100%]
5 passed in 0.05s
```

The prototype's own runner (`python prototype_v0/tests/test_core.py`) also prints all five as `ok`.

| Test | What it asserts | Result |
|---|---|---|
| `test_basic` | `ek muthi chal, ek chimti nun, jol ta jemon lage` -> 1 step, rice range `(30, 50)`, salt in `g`, water `to_taste` | pass |
| `test_bengali_script_and_halves` | Bengali digits/`আড়াই কাপ জল` = 2.5 cups, `lo=375`; `sarhe tin chamoch` = 3.5 | pass |
| `test_calibration_narrows` | weighing `muthi|rice=[38]` -> range `(32, 44)`, basis `yours` | pass |
| `test_timer_and_split` | `dosh minute ... tarpor ...` -> step 1 timer 10, 2 steps | pass |
| `test_spelling_variants_and_commands` | `mutho` -> `muthi`; `পরের` -> `next`; `abar bolo` -> `repeat` | pass |

**Pre-existing lint:** `ruff check .` reports **5 errors, all inside `prototype_v0/`** (`E401` x3, `E702` x2). They predate this work. Because M-01 must not modify the prototype, they are excluded from the new backend lint config (see `pyproject.toml`) and are **not** fixed here.

---

## 2. What the prototype does

`core.py` is a single-file, offline, rule-based parser (no network, no LLM). `app.py` wraps it in a small FastAPI app that also talks to Gnani STT/TTS. The whole parser is ~120 effective lines.

### Functions and responsibilities

| Function | Responsibility | Reuse? |
|---|---|---|
| `_table(rows)` | Builds `word -> canonical value` lookup dicts from space-separated word lists | **Yes** — same idea goes into `parse/lexicon.py` |
| `r(x)` | Rounding rule: `<10` -> 1 decimal, else integer | **Yes**, but replace with the display rounding in `docs/06` (`<1 -> 0.1`, `<10 -> 0.5`, ...) |
| `norm(t)` | Lowercase; Bengali digits -> ASCII; split `50g`; punctuation/newlines -> `\|`; unit phrases (`choto chamoch` -> `tsp`); taste phrases -> `<taste>`; connectors -> boundary | **Yes, concept** — becomes `parse/normalize.py`; must be rewritten for clarity and fixed (see bugs) |
| `num(tok)` | Token -> number: word table, `a/b` fractions, plain float | **Yes, extended** |
| `look(tok, table)` | Lexicon lookup with suffix stripping (`-ta -ti -tuku -gulo ...`) then fuzzy match (`difflib`, cutoff 0.85, ASCII >=4 chars) | **Yes, extended** (spec wants 0.85; keep) |
| `measure(qty, unit, key, cls, cal)` | Quantity -> `{lo, hi, unit, basis}`; exact units pass through; vague units use table row; calibration widens/narrows | **Yes, rewrite** into `units/ranges.py` (spec interval maths, basis `exact/yours/typical`) |
| `clause(toks, cal)` | Scans one clause for numbers/unit/ingredient/duration/taste; picks quantity before unit; returns item + duration | **Yes, replace** with a documented token pass in `parse/rules.py` |
| `parse(text, cal)` | Splits on `\|`, per segment scans clauses split on `,` / `ar` / `ও` / `and`, returns `steps[{i, text, items, timer_min}]` | **Partly** — segmentation idea survives; output shape does **not** |
| `command(text)` | Matches a transcript against `CMD` word sets -> `next/prev/repeat/stop` | **Yes** — becomes `cook` command normaliser (M-22) |

### Lexicons present

- `NUM`: number words (Bengali, Roman Bengali, a few Hindi), fractions, `sarhe`(+0.5), halves (`adha`, `der`, `arai`).
- `UNIT`: `muthi, chimti, cup, spoon, tsp, tbsp, bowl, glass, poa, chhatak, ser, g, kg, ml, litre`.
- `DUR`: `minute(s)`, `ghonta/hour`.
- `ING`: ingredient -> `(canonical, class)`; classes `grain|flour|salt|sugar|liquid|spice|produce|herb`.
- `D`: `(unit, class) -> (lo, hi, out_unit)` starting estimates — matches the `docs/06` table.
- `EXACT`: `g, kg, ml, litre` exact conversions.
- `BREAK`, `TASTE_P`, `UNIT_P`, `SUF`, `AND`, `SARHE`, `CMD`.

### Normalisation (Bengali + Roman Bengali)

- Bengali digits `০১২৩৪৫৬৭৮৯` -> ASCII via `str.maketrans`.
- Lowercasing; `50g` -> `50 g`; `.`/`!`/`?`/`;`/newlines/punctuation -> step boundary token `\|`; commas kept as clause separators.
- Compound Bengali units resolved (`ছোট চামচ`/`choto chamoch` -> `tsp`; `boro/bড় chamoch` -> `tbsp`).
- Taste phrases (`jemon lage`, `ektu`, `স্বাদমতো`, `to taste`, ...) -> `<taste>` sentinel.
- Connectors (`tarpor, erpor, ebar, then, phir, তারপর, এরপর, ...`) -> boundary.
- **No Devanagari digit translation** (only Bengali digits are translated).
- **No English number words** (`one`, `two`) except those listed as Roman Bengali.

### Quantity/range logic

- Exact units multiply by factor and set `lo == hi` with `basis="exact"`.
- Vague units look up `(unit, class)` then `(unit, "*")` and multiply by quantity -> `lo/hi`, `basis="typical"`.
- Calibration (`{unit|ingredient: [g...]}`): n=1 -> `value * [0.85, 1.15]`; n>=2 -> `[min*0.95, max*1.05]`; `basis="yours"`.
- Spoken ranges (`5-6`, `tin-char`) are **not** parsed.

### Step segmentation

- Primary boundary: the `\|` marker inserted by `norm` (sentence punctuation, newlines, connectors).
- Clause split inside a segment on `,` and the `AND` set.
- One item per clause (first unit + first ingredient), quantity chosen from the number immediately before the unit.
- Original segment text is kept on each step (`text` field).

---

## 3. Measured behaviour against `docs/05` (25 required cases)

I ran the prototype against all 25 cases with a read-only script. Summary: **~15 cases extract correctly; 10 fail or are incomplete.**

Legend: OK = correct extraction; PART = extraction right but a required clarification is missing; FAIL = wrong or empty.

| # | Input | Expected (docs/05) | Prototype | Status |
|---|---|---|---|---|
| 1 | ek muthi chal | rice 1 muthi | rice 1 muthi | OK |
| 2 | আড়াই কাপ জল | water 2.5 cup +unit_cup | water 2.5 cup | PART (no clarification) |
| 3 | sarhe tin chamoch tel | oil 3.5 spoon +unit_spoon | oil 3.5 spoon | PART (no clarification) |
| 4 | der kilo alu | potato 1.5 kg = 1500 g | 1500 g exact | OK |
| 5 | adha kap dudh | milk 0.5 cup +unit_cup | milk 0.5 cup | PART (no clarification) |
| 6 | dosh minute dhimi anche | timer 600 s | timer 10 min | OK |
| 7 | ek ghonta bhapa dao | timer 3600 s | timer 60 min | OK |
| 8 | nun jemon lage | salt to_taste | salt to_taste | OK |
| 9 | duto peyaj kuchi kore | onion 2 pc | onion 2 pc | OK |
| 10 | ek chimti holud | turmeric 1 chimti | turmeric 1 chimti | OK |
| 11 | ek poa chal | rice 1 poa | rice 1 poa | OK |
| 12 | du chamoch chini | sugar 2 spoon | **empty** (`du` not in `NUM`) | FAIL |
| 13 | ek ser dudh | milk 1 ser | milk 1 ser | OK |
| 14 | panch-chhoy ta lonka | chilli 5-6 pc | **empty** (hyphen range) | FAIL |
| 15 | tin-char muthi chal | rice 3-4 muthi | **empty** (hyphen range) | FAIL |
| 16 | ektu tel | oil to_taste | oil to_taste | OK |
| 17 | ek muthi chal ar ek muthi dal | rice 1 muthi; lentils 1 muthi | both | OK |
| 18 | chal ta dhuye nao, tarpor ek glass jol dao | 2 steps; water 1 glass | 2 steps; water 1 glass | OK |
| 19 | ek choto chamoch nun | salt 1 tsp, no question | salt 1 tsp | OK |
| 20 | ek chamoch... na na dui chamoch chini | sugar 2 spoon (self-correction) | 2 steps, no ingredient merge | FAIL |
| 21 | ek muththi chawal aur ek chutki namak | rice 1 muthi; salt 1 chimti | both | OK |
| 22 | आधा कप दूध | milk 0.5 cup | **empty** (Devanagari) | FAIL |
| 23 | one cup water | water 1 cup | **empty** (`one`) | FAIL |
| 24 | char jon er jonno | base_servings 4 | **empty** (servings) | FAIL |
| 25 | ek muthi (no ingredient) | muthi +ingredient_missing | unit found, **no clarification** | FAIL |

### Limitations and bugs found

1. **No clarification engine.** Cases 2, 3, 5, 25 need `unit_cup` / `unit_spoon` / `ingredient_missing` questions. The prototype never asks; this is a hard requirement (UND-3, `docs/05` ambiguity table).
2. **No output contract.** `parse()` returns `steps[{i, text, items, timer_min}]`. Missing vs `docs/04`: `recipe`/`meta` wrapper, stable quantity `id`s, `raw_phrase`, `confidence`, `source`, `ingredient_class`, `qty_max`, `range.basis` is present but `range` is a bare dict, `to_taste` only appears on taste items, timers are in **minutes** not `timer_seconds`.
3. **No provenance.** No `raw_phrase` capture and no `source='rules|llm|both'`, so the "LLM suggests, code decides" validation (substring check) cannot be built on this output.
4. **Spoken ranges missing.** `panch-chhoy`, `tin-char`, `N-M`, `N M ta` are all unhandled (cases 14, 15). No `qty_max`.
5. **Number vocabulary gaps.** `du` (case 12), English `one/two/three` (case 23), Devanagari digits and the Devanagari number/unit words used in case 22.
6. **No servings parsing.** `char jon er jonno` is ignored; `base_servings` is never produced.
7. **No self-correction.** Case 20 is split into two steps instead of "the later number replaces the earlier one".
8. **First-match-only clauses.** `clause()` keeps the first unit and first ingredient (`unit = unit or ...`); mixed clauses are lossy.
9. **Fuzzy matching is lexicon-internal only.** It never surfaces "unknown unit/ingredient" candidates, so unknown words are silently dropped rather than flagged.
10. **`norm` artefacts.** Unit/taste replacement inserts padded spaces (`" tsp "`) and can leave doubled spaces and a `to taste` artefact in displayed text (e.g. case 19 shows `ek  tsp  nun`, case 16 `to taste tel`). The original text is not cleanly preserved as required by rule 5 ("her words stay").
11. **Timers heuristic.** A duration word is only recognised when a number sits immediately before it; "dhimi anche" and word order are not generalised.
12. **Calibration does not do class fallback.** `docs/06` step 2 (same unit, other ingredient in same class) is not implemented.
13. **Regex for decimals.** `re.sub(r"\.(?!\d)", ...)` protects decimals, but `num()` would also parse standalone digit tokens fine; the split `50g` only handles `digit`+`letter`, not `digit`+`kg` etc. (it does, since `kg` is letters — acceptable).
14. **Lint debt** in the prototype (`E401`, `E702`), left as-is by design.

---

## 4. Recommendation: what to extract into the new backend

Do **not** copy the prototype forward wholesale and do **not** rewrite it in place. Extract function-by-function into the architecture in `docs/02`, each with its own tests, and only then delete reliance on `prototype_v0`.

| Prototype piece | New home | Notes |
|---|---|---|
| `norm` (concept + tables) | `backend/app/parse/normalize.py` (M-05) | Rebuild cleanly; translate Bengali **and** Devanagari digits; preserve original text untouched (rule 5); return structured segments, not a `\|`-joined string |
| `BREAK`/`AND`/connector lists | `parse/segment.py` (M-06) | Boundaries + connectors + speaker turns; merge <2-token fragments |
| `NUM/UNIT/DUR/ING` + `look` suffix/fuzzy | `parse/lexicon.py` (M-07) | Each alias -> one canonical value; add `du`, English numerals, Devanagari; expose "unknown" instead of dropping |
| `clause` token scan | `parse/rules.py` + `parse/schema.py` (M-08) | Emit the full `Quantity` contract: `raw_phrase`, `source="rules"`, `confidence`, `qty_max`, `ingredient_class` |
| `measure` | `backend/app/units/ranges.py` (M-13) | Exact vs interval; basis `exact/yours/typical`; use `docs/06` rounding |
| `D` table | `backend/app/units/reference.yaml` (M-12) | Every row needs `source` + `status`; unverified rows labelled |
| calibration branch of `measure` | `backend/app/units/hands.py` (M-17) | Add class fallback from `docs/06` |
| (nothing yet) | `parse/ambiguity.py` (M-15) | New: clarifications for spoon/cup/missing ingredient |
| `parse()` wrapper | `parse/` pipeline + `llm/` chain (M-08, PLT-1) | Output must satisfy the new `ParseResult` model |
| `command()` | `backend/app/parse` or cook module (M-22) | Keep the word-set idea |

### What must be deleted from the mental model

- The `{"steps": [...]}` API shape — replaced by `ParseResult` (`docs/04`).
- `timer_min` — replaced by `timer_seconds`.
- The idea that a rule result is the final answer — it becomes one `source` in a merged, validated result.

### Reuse priority for this week

1. **High:** `norm` concepts, `look` (suffix + fuzzy), `NUM/UNIT/ING` data, `measure` interval maths, step-splitting. These are directly on the M-05..M-13 critical path.
2. **Medium:** `command`, `DUR`, calibration bounds.
3. **Low / rewrite:** `parse()` output shape, `clause` internals.

---

## 5. Known risks carried forward

- The `D` estimates are unverified (`docs/06`); the prototype test suite bakes `(30, 50)` in, so tests must not be copied verbatim into the new suite — the new suite should assert ranges through `units/ranges.py`, not hard-coded numbers.
- The prototype's tests import `core` by mutating `sys.path`; the new tests import the `backend` package normally.
- `prototype_v0` lint errors are excluded from `pyproject.toml`, not fixed, to respect folder ownership.

**Conclusion:** keep `prototype_v0/core.py` as a tested reference. Move its lexicon, matching and interval maths into `backend/app/parse/` and `backend/app/units/` behind the new Pydantic contract, add the missing ambiguity/serving/range/self-correction features as separate, tested tasks, and retire `app.py` in favour of `backend/app/main.py`.
</content>
