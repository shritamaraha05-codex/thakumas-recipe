"""``POST /api/parse`` contract: the real M-08 rules parser over HTTP.

These tests exercise the public API only. They never call a network or an LLM;
settings come from the credential-free ``client`` fixture (``LLM_CHAIN=rules``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.models import ParseResult


def _parse(client: TestClient, text: str, mode: str | None = None) -> dict:
    payload: dict = {"text": text}
    if mode is not None:
        payload["mode"] = mode
    response = client.post("/api/parse", json=payload)
    assert response.status_code == 200
    return response.json()


# --------------------------------------------------------------------------- #
# The endpoint is no longer a static fixture                                  #
# --------------------------------------------------------------------------- #


def test_response_is_real_parser_output_not_the_fixture(client: TestClient) -> None:
    body = _parse(client, "এক মুঠো চাল")
    assert body["meta"]["mock"] is False
    assert body["meta"]["mock_source"] is None
    assert body["meta"]["parser_mode"] == "rules"
    assert body["recipe"]["title"] == "Untitled recipe"


def test_results_change_with_submitted_text(client: TestClient) -> None:
    rice = _parse(client, "এক মুঠো চাল")
    salt = _parse(client, "দুই চিমটি নুন")
    rice_ingredients = [q["ingredient"] for q in rice["recipe"]["steps"][0]["quantities"]]
    salt_ingredients = [q["ingredient"] for q in salt["recipe"]["steps"][0]["quantities"]]
    assert rice_ingredients == ["rice"]
    assert salt_ingredients == ["salt"]
    assert rice != salt


def test_different_text_never_returns_identical_body(client: TestClient) -> None:
    first = _parse(client, "ek muthi chal")
    second = _parse(client, "dui chimti nun")
    assert first["recipe"]["steps"] != second["recipe"]["steps"]


# --------------------------------------------------------------------------- #
# Bengali and Roman Bengali narration                                         #
# --------------------------------------------------------------------------- #


def test_bengali_narration_is_parsed(client: TestClient) -> None:
    body = _parse(client, "এক মুঠো চাল")
    quantity = body["recipe"]["steps"][0]["quantities"][0]
    assert quantity["ingredient"] == "rice"
    assert quantity["ingredient_class"] == "grain"
    assert quantity["qty"] == 1
    assert quantity["unit"] == "muthi"
    assert quantity["raw_unit"] == "মুঠো"
    assert quantity["raw_phrase"] == "এক মুঠো চাল"
    assert quantity["kind"] == "exact"
    assert quantity["source"] == "rules"


def test_roman_bengali_narration_is_parsed(client: TestClient) -> None:
    body = _parse(client, "ek muthi chal")
    quantity = body["recipe"]["steps"][0]["quantities"][0]
    assert quantity["ingredient"] == "rice"
    assert quantity["qty"] == 1
    assert quantity["unit"] == "muthi"
    assert quantity["raw_phrase"] == "ek muthi chal"


# --------------------------------------------------------------------------- #
# Modes                                                                        #
# --------------------------------------------------------------------------- #


def test_rules_mode_uses_deterministic_parser(client: TestClient) -> None:
    body = _parse(client, "ek muthi chal", mode="rules")
    assert body["meta"]["parser_mode"] == "rules"
    assert body["meta"]["llm_provider"] is None
    assert body["meta"]["mock"] is False


def test_auto_mode_follows_configured_rules_parser(client: TestClient) -> None:
    body = _parse(client, "ek muthi chal", mode="auto")
    assert body["meta"]["parser_mode"] == "rules"
    assert body["meta"]["llm_provider"] is None


def test_llm_mode_returns_clear_unavailable_error(client: TestClient) -> None:
    # M-10: mode="llm" selects Gemini. With no API key configured it must report
    # a controlled provider-unavailable error, not fall back to the rules parser.
    response = client.post("/api/parse", json={"text": "ek muthi chal", "mode": "llm"})
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "LLM_UNAVAILABLE"
    assert error["message"]
    assert error["hint"]
    # It must not silently fall back to the rules parser.
    assert "recipe" not in response.json()


# --------------------------------------------------------------------------- #
# Clarifications, vague and taste quantities                                  #
# --------------------------------------------------------------------------- #


def test_plain_chamoch_produces_a_clarification(client: TestClient) -> None:
    quantity = _parse(client, "এক চামচ তেল")["recipe"]["steps"][0]["quantities"][0]
    assert quantity["unit"] == "spoon"
    assert quantity["qty"] == 1
    clarification = quantity["clarification"]
    assert clarification["id"] == "unit_spoon_1"
    assert clarification["kind"] == "unit_spoon"
    assert clarification["options"] == ["tsp", "tbsp"]
    assert clarification["question"]


def test_cup_produces_a_clarification(client: TestClient) -> None:
    quantity = _parse(client, "আধা কাপ দুধ")["recipe"]["steps"][0]["quantities"][0]
    assert quantity["unit"] == "cup"
    assert quantity["qty"] == 0.5
    clarification = quantity["clarification"]
    assert clarification["id"] == "unit_cup_1"
    assert clarification["kind"] == "unit_cup"
    assert clarification["options"] == ["tea cup", "measuring cup", "my cup"]


def test_resolved_spoon_compound_has_no_clarification(client: TestClient) -> None:
    quantity = _parse(client, "এক ছোট চামচ নুন")["recipe"]["steps"][0]["quantities"][0]
    assert quantity["unit"] == "tsp"
    assert quantity["clarification"] is None


def test_vague_quantity_stays_nonnumeric(client: TestClient) -> None:
    quantity = _parse(client, "একটু লবণ")["recipe"]["steps"][0]["quantities"][0]
    assert quantity["qty"] is None
    assert quantity["qty_max"] is None
    assert quantity["kind"] == "vague"
    assert quantity["raw_phrase"] == "একটু লবণ"


def test_taste_quantity_keeps_to_taste(client: TestClient) -> None:
    quantity = _parse(client, "স্বাদমতো নুন")["recipe"]["steps"][0]["quantities"][0]
    assert quantity["to_taste"] is True
    assert quantity["qty"] is None
    assert quantity["kind"] == "taste"


# --------------------------------------------------------------------------- #
# Durations stay separate                                                     #
# --------------------------------------------------------------------------- #


def test_duration_stays_out_of_ingredient_quantities(client: TestClient) -> None:
    step = _parse(client, "দশ মিনিট ঢিমে আঁচে রান্না করো")["recipe"]["steps"][0]
    assert step["quantities"] == []
    assert step["timer_seconds"] is None  # never inferred
    assert len(step["durations"]) == 1
    duration = step["durations"][0]
    assert (duration["value"], duration["unit"], duration["kind"]) == (10, "minute", "exact")
    assert duration["raw_phrase"] == "দশ মিনিট"


# --------------------------------------------------------------------------- #
# Source preservation                                                         #
# --------------------------------------------------------------------------- #


def test_original_wording_and_spans_are_preserved(client: TestClient) -> None:
    text = "এক মুঠো চাল, আধা কাপ দুধ।"
    body = _parse(client, text)
    for step in body["recipe"]["steps"]:
        assert text[step["orig_start"] : step["orig_end"]] == step["text"]
        for quantity in step["quantities"]:
            raw = quantity["raw_phrase"]
            assert raw in text
            assert text[quantity["orig_start"] : quantity["orig_end"]] == raw
            assert quantity["ingredient_class"] is not None


def test_unknown_ingredients_are_not_fabricated(client: TestClient) -> None:
    body = _parse(client, "ঝোল কড়াইতে ঢালো")
    quantities = [q for step in body["recipe"]["steps"] for q in step["quantities"]]
    assert quantities == []


# --------------------------------------------------------------------------- #
# Request compatibility, determinism and validation                           #
# --------------------------------------------------------------------------- #


def test_optional_fields_are_accepted_and_not_used(client: TestClient) -> None:
    baseline = _parse(client, "এক মুঠো চাল")
    with_fields = _parse(client, "এক মুঠো চাল")
    # hand_profile_id / servings must not change the quantity (no calibration,
    # no scaling yet); they are accepted for contract compatibility.
    response = client.post(
        "/api/parse",
        json={"text": "এক মুঠো চাল", "hand_profile_id": 7, "servings": 4},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recipe"]["base_servings"] is None
    assert body["recipe"]["steps"] == baseline["recipe"]["steps"]
    assert with_fields["recipe"]["steps"] == baseline["recipe"]["steps"]


def test_repeated_requests_are_deterministic(client: TestClient) -> None:
    text = "এক মুঠো চাল আর আধা কাপ দুধ। তারপর দশ মিনিট রান্না করো।"
    assert _parse(client, text) == _parse(client, text)


def test_response_validates_against_the_model(client: TestClient) -> None:
    body = _parse(client, "ek muthi chal ar ek chimti nun")
    ParseResult.model_validate(body)


def test_ingredient_class_is_populated(client: TestClient) -> None:
    body = _parse(client, "এক মুঠো চাল আর এক চামচ তেল")
    classes = {
        q["ingredient"]: q["ingredient_class"]
        for step in body["recipe"]["steps"]
        for q in step["quantities"]
    }
    assert classes["rice"] == "grain"
    assert classes["oil"] == "liquid"
