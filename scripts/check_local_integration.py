#!/usr/bin/env python3
"""Local integration smoke test for the FastAPI backend.

Checks that a locally running backend speaks the contract the vanilla
frontend expects. Uses only the Python standard library, needs no Supabase
credentials, never calls Gemini and never modifies database records.

Usage (with the backend already running)::

    uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
    python scripts/check_local_integration.py

Environment overrides:
    THAKUMA_BACKEND_URL      default http://127.0.0.1:8000
    THAKUMA_FRONTEND_ORIGIN  default http://localhost:5173

Exit code is 0 only when every check passes.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BACKEND_URL = os.environ.get("THAKUMA_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
FRONTEND_ORIGIN = os.environ.get("THAKUMA_FRONTEND_ORIGIN", "http://localhost:5173")

SAMPLE_TEXT = "এক চামচ তেল দাও। তারপর এক মুঠো চাল দাও।"

_results: list[tuple[bool, str]] = []


def _record(ok: bool, label: str, detail: str = "") -> None:
    _results.append((ok, label))
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" - {detail}"
    print(line)


def _call(method: str, path: str, *, body: dict | None = None, headers: dict | None = None):
    """Return (status, headers, text). HTTP error responses are returned, not raised."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{BACKEND_URL}{path}", data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if body is not None and not request.has_header("Content-Type"):
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return (
                response.status,
                dict(response.headers),
                response.read().decode("utf-8", "replace"),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"FAIL cannot reach {BACKEND_URL} ({exc.reason}). Is the backend running?"
        ) from exc


def _json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except ValueError:
        return None


def check_backend_reachable() -> None:
    status, _, text = _call("GET", "/api/health")
    _record(status == 200, "GET /api/health is reachable", f"status {status}")


def check_health_payload() -> None:
    status, _, text = _call("GET", "/api/health")
    payload = _json(text) or {}
    ok = status == 200 and payload.get("ok") is True and isinstance(payload.get("db"), dict)
    db_status = (payload.get("db") or {}).get("status", "?")
    _record(ok, "GET /api/health returns a valid payload", f"db.status={db_status}")


def check_rules_parse() -> None:
    status, _, text = _call("POST", "/api/parse", body={"text": SAMPLE_TEXT, "mode": "rules"})
    payload = _json(text) or {}
    recipe = payload.get("recipe") or {}
    meta = payload.get("meta") or {}
    steps = recipe.get("steps") or []
    ok = status == 200 and len(steps) > 0 and meta.get("parser_mode") == "rules"
    _record(ok, "POST /api/parse (rules) returns a structured recipe", f"{len(steps)} step(s)")


def check_unauthenticated_me() -> None:
    status, _, text = _call("GET", "/api/me")
    payload = _json(text) or {}
    code = (payload.get("error") or {}).get("code")
    ok = status == 401 and code == "UNAUTHORIZED"
    _record(ok, "GET /api/me without a token is 401 UNAUTHORIZED", f"status {status}")


def check_unauthenticated_recipes() -> None:
    status, _, text = _call("GET", "/api/recipes")
    payload = _json(text) or {}
    code = (payload.get("error") or {}).get("code")
    ok = status == 401 and code == "UNAUTHORIZED"
    _record(ok, "GET /api/recipes without a token is 401 UNAUTHORIZED", f"status {status}")


def check_cors_preflight() -> None:
    headers = {
        "Origin": FRONTEND_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    status, response_headers, _ = _call("OPTIONS", "/api/parse", headers=headers)
    allow_origin = response_headers.get("Access-Control-Allow-Origin", "") or response_headers.get(
        "access-control-allow-origin", ""
    )
    allow_headers = (
        response_headers.get("Access-Control-Allow-Headers", "")
        or response_headers.get("access-control-allow-headers", "")
    ).lower()
    allow_methods = (
        response_headers.get("Access-Control-Allow-Methods", "")
        or response_headers.get("access-control-allow-methods", "")
    ).upper()
    origin_ok = allow_origin == FRONTEND_ORIGIN
    auth_ok = "authorization" in allow_headers
    method_ok = "POST" in allow_methods
    ok = status in (200, 204) and origin_ok and auth_ok and method_ok
    _record(
        ok,
        f"CORS preflight from {FRONTEND_ORIGIN} allows Authorization",
        f"status {status}, origin={allow_origin or 'missing'}",
    )


def main() -> int:
    print(f"Backend: {BACKEND_URL}   Origin: {FRONTEND_ORIGIN}\n")
    check_backend_reachable()
    check_health_payload()
    check_rules_parse()
    check_unauthenticated_me()
    check_unauthenticated_recipes()
    check_cors_preflight()

    passed = sum(1 for ok, _ in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} checks passed.")
    if passed != total:
        print("Some checks failed. Is the backend running and is FRONTEND_ORIGINS set?")
        return 1
    print("Backend and the frontend's expected contract agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
