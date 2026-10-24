"""Family API: the Sozialversicherungsnummer is write-only PII."""
import uuid

import pytest

from tests.conftest import api_url

_SVNR = "1234010190"


def _member(svnr=None) -> dict:
    key = f"t{uuid.uuid4().hex[:8]}"
    body = {"member_key": key, "name": "Test Person", "color": "#123456", "initials": "TP"}
    if svnr is not None:
        body["svnr"] = svnr
    return body


@pytest.mark.asyncio
async def test_svnr_is_never_returned(client):
    resp = await client.post(api_url("/family/"), json=_member(_SVNR))
    assert resp.status_code == 201
    data = resp.json()
    try:
        assert data["has_svnr"] is True
        assert "svnr" not in data
        assert _SVNR not in resp.text

        listed = await client.get(api_url("/family/"))
        assert _SVNR not in listed.text
    finally:
        await client.delete(api_url(f"/family/{data['id']}"))


@pytest.mark.asyncio
async def test_patch_sets_and_clears_svnr(client):
    created = (await client.post(api_url("/family/"), json=_member())).json()
    try:
        assert created["has_svnr"] is False

        resp = await client.patch(api_url(f"/family/{created['id']}"), json={"svnr": _SVNR})
        assert resp.status_code == 200
        assert resp.json()["has_svnr"] is True

        resp = await client.patch(api_url(f"/family/{created['id']}"), json={"svnr": None})
        assert resp.json()["has_svnr"] is False
    finally:
        await client.delete(api_url(f"/family/{created['id']}"))


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["123", "12345678901", "abcdefghij"])
async def test_invalid_svnr_rejected(client, bad):
    resp = await client.post(api_url("/family/"), json=_member(bad))
    assert resp.status_code == 422
    assert bad not in resp.text  # the error body must not echo the rejected value
