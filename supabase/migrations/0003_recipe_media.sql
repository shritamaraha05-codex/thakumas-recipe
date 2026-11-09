-- Thakuma's Recipe — 0003: recipe media metadata (ImageKit)
--
-- Apply this AFTER 0001_initial_schema.sql (and preferably after the
-- separate 0002_auth_trigger_hardening.sql migration).
--
-- ImageKit stores the actual private image/audio files. This table stores
-- their metadata and associates each file with a recipe and, optionally,
-- the recipe version it belongs to. No ImageKit secret is stored here.
--
-- Access model:
--   * A signed-in user can SELECT/INSERT/DELETE media for recipes they own.
--   * There is intentionally no UPDATE policy/grant. Replace media by
--     uploading a new file/row, then deleting the old row/file.
--   * The backend must still verify recipe ownership and the expected
--     /users/{auth-user-id}/ path before generating signed URLs or deleting
--     files in ImageKit. RLS protects these metadata rows; it does not
--     independently protect objects in ImageKit.

begin;

-- A composite FK below ensures a media row's version belongs to its recipe.
-- `id` is already a primary key, but PostgreSQL requires the exact referenced
-- column set to have a unique constraint for the composite FK.
alter table public.recipe_versions
  add constraint recipe_versions_recipe_id_id_unique
  unique (recipe_id, id);

create table public.recipe_media (
  id uuid primary key default gen_random_uuid(),
  recipe_id uuid not null,
  recipe_version_id uuid,
  media_type text not null,
  imagekit_file_id text not null,
  imagekit_url text not null,
  imagekit_file_path text not null,
  mime_type text not null,
  size_bytes bigint not null,
  original_filename text,
  created_at timestamptz not null default now(),

  constraint recipe_media_type_valid
    check (media_type in ('audio', 'image')),
  constraint recipe_media_size_nonnegative
    check (size_bytes >= 0),
  constraint recipe_media_file_id_unique
    unique (imagekit_file_id),
  constraint recipe_media_recipe_fk
    foreign key (recipe_id)
    references public.recipes (id)
    on delete cascade,
  constraint recipe_media_recipe_version_fk
    foreign key (recipe_id, recipe_version_id)
    references public.recipe_versions (recipe_id, id)
    on delete cascade
);

comment on table public.recipe_media is
  'Private ImageKit image/audio metadata linked to an owned recipe and optionally to one recipe version.';
comment on column public.recipe_media.imagekit_url is
  'Canonical ImageKit file URL, not an expiring signed URL.';
comment on column public.recipe_media.imagekit_file_path is
  'Canonical ImageKit file path used by the backend to generate short-lived signed delivery URLs.';
comment on column public.recipe_media.imagekit_file_id is
  'ImageKit fileId used by the backend for file management and deletion.';

create index recipe_media_recipe_created_idx
  on public.recipe_media (recipe_id, created_at desc, id desc);

create index recipe_media_recipe_version_idx
  on public.recipe_media (recipe_id, recipe_version_id);

-- Enable row-level security. Media is visible only through an owned recipe.
alter table public.recipe_media enable row level security;

create policy recipe_media_select_owned
  on public.recipe_media
  for select
  to authenticated
  using (
    exists (
      select 1
      from public.recipes r
      where r.id = recipe_media.recipe_id
        and r.owner_user_id = auth.uid()
    )
  );

create policy recipe_media_insert_owned
  on public.recipe_media
  for insert
  to authenticated
  with check (
    exists (
      select 1
      from public.recipes r
      where r.id = recipe_media.recipe_id
        and r.owner_user_id = auth.uid()
    )
  );

create policy recipe_media_delete_owned
  on public.recipe_media
  for delete
  to authenticated
  using (
    exists (
      select 1
      from public.recipes r
      where r.id = recipe_media.recipe_id
        and r.owner_user_id = auth.uid()
    )
  );

-- Do not grant anonymous access. Authenticated users can read, create and
-- delete their own media rows. UPDATE is intentionally omitted.
revoke all on table public.recipe_media from public, anon, authenticated;
grant select, insert, delete on table public.recipe_media to authenticated;

commit;
