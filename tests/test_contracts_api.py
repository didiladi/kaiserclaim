"""
End-to-end tests for the contracts API endpoints.

parse_contract_full (Gemini) is mocked so tests are fast and offline.
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import TEST_USER_ID, api_url

SAMPLE_PDF = Path(__file__).parent / "fixtures" / "sample.pdf"

# Dummy text returned instead of running OCR/pdfminer — avoids needing system tools.
_DUMMY_PDF_TEXT = "Polizze Test\n\nVersicherungsnehmer\nMax Mustermann\n\n" + "x " * 200


def _parse_patches(extraction: dict):
    """Context manager that mocks both pdf extraction and Gemini."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch(
        "api.endpoints.contracts.pdf_to_text_native",
        new=AsyncMock(return_value=_DUMMY_PDF_TEXT),
    ))
    stack.enter_context(patch(
        "api.endpoints.contracts.parse_contract_full",
        new=AsyncMock(return_value=extraction),
    ))
    return stack

# ---------------------------------------------------------------------------
# Minimal mock extraction result — 2 persons, 2 tariffs, a few benefits
# ---------------------------------------------------------------------------

_MOCK_EXTRACTION = {
    "persons": [
        {
            "full_name": "Jennifer Testperson",
            "kd_nr": "KD-001",
            "birth_date": "1992-10-16",
            "tariffs": [
                {
                    "code": "MENG1E252",
                    "name": "NOVUM",
                    "description_raw": "Test tariff",
                    "benefits": [
                        {
                            "benefit_name": "Ambulante Vorsorge",
                            "benefit_kind": "BUDGET",
                            "limit_amount": 150.0,
                            "reimbursement_pct": 100.0,
                            "reset_period": "CALENDAR_YEAR",
                            "category": "Physiotherapie",
                            "notes": None,
                        },
                        {
                            "benefit_name": "ego4you",
                            "benefit_kind": "PROGRAM",
                            "limit_amount": None,
                            "reimbursement_pct": None,
                            "reset_period": "ONCE_PER_YEAR",
                            "category": None,
                            "notes": "Präventionsprogramm",
                        },
                    ],
                }
            ],
        },
        {
            "full_name": "Dieter Testperson",
            "kd_nr": "KD-002",
            "birth_date": "1987-02-17",
            "tariffs": [
                {
                    "code": "MHNG1E25S1",
                    "name": "NOVUM SMART",
                    "description_raw": "Test tariff 2",
                    "benefits": [
                        {
                            "benefit_name": "Zahnreinigung",
                            "benefit_kind": "BUDGET",
                            "limit_amount": 100.0,
                            "reimbursement_pct": 80.0,
                            "reset_period": "CALENDAR_YEAR",
                            "category": "Zahnreinigung",
                            "notes": None,
                        }
                    ],
                }
            ],
        },
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_contract(client, provider="Merkur Test") -> str:
    r = await client.post(
        api_url("/contracts/"),
        json={"provider_name": provider, "policy_number": "TEST-001"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_contract(client):
    """POST /contracts/ creates a contract owned by the test user."""
    r = await client.post(
        api_url("/contracts/"),
        json={"provider_name": "Merkur", "policy_number": "0.187.036"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["provider_name"] == "Merkur"
    assert data["policy_number"] == "0.187.036"
    assert data["user_id"] == str(TEST_USER_ID)


@pytest.mark.asyncio
async def test_list_contracts(client):
    """GET /contracts/ lists contracts for the test user."""
    await _create_contract(client, "ListTest")
    r = await client.get(api_url("/contracts/"))
    assert r.status_code == 200
    ids = [c["provider_name"] for c in r.json()]
    assert "ListTest" in ids


@pytest.mark.asyncio
async def test_coverage_empty_before_parse(client):
    """GET /contracts/{id}/coverage returns empty insured_persons before any parse."""
    contract_id = await _create_contract(client)
    r = await client.get(api_url(f"/contracts/{contract_id}/coverage"))
    assert r.status_code == 200
    assert r.json()["insured_persons"] == []


@pytest.mark.asyncio
async def test_coverage_unknown_contract(client):
    """GET /contracts/{unknown}/coverage returns 404."""
    r = await client.get(api_url(f"/contracts/{uuid.uuid4()}/coverage"))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_parse_pdf_success(client):
    """POST parse-pdf with mocked Gemini returns ContractCoverageRead with correct persons."""
    contract_id = await _create_contract(client)

    with _parse_patches(_MOCK_EXTRACTION):
        with SAMPLE_PDF.open("rb") as f:
            r = await client.post(
                api_url(f"/contracts/{contract_id}/parse-pdf"),
                files={"file": ("polizze.pdf", f, "application/pdf")},
            )

    assert r.status_code == 200, r.text
    coverage = r.json()
    assert coverage["contract_id"] == contract_id

    persons = coverage["insured_persons"]
    assert len(persons) == 2

    names = [p["full_name"] for p in persons]
    assert "Jennifer Testperson" in names
    assert "Dieter Testperson" in names

    jennifer = next(p for p in persons if "Jennifer" in p["full_name"])
    assert len(jennifer["tariffs"]) == 1
    assert jennifer["tariffs"][0]["code"] == "MENG1E252"
    benefits = jennifer["tariffs"][0]["benefits"]
    benefit_names = [b["benefit_name"] for b in benefits]
    assert "Ambulante Vorsorge" in benefit_names
    assert "ego4you" in benefit_names

    # ego4you should be PROGRAM with no limit_amount
    ego = next(b for b in benefits if b["benefit_name"] == "ego4you")
    assert ego["benefit_kind"] == "PROGRAM"
    assert ego["limit_amount"] is None
    assert ego["reset_period"] == "ONCE_PER_YEAR"


@pytest.mark.asyncio
async def test_parse_pdf_gemini_failure_returns_503(client):
    """When Gemini raises an exception, parse-pdf returns 503 with a descriptive message."""
    contract_id = await _create_contract(client)

    with patch("api.endpoints.contracts.pdf_to_text_native", new=AsyncMock(return_value=_DUMMY_PDF_TEXT)):
        with patch(
            "api.endpoints.contracts.parse_contract_full",
            new=AsyncMock(side_effect=Exception("API key not valid")),
        ):
            with SAMPLE_PDF.open("rb") as f:
                r = await client.post(
                    api_url(f"/contracts/{contract_id}/parse-pdf"),
                    files={"file": ("polizze.pdf", f, "application/pdf")},
                )

    assert r.status_code == 503
    assert "KI-Analyse fehlgeschlagen" in r.json()["detail"]
    assert "API key not valid" in r.json()["detail"]


@pytest.mark.asyncio
async def test_parse_pdf_idempotent(client):
    """Calling parse-pdf twice replaces persons from first call."""
    contract_id = await _create_contract(client)

    first = {
        "persons": [
            {
                "full_name": "First Person",
                "kd_nr": None,
                "birth_date": None,
                "tariffs": [{"code": "TARIFF1", "name": None, "description_raw": None, "benefits": []}],
            }
        ]
    }
    second = {
        "persons": [
            {
                "full_name": "Second Person",
                "kd_nr": None,
                "birth_date": None,
                "tariffs": [{"code": "TARIFF2", "name": None, "description_raw": None, "benefits": []}],
            }
        ]
    }

    for extraction in [first, second]:
        with _parse_patches(extraction):
            with SAMPLE_PDF.open("rb") as f:
                r = await client.post(
                    api_url(f"/contracts/{contract_id}/parse-pdf"),
                    files={"file": ("polizze.pdf", f, "application/pdf")},
                )
        assert r.status_code == 200

    # Only second-call person should remain
    r = await client.get(api_url(f"/contracts/{contract_id}/coverage"))
    persons = r.json()["insured_persons"]
    assert len(persons) == 1
    assert persons[0]["full_name"] == "Second Person"


@pytest.mark.asyncio
async def test_coverage_after_parse(client):
    """GET /coverage after parse returns the mocked extraction data."""
    contract_id = await _create_contract(client)

    with _parse_patches(_MOCK_EXTRACTION):
        with SAMPLE_PDF.open("rb") as f:
            await client.post(
                api_url(f"/contracts/{contract_id}/parse-pdf"),
                files={"file": ("polizze.pdf", f, "application/pdf")},
            )

    r = await client.get(api_url(f"/contracts/{contract_id}/coverage"))
    assert r.status_code == 200
    persons = r.json()["insured_persons"]
    assert len(persons) == 2
    # Each person has their tariff and benefits
    dieter = next(p for p in persons if "Dieter" in p["full_name"])
    assert dieter["tariffs"][0]["benefits"][0]["benefit_name"] == "Zahnreinigung"
