"""Bearer-token auth on /api/v1 and the CORS allowlist."""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import get_settings
from main import app
from tests.conftest import TEST_USER_ID, api_url

_PATH = api_url("/invoices/")


async def _anon(headers=None):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers or {})


@pytest.mark.asyncio
async def test_missing_token_rejected(client):
    async with await _anon() as c:
        r = await c.get(_PATH)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_wrong_token_rejected():
    async with await _anon({"Authorization": "Bearer nope"}) as c:
        r = await c.get(_PATH)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_scheme_rejected():
    async with await _anon({"Authorization": "Basic test-api-token"}) as c:
        r = await c.get(_PATH)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_correct_token_accepted(client):
    r = await client.get(_PATH)
    assert r.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("configured", ["", "CHANGE_ME", "change-me-generate-a-random-value"])
async def test_unconfigured_or_placeholder_token_fails_closed(configured):
    # Even a request echoing the configured value must be refused.
    with patch.object(get_settings(), "api_token", configured):
        async with await _anon({"Authorization": f"Bearer {configured}"}) as c:
            r = await c.get(_PATH)
    assert r.status_code == 401


def test_every_api_route_requires_auth_except_webhook():
    """Guards against a future endpoint forgetting get_current_user."""
    from api.dependencies import get_current_user

    def deps(route):
        stack, seen = list(route.dependant.dependencies), set()
        while stack:
            d = stack.pop()
            seen.add(d.call)
            stack.extend(d.dependencies)
        return seen

    unprotected = [
        r.path
        for r in app.routes
        if getattr(r, "dependant", None)
        and r.path.startswith("/api/v1")
        and get_current_user not in deps(r)
    ]
    assert unprotected == ["/api/v1/webhooks/oegk-refund-ready"]


@pytest.mark.asyncio
async def test_cors_allows_configured_origin_only():
    async with await _anon() as c:
        ok = await c.options(
            _PATH,
            headers={"Origin": "https://kaiserclaim.home", "Access-Control-Request-Method": "GET"},
        )
        bad = await c.options(
            _PATH,
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
    assert ok.headers.get("access-control-allow-origin") == "https://kaiserclaim.home"
    assert "access-control-allow-origin" not in bad.headers
