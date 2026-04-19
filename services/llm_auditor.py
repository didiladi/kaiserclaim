"""
Parses an insurance contract PDF (as plain text) into structured BenefitRules
using the Google Gemini API.
"""
import json
import re
from typing import List

import google.generativeai as genai

from core.config import get_settings
from schemas.payload import BenefitRuleCreate
from models.domain import LimitType

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

_MODEL = "gemini-1.5-flash"

_SYSTEM_PROMPT = """\
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


async def parse_contract(contract_text: str) -> List[BenefitRuleCreate]:
    model = genai.GenerativeModel(_MODEL)
    response = await model.generate_content_async(
        [_SYSTEM_PROMPT, contract_text],
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


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
