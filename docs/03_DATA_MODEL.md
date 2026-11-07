# 03 Data model (Supabase PostgreSQL)

Audio is **not** stored by default. `consent` gates anything beyond transcript storage.

## Three identities that must never be merged

1. **Account user** — the owner of the Supabase Auth account (`auth.users`). This identity owns saved recipes. Created only by Supabase Auth at sign-up; we never store passwords ourselves.
2. **Cook / narrator person** — the family member who prepared or narrated the recipe. A grandmother can narrate a recipe and never have a Thakuma's Recipe login.
3. **Measurement profile** — the person (hand) whose traditional measures are being calibrated by weighing. Postponed with the calibration tasks (see `docs/12_TASKS.md` §1).

An account user can save a recipe narrated by another family member; a narrator needs no account. These three concepts stay in separate structures and are never collapsed into one "user" entity.

## Minimum schema for this release

Cloud-hosted PostgreSQL (via Supabase). The initial SQL migration (task M-18A) creates exactly these three tables. The complete parsed recipe is stored as one JSONB document — there are **no** relational ingredient/step tables in this MVP.

```sql
-- profiles: the application-facing part of an auth.users row.
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- recipes: owned by an account user. Ownership is mandatory.
create table recipes (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index recipes_owner_user_id_idx on recipes(owner_user_id);

-- recipe_versions: every version keeps the exact original transcript and the
-- complete ParseResult JSON. The newest version is the default recipe view.
create table recipe_versions (
  id uuid primary key default gen_random_uuid(),
  recipe_id uuid not null references recipes(id) on delete cascade,
  version_number integer not null check (version_number > 0),
  original_transcript text not null,
  draft jsonb not null,
  created_at timestamptz not null default now(),
  unique (recipe_id, version_number)
);
```

Relationship rules enforced by the schema and the repository:

- One account user owns many recipes; `owner_user_id` is `NOT NULL` — a recipe without an owner cannot exist.
- One recipe has many versions; `version_number` increases sequentially per recipe (`unique(recipe_id, version_number)`).
- Every version preserves the exact original transcript (`original_transcript`) and the complete `ParseResult` JSON (`draft`, see `docs/05_PARSER_SPEC.md` and `docs/fixtures/parse_result.sample.json`). Her words stay beside the numbers, verbatim (golden rule 5).
- Cascade: deleting a cascades to its versions (`on delete cascade`); deleting the owner account cascades to their recipes.
- "Newest version is the default view" is decided by code (highest `version_number`, or latest `created_at` for ties) — `POST /api/recipes` writes version 1.

## Row Level Security

RLS is enabled for every user-owned application table. A user can access only their own data:

```sql
alter table profiles enable row level security;
alter table recipes enable row level security;
alter table recipe_versions enable row level security;

-- Profiles are private to their owner, except intentionally exposed fields.
create policy "profiles are self-visible" on profiles
  for select using (auth.uid() = id);
create policy "profiles are self-writable" on profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

-- A user can read and write only their own recipes, and can never reassign
-- ownership to someone else: owner_user_id must match their own auth uid.
create policy "recipes are owner-scoped" on recipes
  for all using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

-- Versions are reachable only through a recipe the user owns.
create policy "recipe_versions follow the recipe owner" on recipe_versions
  for all using (
    exists (select 1 from recipes r where r.id = recipe_id and r.owner_user_id = auth.uid())
  )
  with check (
    exists (select 1 from recipes r where r.id = recipe_id and r.owner_user_id = auth.uid())
  );
```

- A user cannot claim another user's `id` in a request body or query parameter and gain access: identity always comes from the verified token's `sub` claim (see `docs/04_API.md`). `owner_user_id` is derived server-side, never accepted from the client.
- **Supabase service-role credentials bypass RLS.** The production path (FastAPI → `SUPABASE_DB_URL`) connects with privileged server credentials, so RLS on its own does **not** protect this data. Repository methods must therefore enforce ownership on every read, update and delete in application code, and every acceptance check for M-19/M-20 tests exactly that (two users cannot see or modify each other's recipes).
- Privileged credentials never reach the frontend: no service-role key in `VITE_` variables, in the Vite config, or in any bundle. The browser only ever holds the publishable anon key plus the user's own access token.
- The auth schema (`auth.users`) belongs to Supabase Auth. We do not create, modify or delete rows in it from application code.

## Deferred entities (postponed by the 2026-11-08 planning correction)

These tables exist in the project history (the previous SQLite DDL is preserved in git history) but are **not** part of this release: `person`, `consent`, `hand_profile`, `weighing`, `step`, `quantity`, `clarification`, `tag`, `recipe_tag`, `collection`, `collection_recipe`, `llm_cache`, `api_usage`, `eval_case`, `eval_run`.

They return only if the postponed tasks (personal measurement calibration, weighing repository, person/profile/consent management, recipe scaling, pantry search, collections, advanced evaluation dashboard) are re-opened after the minimum release journey is green. Notes from the previous schema that still apply when they return:

- Weighing tables must stay keyed to a *person/hand* (identity 3 above), never to the account user (identity 1).
- Deletion of a person should cascade to their consents, hand profiles and weighings; recipes keep attribution text but unlink the person.
