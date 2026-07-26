"""
Adapter: FakturaItemValidator.ValidationResult → ValidationFinding.

Plan §13: ne prepisivati postojeće validatore — samo prevoditi.
Koristi alias za import (Faza -1.D — kolizija imena ValidationResult).
"""

from __future__ import annotations

# ALIAS — Faza -1.D: ValidationResult postoji na dva mjesta
from services.validation.validation_service import (
    ValidationResult as FakturaValidationResult,
)

from services.agent.validation.finding_model import (
    FindingCode,
    FindingSeverity,
    ValidationFinding,
)


# Mapa field → FindingCode
_FIELD_CODE_MAP: dict[str, str] = {
    "tarifni_broj": FindingCode.MISSING_TARIFF,
    "naziv_robe": FindingCode.MISSING_AMOUNT,
    "zemlja_porijekla": FindingCode.MISSING_ORIGIN,
    "bruto_kg": FindingCode.INVALID_WEIGHT,
    "neto_kg": FindingCode.INVALID_WEIGHT,
    "kolicina": FindingCode.INVALID_QUANTITY,
    "iznos": FindingCode.MISSING_AMOUNT,
    "jm": FindingCode.INVALID_QUANTITY,
}


def _severity_from_level(level_name: str) -> str:
    level_map = {
        "CRITICAL": FindingSeverity.BLOCKING,
        "ERROR": FindingSeverity.BLOCKING,
        "WARNING": FindingSeverity.WARNING,
    }
    return level_map.get(level_name.upper() if hasattr(level_name, "upper") else str(level_name), FindingSeverity.WARNING)


def adapt_invoice_validation(
    result: FakturaValidationResult,
    row_index: int = 0,
    source: str = "FakturaItemValidator",
) -> list[ValidationFinding]:
    """Konvertuj FakturaItemValidator.ValidationResult u listu ValidationFinding."""
    findings: list[ValidationFinding] = []

    for error in result.errors:
        level = getattr(error, "level", None)
        level_str = level.name if hasattr(level, "name") else str(level)
        field_name = getattr(error, "field", "")
        message = getattr(error, "message", "")
        suggestion = getattr(error, "suggestion", "")
        code = _FIELD_CODE_MAP.get(field_name, FindingCode.HEADER_REQUIRED_FIELD)

        findings.append(ValidationFinding(
            severity=_severity_from_level(level_str),
            code=code,
            target="invoice",
            location=f"stavka {row_index + 1}" if row_index > 0 else "faktura",
            message=message,
            evidence={"field": field_name, "level": level_str},
            source=source,
            auto_fixable=False,
            suggested_action=suggestion,
            blocking=level_str in ("CRITICAL", "ERROR"),
        ))

    for warning in result.warnings:
        field_name = getattr(warning, "field", "")
        message = getattr(warning, "message", "")
        code = _FIELD_CODE_MAP.get(field_name, FindingCode.HEADER_REQUIRED_FIELD)

        findings.append(ValidationFinding(
            severity=FindingSeverity.WARNING,
            code=code,
            target="invoice",
            location=f"stavka {row_index + 1}" if row_index > 0 else "faktura",
            message=message,
            evidence={"field": field_name},
            source=source,
            auto_fixable=False,
            suggested_action=getattr(warning, "suggestion", ""),
            blocking=False,
        ))

    return findings
