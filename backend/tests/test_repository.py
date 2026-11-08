"""Owner-scoped repository behaviour against an in-memory RPC fake (M-19)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from backend.app.db import (
    InvalidPersonLink,
    RecipeCreateRequest,
    RecipeNotFound,
    RecipeRepository,
)
from backend.tests.fakes import FakeRpcClient, FakeStore, repository_for

BENGALI_TRANSCRIPT = "চিতল মাছ ভালো করে ধুয়ে নাও।\nতারপর এক চিমটি নুন আর একটু হলুদ দাও।  "
BENGALI_DRAFT: dict[str, Any] = {
    "recipe": {
        "title": "চিতল মাছের মুইঠা",
        "language": "bn",
        "base_servings": None,
        "steps": [
            {
                "idx": 1,
                "text": "চিতল মাছ ভালো করে ধুয়ে নাও।",
                "orig_start": 0,
                "orig_end": 28,
                "timer_seconds": None,
                "durations": [],
                "quantities": [
                    {
                        "id": "q1",
                        "ingredient": "নুন",
                        "qty": 1.0,
                        "qty_max": None,
                        "unit": "pinch",
                        "raw_phrase": "এক চিমটি নুন",
                        "range": None,
                        "clarification": None,
                    }
                ],
            }
        ],
    },
    "meta": {
        "parser_mode": "rules",
        "llm_provider": None,
        "replayed": False,
        "mock": False,
        "mock_source": None,
    },
}


def _request(**overrides: Any) -> RecipeCreateRequest:
    payload: dict[str, Any] = {
        "title": "Chitol Macher Muitha",
        "original_transcript": BENGALI_TRANSCRIPT,
        "draft": BENGALI_DRAFT,
        "tags": ["fish", "bengali"],
    }
    payload.update(overrides)
    return RecipeCreateRequest(**payload)


def _run(coro):
    return asyncio.run(coro)


def test_create_recipe_starts_at_version_one() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))
    assert created.version == 1
    assert store.recipes[created.id]["owner_user_id"] == "user-a"
    assert [v["version_number"] for v in store.versions[created.id]] == [1]


def test_list_recipes_is_scoped_to_the_authenticated_owner() -> None:
    store = FakeStore()
    repo_a = repository_for(store, "user-a")
    repo_b = repository_for(store, "user-b")
    _run(repo_a.create_recipe(_request(title="A recipe")))
    _run(repo_b.create_recipe(_request(title="B recipe")))

    a = _run(repo_a.list_recipes())
    b = _run(repo_b.list_recipes())
    assert a.total == 1 and [item.title for item in a.items] == ["A recipe"]
    assert b.total == 1 and [item.title for item in b.items] == ["B recipe"]


def test_title_search_and_tag_filter() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    _run(repo.create_recipe(_request(title="Chitol Macher Muitha", tags=["fish"])))
    _run(repo.create_recipe(_request(title="Aloo Posto", tags=["vegetarian"])))

    found = _run(repo.list_recipes(query="chitol"))
    assert found.total == 1
    assert found.items[0].title == "Chitol Macher Muitha"

    tagged = _run(repo.list_recipes(tag="vegetarian"))
    assert tagged.total == 1
    assert tagged.items[0].title == "Aloo Posto"

    missing = _run(repo.list_recipes(query="nothing", tag="fish"))
    assert missing.total == 0 and missing.items == []


def test_list_supports_pagination_and_stable_order() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    for index in range(3):
        _run(repo.create_recipe(_request(title=f"Recipe {index}")))

    first_page = _run(repo.list_recipes(limit=2, offset=0))
    second_page = _run(repo.list_recipes(limit=2, offset=2))
    assert first_page.total == 3
    assert [item.title for item in first_page.items] == ["Recipe 2", "Recipe 1"]
    assert [item.title for item in second_page.items] == ["Recipe 0"]


def test_get_recipe_returns_transcript_and_complete_draft() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))

    detail = _run(repo.get_recipe(created.id))
    assert detail.id == created.id
    assert detail.version == 1
    assert detail.title == "Chitol Macher Muitha"
    assert detail.tags == ["fish", "bengali"]
    assert detail.original_transcript == BENGALI_TRANSCRIPT
    assert detail.draft == BENGALI_DRAFT
    assert detail.created_at is not None


def test_missing_or_unowned_recipe_raises_not_found() -> None:
    store = FakeStore()
    repo_a = repository_for(store, "user-a")
    repo_b = repository_for(store, "user-b")
    created = _run(repo_a.create_recipe(_request()))

    with pytest.raises(RecipeNotFound):
        _run(repo_b.get_recipe(created.id))
    with pytest.raises(RecipeNotFound):
        _run(repo_a.get_recipe("00000000-0000-0000-0000-000000000000"))


def test_update_creates_a_new_version_and_keeps_the_old_one() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))

    updated = _run(
        repo.create_recipe_version(
            created.id,
            title=None,
            tags=None,
            original_transcript="নতুন করে লিখা ট্রান্সক্রিপ্ট",
            draft={"recipe": {"title": "সংস্করণ ২", "steps": []}, "meta": {"parser_mode": "rules"}},
        )
    )
    assert updated.version == 2

    first = _run(repo.get_recipe_version(created.id, 1))
    latest = _run(repo.get_recipe(created.id))
    assert first.version == 1
    assert first.original_transcript == BENGALI_TRANSCRIPT
    assert first.draft == BENGALI_DRAFT
    assert latest.version == 2
    assert latest.original_transcript == "নতুন করে লিখা ট্রান্সক্রিপ্ট"
    assert latest.title == "Chitol Macher Muitha"
    assert latest.tags == ["fish", "bengali"]


def test_update_can_change_title_and_tags() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))
    _run(
        repo.create_recipe_version(
            created.id,
            title="নতুন নাম",
            tags=["updated"],
            original_transcript=BENGALI_TRANSCRIPT,
            draft=BENGALI_DRAFT,
        )
    )
    detail = _run(repo.get_recipe(created.id))
    assert detail.title == "নতুন নাম"
    assert detail.tags == ["updated"]


def test_version_numbers_are_unique_and_sequential() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))
    for index in range(2, 5):
        result = _run(
            repo.create_recipe_version(
                created.id,
                title=None,
                tags=None,
                original_transcript=f"version {index}",
                draft={"version": index},
            )
        )
        assert result.version == index

    numbers = [version["version_number"] for version in store.versions[created.id]]
    assert numbers == [1, 2, 3, 4]
    assert len(set(numbers)) == len(numbers)


def test_concurrent_version_creates_do_not_collide() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))

    async def run_concurrent():
        return await asyncio.gather(
            repo.create_recipe_version(
                created.id,
                title=None,
                tags=None,
                original_transcript="concurrent one",
                draft={"n": 2},
            ),
            repo.create_recipe_version(
                created.id,
                title=None,
                tags=None,
                original_transcript="concurrent two",
                draft={"n": 3},
            ),
        )

    results = _run(run_concurrent())
    assert sorted(result.version for result in results) == [2, 3]
    assert [v["version_number"] for v in store.versions[created.id]] == [1, 2, 3]


def test_delete_cascades_to_versions() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    created = _run(repo.create_recipe(_request()))
    _run(
        repo.create_recipe_version(
            created.id,
            title=None,
            tags=None,
            original_transcript="second",
            draft={},
        )
    )
    _run(repo.delete_recipe(created.id))
    assert created.id not in store.recipes
    assert created.id not in store.versions
    with pytest.raises(RecipeNotFound):
        _run(repo.get_recipe(created.id))


def test_deleting_an_unowned_recipe_raises_not_found() -> None:
    store = FakeStore()
    repo_a = repository_for(store, "user-a")
    repo_b = repository_for(store, "user-b")
    created = _run(repo_a.create_recipe(_request()))
    with pytest.raises(RecipeNotFound):
        _run(repo_b.delete_recipe(created.id))
    assert created.id in store.recipes


def test_person_links_are_rejected_instead_of_silently_dropped() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    with pytest.raises(InvalidPersonLink):
        _run(repo.create_recipe(_request(cook_person_id="person-1")))
    with pytest.raises(InvalidPersonLink):
        _run(repo.create_recipe(_request(narrator_person_id="person-2")))
    assert store.recipes == {}


def test_profile_is_created_once_and_keeps_the_first_display_name() -> None:
    store = FakeStore()
    repo = repository_for(store, "user-a")
    first = _run(repo.get_or_create_profile("Alice"))
    second = _run(repo.get_or_create_profile("Someone Else"))
    assert first.id == "user-a"
    assert first.display_name == "Alice"
    assert second.display_name == "Alice"


def test_repository_uses_only_parameterised_rpcs() -> None:
    store = FakeStore()
    client = FakeRpcClient(store, "user-a")
    repo = RecipeRepository(client, "user-a")
    _run(repo.create_recipe(_request()))
    assert client.calls[0][0] == "create_recipe_with_version"
    assert client.calls[0][1]["p_owner_user_id"] == "user-a"
    assert client.calls[0][1]["p_title"] == "Chitol Macher Muitha"


def test_a_repository_with_a_mismatched_owner_is_rejected_by_the_data_client() -> None:
    store = FakeStore()
    repository = RecipeRepository(FakeRpcClient(store, "user-a"), "user-b")
    with pytest.raises(AssertionError):
        _run(repository.list_recipes())
