"""AI data extraction layer.

Converts raw OCR text into structured healthcare data using Anthropic Claude
with structured outputs. Falls back to a deterministic regex/template extractor
when no API key is configured, so the pipeline always runs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# The structured shape we ask Claude to return.
EXTRACTION_FIELDS = [
    "patient_name",
    "dob",
    "insurance_provider",
    "insurance_member_id",
    "referring_doctor",
    "diagnosis",
    "referral_reason",
]

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fields": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                f: {"type": ["string", "null"]} for f in EXTRACTION_FIELDS
            },
            "required": EXTRACTION_FIELDS,
        },
        "field_confidence": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                f: {"type": "number"} for f in EXTRACTION_FIELDS
            },
            "required": EXTRACTION_FIELDS,
        },
        "notes": {"type": "string"},
    },
    "required": ["fields", "field_confidence", "notes"],
}

_SYSTEM_PROMPT = (
    "You are a clinical intake specialist extracting structured data from healthcare "
    "referral documents. Extract only what is explicitly present in the text. For any "
    "field you cannot find, return null and give it a low confidence score. Confidence "
    "is a 0.0-1.0 estimate of how certain you are the value is correct. Normalize dates "
    "to ISO 8601 (YYYY-MM-DD) when possible. Do not invent values."
)


@dataclass
class ExtractionResult:
    fields: dict[str, str | None]
    field_confidence: dict[str, float]
    extractor: str
    notes: str = ""
    overall_confidence: float = field(default=0.0)

    def __post_init__(self) -> None:
        if self.field_confidence:
            self.overall_confidence = round(
                sum(self.field_confidence.values()) / len(self.field_confidence), 3
            )


def extract(text: str) -> ExtractionResult:
    """Extract structured data from referral text."""
    if settings.has_llm:
        try:
            return _extract_with_claude(text)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully to template
            from app.core.metrics import extraction_failures

            extraction_failures.labels(reason=type(exc).__name__).inc()
            logger.warning("Claude extraction failed, using template fallback: %s", exc)
    return _extract_with_template(text)


def _extract_with_claude(text: str) -> ExtractionResult:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": _JSON_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract the referral fields from this document text:\n\n"
                    f"<document>\n{text}\n</document>"
                ),
            }
        ],
    )

    payload = _first_json(response)
    fields = {f: payload["fields"].get(f) for f in EXTRACTION_FIELDS}
    confidence = {
        f: float(payload["field_confidence"].get(f, 0.0)) for f in EXTRACTION_FIELDS
    }
    return ExtractionResult(
        fields=fields,
        field_confidence=confidence,
        extractor="claude",
        notes=payload.get("notes", ""),
    )


def _first_json(response: Any) -> dict[str, Any]:
    """Pull the JSON object out of a Claude structured-output response."""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise ValueError("No text block in Claude response")


# ── Deterministic fallback ───────────────────────────────────────────

_PATTERNS: dict[str, re.Pattern[str]] = {
    "patient_name": re.compile(r"patient(?:\s*name)?\s*[:\-]\s*(.+)", re.I),
    "dob": re.compile(r"(?:dob|date of birth)\s*[:\-]\s*(.+)", re.I),
    "insurance_provider": re.compile(r"insurance(?:\s*provider)?\s*[:\-]\s*(.+)", re.I),
    "insurance_member_id": re.compile(r"(?:member|policy)\s*(?:id|#|number)\s*[:\-]\s*(.+)", re.I),
    "referring_doctor": re.compile(r"(?:referring|provider|physician|dr\.?)\s*(?:doctor)?\s*[:\-]\s*(.+)", re.I),
    "diagnosis": re.compile(r"diagnos[ie]s\s*[:\-]\s*(.+)", re.I),
    "referral_reason": re.compile(r"(?:reason|reason for referral)\s*[:\-]\s*(.+)", re.I),
}


def _extract_with_template(text: str) -> ExtractionResult:
    fields: dict[str, str | None] = {}
    confidence: dict[str, float] = {}
    for name, pattern in _PATTERNS.items():
        match = pattern.search(text or "")
        if match:
            value = match.group(1).strip().splitlines()[0].strip()
            fields[name] = value or None
            confidence[name] = 0.6 if value else 0.0
        else:
            fields[name] = None
            confidence[name] = 0.0
    return ExtractionResult(
        fields=fields,
        field_confidence=confidence,
        extractor="template",
        notes="Extracted with deterministic template (no LLM key configured).",
    )
