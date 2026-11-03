# 03 Data model (SQLite)

Audio is **not** stored by default. `consent` gates anything beyond transcript storage.

```sql
PRAGMA foreign_keys=ON;
CREATE TABLE person(id INTEGER PRIMARY KEY, name TEXT NOT NULL, relationship TEXT,
  created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE consent(id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK(scope IN ('transcript','share_public','voice_clone')),
  granted_at TEXT NOT NULL, revoked_at TEXT, note TEXT);
CREATE TABLE hand_profile(id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE, label TEXT NOT NULL);
CREATE TABLE weighing(id INTEGER PRIMARY KEY, hand_profile_id INTEGER NOT NULL REFERENCES hand_profile(id) ON DELETE CASCADE,
  unit TEXT NOT NULL, ingredient TEXT NOT NULL DEFAULT 'any', amount REAL NOT NULL CHECK(amount>0),
  amount_unit TEXT NOT NULL CHECK(amount_unit IN ('g','ml')), note TEXT, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE recipe(id INTEGER PRIMARY KEY, title TEXT NOT NULL, cook_person_id INTEGER REFERENCES person(id),
  narrator_person_id INTEGER REFERENCES person(id), language TEXT, base_servings REAL, source_note TEXT,
  current_version_id INTEGER, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE recipe_version(id INTEGER PRIMARY KEY, recipe_id INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
  version INTEGER NOT NULL, transcript TEXT NOT NULL, parser_mode TEXT CHECK(parser_mode IN ('rules','llm','hybrid')),
  llm_provider TEXT, created_at TEXT DEFAULT (datetime('now')), UNIQUE(recipe_id, version));
CREATE TABLE step(id INTEGER PRIMARY KEY, version_id INTEGER NOT NULL REFERENCES recipe_version(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL, text TEXT NOT NULL, timer_seconds INTEGER, UNIQUE(version_id, idx));
CREATE TABLE quantity(id INTEGER PRIMARY KEY, step_id INTEGER NOT NULL REFERENCES step(id) ON DELETE CASCADE,
  ingredient TEXT, ingredient_class TEXT, qty REAL, qty_max REAL, unit TEXT, to_taste INTEGER NOT NULL DEFAULT 0,
  raw_phrase TEXT NOT NULL, confidence REAL, needs_clarification INTEGER NOT NULL DEFAULT 0);
CREATE TABLE clarification(id INTEGER PRIMARY KEY, quantity_id INTEGER NOT NULL REFERENCES quantity(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, question TEXT NOT NULL, options_json TEXT NOT NULL, answer TEXT, answered_at TEXT);
CREATE TABLE tag(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE recipe_tag(recipe_id INTEGER REFERENCES recipe(id) ON DELETE CASCADE, tag_id INTEGER REFERENCES tag(id) ON DELETE CASCADE, PRIMARY KEY(recipe_id, tag_id));
CREATE TABLE collection(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE collection_recipe(collection_id INTEGER REFERENCES collection(id) ON DELETE CASCADE, recipe_id INTEGER REFERENCES recipe(id) ON DELETE CASCADE, PRIMARY KEY(collection_id, recipe_id));
CREATE TABLE llm_cache(key TEXT PRIMARY KEY, provider TEXT, model TEXT, request_json TEXT, response_json TEXT, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE api_usage(id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')), service TEXT CHECK(service IN ('stt','tts','vc','llm')),
  endpoint TEXT, audio_seconds REAL, chars INTEGER, credits_est REAL, ok INTEGER, error TEXT);
CREATE TABLE eval_case(id INTEGER PRIMARY KEY, case_key TEXT UNIQUE NOT NULL, person_id INTEGER REFERENCES person(id),
  utterance_text TEXT NOT NULL, ingredient TEXT, unit TEXT, qty REAL, truth_amount REAL, truth_unit TEXT, replicate INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE eval_run(id INTEGER PRIMARY KEY, ts TEXT DEFAULT (datetime('now')), git_sha TEXT, config_json TEXT,
  coverage REAL, mean_rel_width REAL, median_abs_err REAL, parse_f1 REAL, notes TEXT);
```

Notes: `qty_max` holds the upper end of spoken ranges ("panch-chhoy"). `api_usage.credits_est` stays NULL until the real credit cost per call is measured (task M2). Deleting a person cascades to consents, hand profiles and weighings; recipes keep attribution text but unlink the person.
