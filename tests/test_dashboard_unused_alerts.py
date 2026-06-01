"""
Tests for the unused_alerts logic in GET /dashboard/summary.

Contracts are created via the HTTP API. Benefit rules are injected via a
mocked parse_contract_full so we control the benefit_kind / reset_period
without needing direct DB access.
"""
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import api_url

SAMPLE_PDF = Path(__file__).parent / "fixtures" / "sample.pdf"
_DUMMY_PDF_TEXT = "Polizze Test\n\nVersicherungsnehmer\nMax Mustermann\n\n" + "x " * 200


def _program_extraction(benefit_name: str = "Test ego4you Alert") -> dict:
    return {
        "persons": [
            {
                "full_name": "Alert Testperson",
                "kd_nr": None,
                "birth_date": None,
                "tariffs": [
                    {
                        "code": "ALERT-TARIFF",
                        "name": None,
                        "description_raw": None,
                        "benefits": [
                            {
                                "benefit_name": benefit_name,
                                "benefit_kind": "PROGRAM",
                                "limit_amount": None,
                                "reimbursement_pct": None,
                                "reset_period": "ONCE_PER_YEAR",
                                "category": None,
                                "notes": None,
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _budget_extraction(benefit_name: str = "Test ego4you Alert") -> dict:
    return {
        "persons": [
            {
                "full_name": "Alert Testperson",
                "kd_nr": None,
                "birth_date": None,
                "tariffs": [
                    {
                        "code": "ALERT-TARIFF",
                        "name": None,
                        "description_raw": None,
                        "benefits": [
                            {
                                "benefit_name": benefit_name,
                                "benefit_kind": "BUDGET",
                                "limit_amount": 300.0,
                                "reimbursement_pct": None,
                                "reset_period": "CALENDAR_YEAR",
                                "category": None,
                                "notes": None,
                            }
                        ],
                    }
                ],
            }
        ]
    }


async def _seed_benefit(client, extraction: dict) -> str:
    """Create a contract and seed it with the given extraction."""
    r = await client.post(
        api_url("/contracts/"),
        json={"provider_name": "AlertTest", "policy_number": "TEST-ALERT"},
    )
    assert r.status_code == 201
    contract_id = r.json()["id"]

    with patch("api.endpoints.contracts.pdf_to_text_native", new=AsyncMock(return_value=_DUMMY_PDF_TEXT)):
        with patch("api.endpoints.contracts.parse_contract_full", new=AsyncMock(return_value=extraction)):
            with SAMPLE_PDF.open("rb") as f:
                r = await client.post(
                    api_url(f"/contracts/{contract_id}/parse-pdf"),
                    files={"file": ("polizze.pdf", f, "application/pdf")},
                )
    assert r.status_code == 200, r.text
    return contract_id


@pytest.mark.asyncio
async def test_dashboard_summary_has_unused_alerts_key(client):
    """GET /dashboard/summary always returns the unused_alerts key."""
    r = await client.get(api_url("/dashboard/summary"))
    assert r.status_code == 200
    assert "unused_alerts" in r.json()
    assert isinstance(r.json()["unused_alerts"], list)


@pytest.mark.asyncio
async def test_unused_alerts_empty_in_may(client):
    """In May, ONCE_PER_YEAR benefits are 217 days from Dec 31 — outside the 56-day window."""
    await _seed_benefit(client, _program_extraction("May Test ego4you"))

    with patch("api.endpoints.stats.date") as mock_date:
        mock_date.today.return_value = date(2026, 5, 28)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        r = await client.get(api_url("/dashboard/summary"))

    assert r.status_code == 200
    names = [a["benefit_name"] for a in r.json()["unused_alerts"]]
    assert "May Test ego4you" not in names


@pytest.mark.asyncio
async def test_unused_alerts_fires_in_november(client):
    """On Nov 15, ONCE_PER_YEAR benefits are 46 days from Dec 31 — inside the 56-day window."""
    await _seed_benefit(client, _program_extraction("Nov Test ego4you"))

    with patch("api.endpoints.stats.date") as mock_date:
        mock_date.today.return_value = date(2026, 11, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        r = await client.get(api_url("/dashboard/summary"))

    assert r.status_code == 200
    alerts = r.json()["unused_alerts"]
    names = [a["benefit_name"] for a in alerts]
    assert "Nov Test ego4you" in names

    alert = next(a for a in alerts if a["benefit_name"] == "Nov Test ego4you")
    assert alert["days_until_reset"] == 46
    assert alert["reset_date"] == "2026-12-31"


@pytest.mark.asyncio
async def test_unused_alerts_budget_under_30pct_fires(client):
    """A BUDGET benefit with 0% used fires an alert in November."""
    await _seed_benefit(client, _budget_extraction("Nov Test Budget"))

    with patch("api.endpoints.stats.date") as mock_date:
        mock_date.today.return_value = date(2026, 11, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        r = await client.get(api_url("/dashboard/summary"))

    assert r.status_code == 200
    names = [a["benefit_name"] for a in r.json()["unused_alerts"]]
    assert "Nov Test Budget" in names
