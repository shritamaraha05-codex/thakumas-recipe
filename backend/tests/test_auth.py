"""Access-token verification and authenticated-route behaviour (M-18B)."""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Iterator

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app.auth import (
    SupabaseTokenVerifier,
    TokenVerificationError,
    TokenVerificationUnavailable,
    get_auth_context,
)
from backend.app.auth.schemas import AuthContext
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.routers.recipes import get_repository
from backend.tests.fakes import (
    FakeStore,
    FakeTokenVerifier,
    build_test_app,
    make_user,
)

PROJECT_URL = "https://project.supabase.co"
ISSUER = f"{PROJECT_URL}/auth/v1"
JWKS_PATH = "/auth/v1/.well-known/jwks.json"
USER_PATH = "/auth/v1/user"


def _settings() -> Settings:
    return Settings(
        supabase_url=PROJECT_URL,
        supabase_publishable_key="test-publishable-key",
        supabase_anon_key="",
        gnani_api_key="",
        gnani_mock=True,
        llm_chain="rules",
        gemini_api_key="",
        gemini_model="",
    )


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks(private_key, kid: str = "test-key") -> dict:
    numbers = private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": kid,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def _claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "sub": "user-1",
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": now + 3600,
        "iat": now,
        "email": "a@example.com",
        "role": "authenticated",
    }
    claims.update(overrides)
    return claims


def _token(private_key, claims: dict | None = None, *, kid: str = "test-key") -> str:
    return jwt.encode(
        claims if claims is not None else _claims(),
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _transport(
    *,
    jwks: dict | None = None,
    user_response: httpx.Response | None = None,
    paths: list[str] | None = None,
    error: Exception | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if paths is not None:
            paths.append(request.url.path)
        if error is not None:
            raise error
        if request.url.path == JWKS_PATH:
            return httpx.Response(200, json=jwks or {"keys": []})
        if request.url.path == USER_PATH:
            return user_response or httpx.Response(401, json={"error": "invalid"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _verify_with(transport: httpx.MockTransport, token: str):
    async def run():
        async with httpx.AsyncClient(transport=transport) as http_client:
            verifier = SupabaseTokenVerifier(
                url=PROJECT_URL,
                publishable_key="test-publishable-key",
                http_client=http_client,
            )
            return await verifier.verify(token)

    return asyncio.run(run())


# --- SupabaseTokenVerifier ---------------------------------------------------


def test_valid_rs256_token_identifies_the_token_subject() -> None:
    private = _keypair()
    user = _verify_with(_transport(jwks=_jwks(private)), _token(private))
    assert user.id == "user-1"
    assert user.email == "a@example.com"
    assert user.role == "authenticated"


def test_expired_token_is_rejected() -> None:
    private = _keypair()
    token = _token(private, _claims(exp=int(time.time()) - 10))
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_wrong_issuer_is_rejected() -> None:
    private = _keypair()
    token = _token(private, _claims(iss="https://evil.example/auth/v1"))
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_wrong_audience_is_rejected() -> None:
    private = _keypair()
    token = _token(private, _claims(aud="service_role"))
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_missing_expiry_is_rejected() -> None:
    private = _keypair()
    claims = _claims()
    del claims["exp"]
    token = _token(private, claims)
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_bad_signature_is_rejected() -> None:
    trusted = _keypair()
    attacker = _keypair()
    token = _token(attacker)
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(trusted)), token)


def test_unknown_key_id_is_rejected() -> None:
    private = _keypair()
    token = _token(private, kid="other-key")
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_algorithm_mismatch_with_jwk_is_rejected() -> None:
    private = _keypair()
    token = jwt.encode(
        _claims(),
        private,
        algorithm="RS512",
        headers={"kid": "test-key"},
    )
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(jwks=_jwks(private)), token)


def test_alg_none_is_rejected() -> None:
    token = jwt.encode(_claims(), None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(), token)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(TokenVerificationError):
        _verify_with(_transport(), "not-a-jwt")


def test_jwks_is_cached_between_verifications() -> None:
    private = _keypair()
    paths: list[str] = []

    async def run():
        async with httpx.AsyncClient(
            transport=_transport(jwks=_jwks(private), paths=paths)
        ) as http:
            verifier = SupabaseTokenVerifier(
                url=PROJECT_URL,
                publishable_key="test-publishable-key",
                http_client=http,
            )
            await verifier.verify(_token(private))
            await verifier.verify(_token(private))

    asyncio.run(run())
    assert paths.count(JWKS_PATH) == 1


def test_unreachable_jwks_is_reported_as_unavailable() -> None:
    request = httpx.Request("GET", f"{PROJECT_URL}{JWKS_PATH}")
    transport = _transport(error=httpx.ConnectError("offline", request=request))
    with pytest.raises(TokenVerificationUnavailable):
        _verify_with(transport, _token(_keypair()))


def test_legacy_hs256_uses_supabase_auth_endpoint_not_a_local_secret() -> None:
    token = jwt.encode(_claims(sub="legacy-user"), "legacy-test-secret-that-is-at-least-32-bytes-long", algorithm="HS256")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "legacy-user",
                "email": "legacy@example.com",
                "role": "authenticated",
                "user_metadata": {"full_name": "Legacy"},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            verifier = SupabaseTokenVerifier(
                url=PROJECT_URL,
                publishable_key="test-publishable-key",
                http_client=http,
            )
            return await verifier.verify(token)

    user = asyncio.run(run())
    assert user.id == "legacy-user"
    assert user.display_name == "Legacy"
    assert [request.url.path for request in seen] == [USER_PATH]
    assert seen[0].headers["apikey"] == "test-publishable-key"
    assert seen[0].headers["authorization"] == f"Bearer {token}"


def test_legacy_hs256_rejected_by_supabase_is_rejected() -> None:
    token = jwt.encode(_claims(), "legacy-test-secret-that-is-at-least-32-bytes-long", algorithm="HS256")
    transport = _transport(user_response=httpx.Response(401, json={"error": "bad"}))
    with pytest.raises(TokenVerificationError):
        _verify_with(transport, token)


def test_unconfigured_verifier_is_unavailable() -> None:
    verifier = SupabaseTokenVerifier(url="", publishable_key="")
    with pytest.raises(TokenVerificationUnavailable):
        asyncio.run(verifier.verify("anything"))


# --- Dependencies and protected routes --------------------------------------


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier(
        {
            "token-a": make_user("user-a", name="Alice"),
            "token-b": make_user("user-b", name="Bob"),
        }
    )


@pytest.fixture
def client(store: FakeStore, verifier: FakeTokenVerifier) -> Iterator[TestClient]:
    with TestClient(build_test_app(_settings(), verifier, store)) as test_client:
        yield test_client


def test_missing_authorization_header_returns_401(client: TestClient) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_malformed_bearer_header_returns_401(client: TestClient) -> None:
    for header in ("Basic abc", "Bearer", "Token abc", "Bearer   "):
        response = client.get("/api/me", headers={"Authorization": header})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/me", headers={"Authorization": "Bearer unknown"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_verifier_unavailable_returns_503(store: FakeStore) -> None:
    verifier = FakeTokenVerifier(error=TokenVerificationUnavailable("offline"))
    app = build_test_app(_settings(), verifier, store)
    with TestClient(app) as test_client:
        response = test_client.get("/api/me", headers={"Authorization": "Bearer token-a"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_BUSY"


def test_valid_token_returns_the_verified_profile(client: TestClient) -> None:
    response = client.get("/api/me", headers={"Authorization": "Bearer token-a"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-a"
    assert body["display_name"] == "Alice"
    assert "access_token" not in body
    assert "token-a" not in response.text


def test_all_recipe_routes_require_authentication(client: TestClient) -> None:
    recipe_id = "00000000-0000-0000-0000-000000000001"
    calls = [
        ("get", "/api/me", None),
        ("post", "/api/recipes", {}),
        ("get", "/api/recipes", None),
        ("get", f"/api/recipes/{recipe_id}", None),
        ("put", f"/api/recipes/{recipe_id}", {}),
        ("delete", f"/api/recipes/{recipe_id}", None),
    ]
    for method, path, body in calls:
        response = (
            getattr(client, method)(path, json=body)
            if body is not None
            else getattr(client, method)(path)
        )
        assert response.status_code == 401, (method, path, response.text)


def test_user_id_comes_from_the_token_not_the_request_body(client: TestClient) -> None:
    response = client.post(
        "/api/recipes",
        headers={"Authorization": "Bearer token-a"},
        json={
            "title": "Owned by token",
            "original_transcript": "এক চামচ তেল",
            "draft": {"recipe": {"title": "Owned by token", "steps": []}, "meta": {}},
            "tags": [],
            "owner_user_id": "user-b",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_concurrent_requests_keep_distinct_authenticated_users(
    store: FakeStore, verifier: FakeTokenVerifier
) -> None:
    app = build_test_app(_settings(), verifier, store)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:

            async def me(token: str):
                response = await http.get("/api/me", headers={"Authorization": f"Bearer {token}"})
                return response.json()

            return await asyncio.gather(me("token-a"), me("token-b"))

    results = asyncio.run(run())
    assert {result["id"] for result in results} == {"user-a", "user-b"}
    assert len({result["display_name"] for result in results}) == 2


def test_default_app_without_a_token_never_calls_the_network() -> None:
    app = create_app(_settings())
    with TestClient(app) as test_client:
        response = test_client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_repository_is_not_built_without_authentication() -> None:
    def forbidden(
        auth: AuthContext = Depends(get_auth_context),
    ):  # pragma: no cover - must never run
        raise AssertionError("repository was built before authentication")

    app = create_app(_settings())
    app.dependency_overrides[get_repository] = forbidden
    with TestClient(app) as test_client:
        response = test_client.get("/api/recipes")
    assert response.status_code == 401
