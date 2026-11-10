# 05 Parser spec

Starting point: `prototype_v0/core.py` (tables, fuzzy matching, clause logic). Refactor into `backend/app/parse/`.

## Pipeline
1. **normalize**: `backend/app/parse/normalize.py` (M-05) returns `{original, text, tokens}`: the original transcript untouched; a single-line normalised form (Latin lower-cased, Bengali/Devanagari digits -> ASCII, single spaces, `50g` -> `50 g`, compound units `choto chamoch` -> `tsp`); and word/punctuation tokens each carrying spans into both the original and the normalised text. Punctuation (`। . ! ? ;`, ...) is kept as tokens (decimals and hyphen ranges intact). Boundary *marking*, the taste sentinel and speaker-label stripping belong to later stages (M-06, M-08, CAP-4).
2. **segment**: `backend/app/parse/segment.py` (M-06) splits the normalised narration into ordered `Segment`s, each keeping its `text`, exact `original_text`, original + normalised spans, leading `connector`, `boundary` reason (`start|punctuation|connector`) and `conditional` metadata. New segments begin only on sentence-final punctuation (`। . ! ? ;` and ellipsis) or a sequence connector (`প্রথমে, তারপর, এরপর, এবার, শেষে, সবশেষে, একে একে, তারপর আবার; tarpor, erpor, prothome, ebar, sheshe, then, phir, uske baad, tarpor abar`; multi-word matched longest-first). Commas, conditionals (`যখন, হলে, যতক্ষণ, যতক্ষণ না, না হলে, যখনই`) and negations never split a segment, so a condition stays attached to its action. Speaker turns and merging of <2-token fragments are deferred to capture work (CAP-4); they are not part of M-06.
3. **rules**: lexicon passes over clauses (split on `,` and `ar/ও/aur/and`): numbers (words, digits, fractions, `sarhe N`, `N-M` and `N M ta` ranges), units, ingredients, durations, taste phrases, self-correction. Suffix stripping (`-ta, -ti, -tuku, -gulo`) and fuzzy matching (cutoff 0.85, ASCII tokens >=4 letters).
4. **llm_extract** (optional): see contract below.
5. **merge/validate**: items found by both -> `source:"both"`, confidence up. LLM-only items kept only if `raw_phrase` is a substring of the normalised transcript and the unit/ingredient are in the lexicon or the LLM marks `unknown_unit`. Rules-only items kept. Numeric disagreement -> `qty_conflict` clarification.
6. **ambiguity**: see table. The user-facing review renders each clarification and submits only an offered answer to `/api/parse/resolve`; the spoken `raw_unit` and original step text remain intact. Cup-type answers do not create a volume or weight estimate until a documented conversion is available.
7. **ranges**: `units.ranges.interval(...)` for every quantity with a unit.

## Ambiguity triggers
| kind | trigger | options | resolution |
|---|---|---|---|
| unit_spoon | `chamoch` without `tsp/tbsp/choto/boro` | tsp, tbsp | sets unit |
| unit_cup | `kap/cup` and no weighing for this person | tea cup, measuring cup, my cup | picks interval / opens weighing |
| qty_conflict | rules and LLM differ | both numbers | sets qty |
| ingredient_missing | measured unit, no ingredient | likely ingredients from step context | sets ingredient |
| qty_missing | unit present, no number | 1/2/3 | sets qty (default assumed 1 with confidence 0.5 until answered) |
Spoken ranges ("panch-chhoy ta lonka") fill `qty` and `qty_max` and need no question. "ektu/jemon lage" -> `to_taste:true`.

## LLM contract
Input: normalised step text (names stripped). Output JSON only:
```json
{"items":[{"ingredient":"string|null","qty":"number|null","qty_max":"number|null","unit":"string|null",
"to_taste":false,"raw_phrase":"exact substring","unknown_unit":false}],"timer_seconds":"integer|null"}
```
System prompt (use verbatim as a starting point): *"You extract cooking quantities from a Bengali, Hindi or English recipe narration. Return JSON that matches the schema and nothing else. Never convert to grams or millilitres. Copy `raw_phrase` exactly from the input. If a quantity is vague (muthi, chimti, ektu) keep it as spoken. If unsure, omit the item. Do not invent ingredients."* Include 3 few-shot examples taken from the cases below. Temperature 0; JSON-schema/response_format if the provider supports it, otherwise validate with pydantic and retry once with "return valid JSON only".

## Required test cases (extend to >=60 in `backend/tests/parse_cases.yaml`: add script and spelling variants)
Format `ingredient|qty|unit` (`+flag`).
| # | Input | Expected |
|---|---|---|
| 1 | ek muthi chal | rice\|1\|muthi |
| 2 | আড়াই কাপ জল | water\|2.5\|cup +unit_cup |
| 3 | sarhe tin chamoch tel | oil\|3.5\|spoon +unit_spoon |
| 4 | der kilo alu | potato\|1.5\|kg (exact 1500 g) |
| 5 | adha kap dudh | milk\|0.5\|cup +unit_cup |
| 6 | dosh minute dhimi anche ranna koro | timer 600 s, no items |
| 7 | ek ghonta bhapa dao | timer 3600 s |
| 8 | nun jemon lage | salt\|-\|- to_taste |
| 9 | duto peyaj kuchi kore | onion\|2\|pc |
| 10 | ek chimti holud | turmeric\|1\|chimti |
| 11 | ek poa chal | rice\|1\|poa |
| 12 | du chamoch chini | sugar\|2\|spoon +unit_spoon (needs `du` = 2) |
| 13 | ek ser dudh | milk\|1\|ser |
| 14 | panch-chhoy ta lonka | chilli\|5-6\|pc |
| 15 | tin-char muthi chal | rice\|3-4\|muthi |
| 16 | ektu tel | oil\|-\|- to_taste |
| 17 | ek muthi chal ar ek muthi dal | rice 1 muthi; lentils 1 muthi |
| 18 | chal ta dhuye nao, tarpor ek glass jol dao | 2 steps; step 2 water\|1\|glass |
| 19 | ek choto chamoch nun | salt\|1\|tsp (no question) |
| 20 | ek chamoch... na na dui chamoch chini | sugar\|2\|spoon (self-correction replaces) |
| 21 | ek muththi chawal aur ek chutki namak | rice\|1\|muthi; salt\|1\|chimti |
| 22 | आधा कप दूध | milk\|0.5\|cup |
| 23 | one cup water | water\|1\|cup |
| 24 | char jon er jonno | base_servings 4 |
| 25 | ek muthi (no ingredient) | quantity unit muthi +ingredient_missing |

## Acceptance
Item-level precision/recall/F1 reported by `eval/harness.py`; all 25 cases pass in rules mode; LLM mode must never reduce a case that rules already pass (merge policy test).
