-- Thakuma's Recipe - initial Supabase schema (M-18A, M-19, M-20).
--
-- Apply this file in the Supabase Dashboard -> SQL Editor (no CLI or Docker
-- required). It creates the three MVP tables, ownership RLS policies, the
-- new-user profile trigger and the atomic recipe RPCs.
--
-- Ownership model
--   auth.users (Supabase Auth) is the account identity.
--   profiles.id is that same UUID (one profile per account).
--   recipes.owner_user_id references auth.users(id) and is mandatory.
--   recipe_versions are reachable only through a recipe the caller owns.
--
-- The FastAPI backend uses the Supabase Data API with the signed-in user's
-- access token (never a service-role key), so auth.uid() is the real user and
-- these RLS policies are enforced by PostgreSQL itself.

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Maintains updated_at on row updates.';

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.profiles is
  'Application-facing part of an auth.users row. Never stores passwords or tokens.';

create table if not exists public.recipes (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint recipes_title_not_empty check (length(btrim(title)) > 0)
);

comment on table public.recipes is
  'One row per saved recipe. owner_user_id is mandatory and is never accepted from the client.';

create index if not exists recipes_owner_user_id_idx
  on public.recipes (owner_user_id);
create index if not exists recipes_owner_created_idx
  on public.recipes (owner_user_id, created_at desc, id desc);
create index if not exists recipes_tags_gin
  on public.recipes using gin (tags);

create table if not exists public.recipe_versions (
  id uuid primary key default gen_random_uuid(),
  recipe_id uuid not null references public.recipes(id) on delete cascade,
  version_number integer not null,
  original_transcript text not null,
  draft jsonb not null,
  created_at timestamptz not null default now(),
  constraint recipe_versions_version_positive check (version_number > 0),
  constraint recipe_versions_recipe_version_unique unique (recipe_id, version_number)
);

comment on table public.recipe_versions is
  'Immutable history. The newest version_number is the default view; deletion of the recipe cascades here.';

create index if not exists recipe_versions_recipe_id_idx
  on public.recipe_versions (recipe_id, version_number desc);

-- ---------------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------------

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

drop trigger if exists recipes_set_updated_at on public.recipes;
create trigger recipes_set_updated_at
  before update on public.recipes
  for each row execute function public.set_updated_at();

-- Create a private profile for every new Supabase Auth user. This function is
-- SECURITY DEFINER because it runs inside the auth.users trigger and must write
-- to public.profiles; it never exposes the row to anyone else.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    coalesce(
      nullif(new.raw_user_meta_data->>'full_name', ''),
      nullif(new.raw_user_meta_data->>'name', ''),
      nullif(split_part(coalesce(new.email, ''), '@', 1), '')
    )
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

comment on function public.handle_new_user() is
  'Initialises a profile for each new auth user; no password data is copied.';

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.recipes enable row level security;
alter table public.recipe_versions enable row level security;

-- Profiles: a user can see, create and update only their own row. There is no
-- delete policy: deletion of the account cascades from auth.users.
drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own on public.profiles
  for select to authenticated
  using (auth.uid() = id);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own on public.profiles
  for insert to authenticated
  with check (auth.uid() = id);

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Recipes: the owner is the authenticated uid on every operation. WITH CHECK
-- prevents a user from reassigning owner_user_id to someone else.
drop policy if exists recipes_select_own on public.recipes;
create policy recipes_select_own on public.recipes
  for select to authenticated
  using (auth.uid() = owner_user_id);

drop policy if exists recipes_insert_own on public.recipes;
create policy recipes_insert_own on public.recipes
  for insert to authenticated
  with check (auth.uid() = owner_user_id);

drop policy if exists recipes_update_own on public.recipes;
create policy recipes_update_own on public.recipes
  for update to authenticated
  using (auth.uid() = owner_user_id)
  with check (auth.uid() = owner_user_id);

drop policy if exists recipes_delete_own on public.recipes;
create policy recipes_delete_own on public.recipes
  for delete to authenticated
  using (auth.uid() = owner_user_id);

-- Versions: reachable only when the related recipe belongs to the caller.
-- Only SELECT and INSERT policies exist, so previous versions are immutable and
-- cannot be updated or deleted directly. Recipe deletion cascades to versions.
drop policy if exists recipe_versions_select_owned on public.recipe_versions;
create policy recipe_versions_select_owned on public.recipe_versions
  for select to authenticated
  using (
    exists (
      select 1 from public.recipes r
      where r.id = recipe_id and r.owner_user_id = auth.uid()
    )
  );

drop policy if exists recipe_versions_insert_owned on public.recipe_versions;
create policy recipe_versions_insert_owned on public.recipe_versions
  for insert to authenticated
  with check (
    exists (
      select 1 from public.recipes r
      where r.id = recipe_id and r.owner_user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Privileges: authenticated only. Anonymous users get no recipe data access.
-- ---------------------------------------------------------------------------

revoke all on public.profiles from anon;
revoke all on public.recipes from anon;
revoke all on public.recipe_versions from anon;

grant usage on schema public to authenticated;
grant select, insert, update on public.profiles to authenticated;
grant select, insert, update, delete on public.recipes to authenticated;
grant select, insert on public.recipe_versions to authenticated;

-- ---------------------------------------------------------------------------
-- RPCs used by the FastAPI repository
--
-- All RPCs are SECURITY INVOKER, so RLS still applies. Each one also checks the
-- caller-supplied p_owner_user_id against auth.uid(); the backend always passes
-- the verified token subject, and a mismatch is rejected instead of ignored.
-- ---------------------------------------------------------------------------

create or replace function public.assert_owner(p_owner_user_id uuid)
returns void
language plpgsql
set search_path = public
as $$
begin
  if auth.uid() is null then
    raise exception 'not authenticated' using errcode = '42501';
  end if;
  if p_owner_user_id is distinct from auth.uid() then
    raise exception 'owner mismatch' using errcode = '42501';
  end if;
end;
$$;

create or replace function public.create_recipe_with_version(
  p_owner_user_id uuid,
  p_title text,
  p_original_transcript text,
  p_draft jsonb,
  p_tags text[] default '{}'
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_recipe_id uuid;
begin
  perform public.assert_owner(p_owner_user_id);

  if p_title is null or length(btrim(p_title)) = 0 then
    raise exception 'title must not be empty' using errcode = '22023';
  end if;
  if p_original_transcript is null then
    raise exception 'original_transcript is required' using errcode = '22023';
  end if;
  if p_draft is null then
    raise exception 'draft is required' using errcode = '22023';
  end if;

  insert into public.recipes (owner_user_id, title, tags)
  values (p_owner_user_id, btrim(p_title), coalesce(p_tags, '{}'))
  returning id into v_recipe_id;

  insert into public.recipe_versions
    (recipe_id, version_number, original_transcript, draft)
  values
    (v_recipe_id, 1, p_original_transcript, p_draft);

  return jsonb_build_object('id', v_recipe_id, 'version', 1);
end;
$$;

create or replace function public.add_recipe_version(
  p_owner_user_id uuid,
  p_recipe_id uuid,
  p_title text,
  p_tags text[],
  p_original_transcript text,
  p_draft jsonb
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_next integer;
  v_recipe public.recipes%rowtype;
begin
  perform public.assert_owner(p_owner_user_id);

  -- Locking the recipe row serialises concurrent version creation for this
  -- recipe, so MAX(version_number) + 1 cannot race. The unique constraint is a
  -- second line of defence.
  select * into v_recipe
  from public.recipes
  where id = p_recipe_id and owner_user_id = p_owner_user_id
  for update;

  if not found then
    return null;
  end if;

  if p_original_transcript is null then
    raise exception 'original_transcript is required' using errcode = '22023';
  end if;
  if p_draft is null then
    raise exception 'draft is required' using errcode = '22023';
  end if;

  select coalesce(max(version_number), 0) + 1
  into v_next
  from public.recipe_versions
  where recipe_id = p_recipe_id;

  insert into public.recipe_versions
    (recipe_id, version_number, original_transcript, draft)
  values
    (p_recipe_id, v_next, p_original_transcript, p_draft);

  update public.recipes
  set title = coalesce(nullif(btrim(p_title), ''), title),
      tags = coalesce(p_tags, tags),
      updated_at = now()
  where id = p_recipe_id;

  return jsonb_build_object('id', p_recipe_id, 'version', v_next);
end;
$$;

create or replace function public.get_recipe_detail(
  p_owner_user_id uuid,
  p_recipe_id uuid
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_recipe public.recipes%rowtype;
  v_version public.recipe_versions%rowtype;
begin
  perform public.assert_owner(p_owner_user_id);

  select * into v_recipe
  from public.recipes
  where id = p_recipe_id and owner_user_id = p_owner_user_id;

  if not found then
    return null;
  end if;

  select * into v_version
  from public.recipe_versions
  where recipe_id = p_recipe_id
  order by version_number desc
  limit 1;

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'id', v_recipe.id,
    'title', v_recipe.title,
    'version', v_version.version_number,
    'original_transcript', v_version.original_transcript,
    'draft', v_version.draft,
    'tags', v_recipe.tags,
    'created_at', v_recipe.created_at,
    'updated_at', v_recipe.updated_at
  );
end;
$$;

create or replace function public.get_recipe_version(
  p_owner_user_id uuid,
  p_recipe_id uuid,
  p_version_number integer
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_recipe public.recipes%rowtype;
  v_version public.recipe_versions%rowtype;
begin
  perform public.assert_owner(p_owner_user_id);

  select * into v_recipe
  from public.recipes
  where id = p_recipe_id and owner_user_id = p_owner_user_id;

  if not found then
    return null;
  end if;

  select * into v_version
  from public.recipe_versions
  where recipe_id = p_recipe_id and version_number = p_version_number;

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'id', v_recipe.id,
    'title', v_recipe.title,
    'version', v_version.version_number,
    'original_transcript', v_version.original_transcript,
    'draft', v_version.draft,
    'tags', v_recipe.tags,
    'created_at', v_recipe.created_at,
    'updated_at', v_recipe.updated_at
  );
end;
$$;

create or replace function public.list_recipes(
  p_owner_user_id uuid,
  p_query text default null,
  p_tag text default null,
  p_limit integer default 50,
  p_offset integer default 0
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_items jsonb;
  v_total bigint;
begin
  perform public.assert_owner(p_owner_user_id);

  select count(*) into v_total
  from public.recipes r
  where r.owner_user_id = p_owner_user_id
    and (p_query is null or r.title ilike '%' || p_query || '%')
    and (p_tag is null or p_tag = any(r.tags));

  select coalesce(
    jsonb_agg(item order by sort_created desc, sort_id desc),
    '[]'::jsonb
  )
  into v_items
  from (
    select
      jsonb_build_object(
        'id', r.id,
        'title', r.title,
        'tags', r.tags,
        'version', coalesce(
          (select max(v.version_number)
             from public.recipe_versions v
            where v.recipe_id = r.id),
          0
        ),
        'created_at', r.created_at,
        'updated_at', r.updated_at
      ) as item,
      r.created_at as sort_created,
      r.id as sort_id
    from public.recipes r
    where r.owner_user_id = p_owner_user_id
      and (p_query is null or r.title ilike '%' || p_query || '%')
      and (p_tag is null or p_tag = any(r.tags))
    order by r.created_at desc, r.id desc
    limit greatest(1, least(coalesce(p_limit, 50), 100))
    offset greatest(0, coalesce(p_offset, 0))
  ) page;

  return jsonb_build_object('items', v_items, 'total', v_total);
end;
$$;

create or replace function public.delete_recipe(
  p_owner_user_id uuid,
  p_recipe_id uuid
)
returns boolean
language plpgsql
set search_path = public
as $$
declare
  v_deleted integer;
begin
  perform public.assert_owner(p_owner_user_id);

  delete from public.recipes
  where id = p_recipe_id and owner_user_id = p_owner_user_id;

  get diagnostics v_deleted = row_count;
  return v_deleted > 0;
end;
$$;

create or replace function public.get_or_create_profile(
  p_owner_user_id uuid,
  p_display_name text default null
)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  v_profile public.profiles%rowtype;
begin
  perform public.assert_owner(p_owner_user_id);

  insert into public.profiles (id, display_name)
  values (
    p_owner_user_id,
    nullif(btrim(coalesce(p_display_name, '')), '')
  )
  on conflict (id) do nothing;

  select * into v_profile from public.profiles where id = p_owner_user_id;

  return jsonb_build_object(
    'id', v_profile.id,
    'display_name', v_profile.display_name,
    'created_at', v_profile.created_at
  );
end;
$$;

-- Function privileges: authenticated only.
revoke all on function public.assert_owner(uuid) from public, anon;
revoke all on function public.create_recipe_with_version(uuid, text, text, jsonb, text[])
  from public, anon;
revoke all on function public.add_recipe_version(uuid, uuid, text, text[], text, jsonb)
  from public, anon;
revoke all on function public.get_recipe_detail(uuid, uuid) from public, anon;
revoke all on function public.get_recipe_version(uuid, uuid, integer) from public, anon;
revoke all on function public.list_recipes(uuid, text, text, integer, integer) from public, anon;
revoke all on function public.delete_recipe(uuid, uuid) from public, anon;
revoke all on function public.get_or_create_profile(uuid, text) from public, anon;

grant execute on function public.assert_owner(uuid) to authenticated;
grant execute on function public.create_recipe_with_version(uuid, text, text, jsonb, text[])
  to authenticated;
grant execute on function public.add_recipe_version(uuid, uuid, text, text[], text, jsonb)
  to authenticated;
grant execute on function public.get_recipe_detail(uuid, uuid) to authenticated;
grant execute on function public.get_recipe_version(uuid, uuid, integer) to authenticated;
grant execute on function public.list_recipes(uuid, text, text, integer, integer)
  to authenticated;
grant execute on function public.delete_recipe(uuid, uuid) to authenticated;
grant execute on function public.get_or_create_profile(uuid, text) to authenticated;