"""Authenticated hand calibration storage and personal intervals."""
from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..auth import AuthContext, get_auth_context
from ..config import Settings
from ..db import DatabaseFailure, DatabaseUnavailable, build_user_client
from ..dependencies import get_settings
from ..errors import ApiError
from ..models import ErrorCode

router = APIRouter(tags=["hand calibration"])
Unit = Literal["muthi", "chimti", "cup", "spoon", "tsp", "tbsp", "bati", "glass", "poa", "chhatak", "ser"]


class WeighingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Unit
    ingredient: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0, le=100000)
    amount_unit: Literal["g", "ml"]

    @field_validator("ingredient")
    @classmethod
    def clean_ingredient(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("ingredient must not be blank")
        return value


async def client_for(settings: Settings = Depends(get_settings), auth: AuthContext = Depends(get_auth_context)) -> AsyncIterator:
    try:
        client = build_user_client(settings, auth.access_token)
    except DatabaseUnavailable as exc:
        raise ApiError(503, ErrorCode.UPSTREAM_BUSY, "Calibration storage is unavailable.", "Try again shortly.") from exc
    try:
        yield client
    finally:
        await client.aclose()


async def call(client, name: str, params: dict):
    try:
        return await client.rpc(name, params)
    except (DatabaseUnavailable, DatabaseFailure) as exc:
        raise ApiError(502, ErrorCode.UPSTREAM_ERROR, "Calibration could not be saved or loaded.", "Retry shortly.") from exc


def interval(values: list[float], amount_unit: str = "") -> dict:
    if len(values) == 1:
        lo, hi = values[0] * .85, values[0] * 1.15
    else:
        lo, hi = min(values) * .95, max(values) * 1.05
    return {"lo": round(lo, 2), "hi": round(hi, 2), "unit": amount_unit, "basis": "yours"}


@router.get("/me/hand-calibration")
async def get_calibration(auth: AuthContext = Depends(get_auth_context), client=Depends(client_for)):
    data = await call(client, "get_hand_calibration", {"p_owner_user_id": auth.user.id})
    return _with_ranges(data)


@router.post("/me/hand-calibration/weighings", status_code=201)
async def add_weighing(payload: WeighingInput, auth: AuthContext = Depends(get_auth_context), client=Depends(client_for)):
    await call(client, "add_hand_weighing", {"p_owner_user_id": auth.user.id, "p_unit": payload.unit, "p_ingredient": payload.ingredient, "p_amount": payload.amount, "p_amount_unit": payload.amount_unit})
    data = await call(client, "get_hand_calibration", {"p_owner_user_id": auth.user.id})
    return _with_ranges(data)


@router.delete("/me/hand-calibration/weighings/{weighing_id}")
async def delete_weighing(weighing_id: UUID, auth: AuthContext = Depends(get_auth_context), client=Depends(client_for)):
    deleted = await call(client, "delete_hand_weighing", {"p_owner_user_id": auth.user.id, "p_weighing_id": str(weighing_id)})
    if not deleted:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Weighing not found.", "It may already have been removed.")
    return _with_ranges(await call(client, "get_hand_calibration", {"p_owner_user_id": auth.user.id}))


def _with_ranges(data: dict) -> dict:
    groups: dict[tuple[str, str, str], list[float]] = {}
    for row in data.get("weighings", []):
        groups.setdefault((row["unit"], row["ingredient"].casefold(), row["amount_unit"]), []).append(float(row["amount"]))
    ranges = [{"unit": key[0], "ingredient": key[1], "amount_unit": key[2], "range": interval(values, key[2])} for key, values in groups.items()]
    return {**data, "ranges": ranges}
