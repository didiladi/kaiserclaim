"""
Parses an insurance contract PDF into per-person, per-tariff BenefitRules
using the Google Gemini API.

Two-stage extraction:
  1. Persons + tariffs pass — who is insured, under which tariff codes.
  2. Benefits pass — for each BVB section (keyed by tariff code), extract
     structured benefit rules including preventive programs.
"""
import json
import re
from typing import Any

import google.generativeai as genai

from core.config import get_settings
from schemas.payload import BenefitRuleCreate
from models.domain import LimitType

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

_MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Stage 1 — Persons & tariffs
# ---------------------------------------------------------------------------

_PERSONS_PROMPT = """\
You are an expert at reading Austrian private health insurance contracts written in German.

Extract all insured persons from this Merkur insurance policy document.
Return a JSON array where each element represents one insured person with:
- full_name: string (e.g. "Mustermann Maria")
- kd_nr: string or null (Kd.Nr. / Kundennummer)
- birth_date: string or null (ISO date e.g. "1985-03-22", from "Geb.Dat." or similar)
- tariffs: array of objects, each with:
    - code: string (e.g. "MHNG1E25S1", "MENG1E252", "MHBABY/25")
    - name: string or null (e.g. "NOVUM SMART", "NOVUM")
    - description_raw: string or null (one-line description if present)

Look for sections titled "Versicherte Personen", "Versicherungsnehmer", or tables listing names with Kd.Nr. and tariff codes.
Return ONLY the raw JSON array, no markdown, no explanation.
"""

# ---------------------------------------------------------------------------
# Stage 2 — Benefits per tariff
# ---------------------------------------------------------------------------

_BENEFITS_PROMPT_TMPL = """\
You are an expert at reading Austrian private health insurance contracts written in German.

Extract all benefit rules from the BVB (Besondere Versicherungsbedingungen / "Zweiter Abschnitt – Leistungen") \
for these tariff codes: {tariff_codes}.

Return a JSON object where each key is a tariff code and the value is an array of benefit rules.
Each benefit rule has:
- benefit_name: string (e.g. "Zahnreinigung", "Brillen", "ego4you", "Physiotherapie")
- benefit_kind: one of "BUDGET" (euro cap), "PROGRAM" (use-once preventive program like ego4you), "DEDUCTIBLE" (Selbstbehalt)
- limit_amount: number or null (the maximum reimbursable EUR amount; null for PROGRAM benefits)
- reimbursement_pct: number or null (e.g. 80.0 for 80%; null if not specified)
- reset_period: one of "CALENDAR_YEAR", "INSURANCE_YEAR", "PER_EVENT", "ONCE_PER_YEAR"
  - Use CALENDAR_YEAR for "pro Kalenderjahr", INSURANCE_YEAR for "pro Versicherungsjahr"
  - Use ONCE_PER_YEAR for once-per-year preventive programs like ego4you, time4me
  - Use PER_EVENT for per-case / per-instance benefits
- category: one of "Zahnreinigung", "Physiotherapie", "Allgemeinmedizin", "Medikamente", "Sehbehelfe", "Kinderarzt" or null
- notes: string or null (brief clarification e.g. "inkl. Rezeptgebühr", "Selbstbehalt 20%")

Important:
- Capture preventive programs (ego4you, time4me, Gesundheitsprogramme, etc.) as benefit_kind "PROGRAM" with reset_period "ONCE_PER_YEAR"
- Capture yearly deductibles (Selbstbehalt) as benefit_kind "DEDUCTIBLE"
- If a tariff code has no section in the BVB, return an empty array for it

Return ONLY the raw JSON object (keys = tariff codes, values = arrays), no markdown, no explanation.
"""


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


async def parse_contract_full(contract_text: str) -> dict[str, Any]:
    """
    Two-stage extraction returning a nested structure:
    {
      "persons": [
        {
          "full_name": ..., "kd_nr": ..., "birth_date": ...,
          "tariffs": [
            {
              "code": ..., "name": ..., "description_raw": ...,
              "benefits": [
                { "benefit_name": ..., "benefit_kind": ..., "limit_amount": ...,
                  "reimbursement_pct": ..., "reset_period": ..., "category": ..., "notes": ... }
              ]
            }
          ]
        }
      ]
    }
    """
    model = genai.GenerativeModel(_MODEL)

    # Stage 1: persons + tariff codes
    r1 = await model.generate_content_async(
        [_PERSONS_PROMPT, contract_text],
        generation_config={"response_mime_type": "application/json"},
    )
    persons: list[dict] = json.loads(_strip_markdown_fences(r1.text))

    # Collect all unique tariff codes
    all_tariff_codes = []
    seen = set()
    for person in persons:
        for tariff in person.get("tariffs", []):
            code = tariff.get("code", "")
            if code and code not in seen:
                all_tariff_codes.append(code)
                seen.add(code)

    # Stage 2: benefits per tariff
    benefits_by_tariff: dict[str, list[dict]] = {}
    if all_tariff_codes:
        benefits_prompt = _BENEFITS_PROMPT_TMPL.format(
            tariff_codes=", ".join(all_tariff_codes)
        )
        r2 = await model.generate_content_async(
            [benefits_prompt, contract_text],
            generation_config={"response_mime_type": "application/json"},
        )
        benefits_by_tariff = json.loads(_strip_markdown_fences(r2.text))

    # Join: attach benefits to each tariff in each person
    for person in persons:
        for tariff in person.get("tariffs", []):
            code = tariff.get("code", "")
            tariff["benefits"] = benefits_by_tariff.get(code, [])

    return {"persons": persons}


# ---------------------------------------------------------------------------
# Legacy flat extraction (kept for backward compatibility / manual benefit creation)
# ---------------------------------------------------------------------------

_LEGACY_SYSTEM_PROMPT = """\
You are an expert at reading Austrian private health insurance contracts written in German.
Your task is to extract all benefit quota rules from the provided contract text.

Return a JSON array where each element has exactly these fields:
- benefit_name: string (e.g. "Zahnreinigung", "Brille", "Physiotherapie")
- limit_amount: number (the maximum reimbursable amount in EUR)
- limit_type: one of "YEARLY" or "BIANNUAL"
- reset_date: null (we will compute resets dynamically)

Only include benefits that have a concrete monetary limit. Ignore general coverage text.
Return ONLY the raw JSON array, no markdown, no explanation.
"""


async def parse_contract(contract_text: str) -> list[BenefitRuleCreate]:
    """Legacy flat extraction. Kept for manual benefit-rule creation endpoints."""
    model = genai.GenerativeModel(_MODEL)
    response = await model.generate_content_async(
        [_LEGACY_SYSTEM_PROMPT, contract_text],
        generation_config={"response_mime_type": "application/json"},
    )

    raw = _strip_markdown_fences(response.text)
    items = json.loads(raw)
    return [
        BenefitRuleCreate(
            benefit_name=item["benefit_name"],
            limit_amount=float(item["limit_amount"]),
            limit_type=LimitType(item["limit_type"]),
            reset_date=item.get("reset_date"),
        )
        for item in items
    ]
