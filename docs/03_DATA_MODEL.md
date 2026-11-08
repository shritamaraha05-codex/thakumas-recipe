# 03 Data model (Supabase PostgreSQL)

Audio is **not** stored by default. `consent` gates anything beyond transcript storage.

## Three identities that must never be merged

1. **Account user** — the owner of the Supabase Auth account (`auth.users`). This identity owns saved recipes. Created only by Supabase Auth at sign-up; we never store passwords ourselves.
2. **Cook / narrator person** — the family member who prepared or narrated the recipe. A grandmother can narrate a recipe and never have a Thakuma's Recipe login.
3. **Measurement profile** — the person (hand) whose traditional measures are being calibrated by weighing. Postponed with the calibration tasks (see `docs/12_TASKS.md` §1).

An account user can save a recipe narrated by another family member; a narrator needs no account. These three concepts stay in separate structures and are never collapsed into one "user" entity.

## Minimum schema for this release

Cloud-hosted PostgreSQL (via Supabase). `supabase/migrations/0001_initial_schema.sql` creates exactly these three tables, their RLS policies, the sign-up profile trigger and the atomic recipe RPCs. The complete parsed recipe is stored as one JSONB document — there are **no** relational ingredient/step tables in this MVP.

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

The migration (`supabase/migrations/0001_initial_schema.sql`) enables RLS on all three tables and grants table/function privileges to `authenticated` only. Anonymous users get no recipe data access.

```sql
alter table public.profiles enable row level security;
alter table public.recipes enable row level security;
alter table public.recipe_versions enable row level security;

-- Profiles: self only.
create policy profiles_select_own on public.profiles
  for select to authenticated using (auth.uid() = id);
create policy profiles_insert_own on public.profiles
  for insert to authenticated with check (auth.uid() = id);
create policy profiles_update_own on public.profiles
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- Recipes: owner on every operation; WITH CHECK prevents reassignment.
create policy recipes_select_own on public.recipes
  for select to authenticated using (auth.uid() = owner_user_id);
create policy recipes_insert_own on public.recipes
  for insert to authenticated with check (auth.uid() = owner_user_id);
create policy recipes_update_own on public.recipes
  for update to authenticated using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);
create policy recipes_delete_own on public.recipes
  for delete to authenticated using (auth.uid() = owner_user_id);

-- Versions: only through an owned recipe. No UPDATE/DELETE policy exists,
-- so old versions are immutable; deleting the recipe cascades.
create policy recipe_versions_select_owned on public.recipe_versions
  for select to authenticated using (
    exists (select 1 from public.recipes r
            where r.id = recipe_id and r.owner_user_id = auth.uid()));
create policy recipe_versions_insert_owned on public.recipe_versions
  for insert to authenticated with check (
    exists (select 1 from public.recipes r
            where r.id = recipe_id and r.owner_user_id = auth.uid()));
```

How the backend participates:

- A user cannot claim another user's identity in a request body or query parameter: FastAPI verifies the token and derives `owner_user_id` from its `sub` claim (see `docs/04_API.md`). Request models reject an `owner_user_id` field (`extra="forbid"`).
- FastAPI builds a **per-request** Data API client carrying the publishable key and the user's access token. There is no shared mutable client and no `SUPABASE_DB_URL`/service-role connection, so PostgreSQL RLS evaluates the real authenticated user on every statement.
- The SQL RPCs (`create_recipe_with_version`, `add_recipe_version`, `get_recipe_detail`, `get_recipe_version`, `list_recipes`, `delete_recipe`, `get_or_create_profile`) are `SECURITY INVOKER`, use parameterised arguments, and call `assert_owner(p_owner_user_id)`, which requires `p_owner_user_id = auth.uid()`. User input is never interpolated into raw SQL.
- `add_recipe_version` locks the recipe row (`FOR UPDATE`) before computing `MAX(version_number) + 1`; `unique(recipe_id, version_number)` is a second line of defence against concurrent writes.
- Ordinary recipe CRUD never uses the service-role key.
- The auth schema (`auth.users`) belongs to Supabase Auth. Application code does not create, modify or delete rows there; the sign-up trigger only inserts into `public.profiles`.

**Do not claim RLS works because `ENABLE ROW LEVEL SECURITY` appears in the SQL.** The automated tests use fakes and static SQL checks. Apply the migration in the Supabase SQL Editor and run the README's manual two-user verification (A saves; B cannot list/open/update/delete; old versions survive an edit; deleting A's recipe removes its versions). That live result is the evidence.

## Deferred entities (postponed by the 2026-11-08 planning correction)

These tables exist in the project history (the previous SQLite DDL is preserved in git history) but are **not** part of this release: `person`, `consent`, `hand_profile`, `weighing`, `step`, `quantity`, `clarification`, `tag`, `recipe_tag`, `collection`, `collection_recipe`, `llm_cache`, `api_usage`, `eval_case`, `eval_run`.

They return only if the postponed tasks (personal measurement calibration, weighing repository, person/profile/consent management, recipe scaling, pantry search, collections, advanced evaluation dashboard) are re-opened after the minimum release journey is green. Notes from the previous schema that still apply when they return:

- Weighing tables must stay keyed to a *person/hand* (identity 3 above), never to the account user (identity 1).
- Deletion of a person should cascade to their consents, hand profiles and weighings; recipes keep attribution text but unlink the person.
