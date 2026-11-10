"""Documented personal interval behaviour for account hand calibration."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.auth import AuthenticatedUser
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.routers.hands import _with_ranges, client_for, interval
from backend.tests.fakes import FakeTokenVerifier


def test_one_weighing_gets_documented_fifteen_percent_interval() -> None:
    assert interval([40], "g") == {"lo": 34.0, "hi": 46.0, "unit": "g", "basis": "yours"}


def test_multiple_weighings_use_min_and_max_with_five_percent_padding() -> None:
    assert interval([40, 50, 45], "g") == {"lo": 38.0, "hi": 52.5, "unit": "g", "basis": "yours"}


def test_ranges_are_separated_by_unit_ingredient_and_amount_unit() -> None:
    result = _with_ranges({"profile_id": "p", "weighings": [
        {"id": "1", "unit": "muthi", "ingredient": "Rice", "amount": 40, "amount_unit": "g"},
        {"id": "2", "unit": "muthi", "ingredient": "rice", "amount": 50, "amount_unit": "g"},
        {"id": "3", "unit": "muthi", "ingredient": "Rice", "amount": 60, "amount_unit": "ml"},
        {"id": "4", "unit": "cup", "ingredient": "Rice", "amount": 60, "amount_unit": "g"},
    ]})
    assert len(result["ranges"]) == 3
    rice = next(item for item in result["ranges"] if item["unit"] == "muthi" and item["amount_unit"] == "g")
    assert rice["range"] == {"lo": 38.0, "hi": 52.5, "unit": "g", "basis": "yours"}


def test_api_persists_and_deletes_only_authenticated_users_weighings() -> None:
    rows = []
    profile_id = str(uuid4())

    class Rpc:
        async def rpc(self, name, params):
            if name == "get_hand_calibration":
                return {"profile_id": profile_id, "weighings": list(rows)}
            if name == "add_hand_weighing":
                row = {"id": str(uuid4()), "unit": params["p_unit"], "ingredient": params["p_ingredient"], "amount": params["p_amount"], "amount_unit": params["p_amount_unit"], "created_at": datetime.now(timezone.utc).isoformat()}
                rows.append(row)
                return row
            if name == "delete_hand_weighing":
                before = len(rows)
                rows[:] = [row for row in rows if row["id"] != params["p_weighing_id"]]
                return len(rows) < before
            raise AssertionError(name)

        async def aclose(self):
            pass

    async def fake_client():
        yield Rpc()

    settings = Settings(supabase_url="https://project.supabase.co", supabase_publishable_key="key", supabase_anon_key="", gnani_api_key="", gnani_mock=True, llm_chain="rules", gemini_api_key="", gemini_model="")
    app = create_app(settings, token_verifier=FakeTokenVerifier({"token": AuthenticatedUser(id="user-a")}))
    app.dependency_overrides[client_for] = fake_client
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer token"}
        saved = client.post("/api/me/hand-calibration/weighings", headers=headers, json={"unit": "muthi", "ingredient": "rice", "amount": 40, "amount_unit": "g"})
        assert saved.status_code == 201
        assert saved.json()["ranges"][0]["range"] == {"lo": 34.0, "hi": 46.0, "unit": "g", "basis": "yours"}
        assert client.get("/api/me/hand-calibration", headers=headers).json()["weighings"][0]["ingredient"] == "rice"
        deleted = client.delete(f"/api/me/hand-calibration/weighings/{saved.json()['weighings'][0]['id']}", headers=headers)
        assert deleted.status_code == 200 and deleted.json()["weighings"] == []
        assert client.post("/api/me/hand-calibration/weighings", headers=headers, json={"unit": "muthi", "ingredient": "rice", "amount": -1, "amount_unit": "g"}).status_code == 422
