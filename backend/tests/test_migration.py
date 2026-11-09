"""Static checks on the initial Supabase migration.

These assertions verify the SQL text is present. They do **not** prove that
PostgreSQL/RLS behaves correctly; the manual two-user smoke test in the README
is the only evidence for that.
"""

from __future__ import annotations

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "0001_initial_schema.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists() -> None:
    assert MIGRATION.is_file()


def test_only_the_three_mvp_tables_are_created() -> None:
    sql = _sql().lower()
    created = re.findall(r"create table if not exists ([a-z_.]+)", sql)
    assert created == ["public.profiles", "public.recipes", "public.recipe_versions"]


def test_ownership_columns_and_cascades_are_present() -> None:
    sql = _sql()
    assert "owner_user_id uuid not null references auth.users(id) on delete cascade" in sql
    assert "id uuid primary key references auth.users(id) on delete cascade" in sql
    assert "recipe_id uuid not null references public.recipes(id) on delete cascade" in sql


def test_versions_are_immutable_by_number() -> None:
    sql = _sql()
    assert "unique (recipe_id, version_number)" in sql
    assert "version_number integer not null" in sql
    assert "recipe_versions_update" not in sql
    assert "recipe_versions_delete" not in sql


def test_exact_transcript_and_full_jsonb_draft_are_required() -> None:
    sql = _sql()
    assert "original_transcript text not null" in sql
    assert "draft jsonb not null" in sql


def test_rls_is_enabled_on_every_user_table() -> None:
    sql = _sql()
    assert sql.count("enable row level security") == 3
    assert "alter table public.profiles enable row level security" in sql
    assert "alter table public.recipes enable row level security" in sql
    assert "alter table public.recipe_versions enable row level security" in sql


def test_recipe_policies_use_owner_checks_with_using_and_with_check() -> None:
    sql = _sql()
    for name in (
        "recipes_select_own",
        "recipes_insert_own",
        "recipes_update_own",
        "recipes_delete_own",
    ):
        assert name in sql
    assert "using (auth.uid() = owner_user_id)" in sql
    assert "with check (auth.uid() = owner_user_id)" in sql


def test_version_policies_only_allow_read_and_insert() -> None:
    sql = _sql()
    assert "recipe_versions_select_owned" in sql
    assert "recipe_versions_insert_owned" in sql
    assert "recipe_versions_update" not in sql
    assert "recipe_versions_delete" not in sql
    assert "exists (" in sql


def test_anonymous_role_gets_no_table_grants() -> None:
    sql = _sql().lower()
    assert not re.search(r"grant\b[^;]*\bto\s+anon\b", sql)
    assert "grant select, insert, update, delete on public.recipes to authenticated" in sql


def test_no_service_role_key_or_bypass_is_introduced() -> None:
    sql = _sql().lower()
    code = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert "service_role" not in code
    # Only the sign-up trigger escalates privileges.
    assert code.count("security definer") == 1


def test_atomic_version_rpc_locks_the_recipe_row() -> None:
    sql = _sql()
    assert "create or replace function public.add_recipe_version" in sql
    assert "for update" in sql
    assert "coalesce(max(version_number), 0) + 1" in sql


def test_all_repository_rpcs_exist() -> None:
    sql = _sql()
    for function in (
        "create_recipe_with_version",
        "add_recipe_version",
        "get_recipe_detail",
        "get_recipe_version",
        "list_recipes",
        "delete_recipe",
        "get_or_create_profile",
    ):
        assert f"create or replace function public.{function}" in sql


def test_new_auth_users_get_a_profile_via_a_trigger() -> None:
    sql = _sql()
    assert "create trigger on_auth_user_created" in sql
    assert "after insert on auth.users" in sql
    assert "insert into public.profiles" in sql


def test_rpc_owner_is_checked_against_the_verified_uid() -> None:
    sql = _sql()
    assert "p_owner_user_id is distinct from auth.uid()" in sql
    assert "perform public.assert_owner(p_owner_user_id)" in sql
