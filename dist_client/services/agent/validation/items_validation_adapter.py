"""
Adapter: NaimenovanjeValidator.ValidationResult → ValidationFinding.

Plan §13: ne prepisivati postojeće validatore — samo prevoditi.
ALIAS import (Faza -1.D — kolizija imena ValidationResult).
"""

from __future__ import annotations

# ALIAS — Faza -1.D
from services.validation.validation_service import (
    ValidationResult as NaimenovanjeValidationResult,
)

from services.agent.validation.finding_model import (
    FindingCode,
    FindingSeverity,
    ValidationFinding,
)

_FIELD_CODE_MAP: dict[str, str] = {
    "tarifni_broj": FindingCode.MISSING_TARIFF,
    "naziv_robe": FindingCode.MISSING_AMOUNT,
    "net_mass_kg": FindingCode.INVALID_WEIGHT,
    "gross_mass_kg": FindingCode.INVALID_WEIGHT,
    "vrednost": FindingCode.MISSING_AMOUNT,
    "zemlja_porijekla": FindingCode.MISSING_ORIGIN,
    "povlastica": FindingCode.UNCONFIRMED_PREFERENCE,
}


def _severity_from_level(level_name: str) -> str:
    level_map = {"CRITICAL": FindingSeverity.BLOCKING, "ERROR": FindingSeverity.BLOCKING, "WARNING": FindingSeverity.WARNING}
    return level_map.get(level_name.upper() if hasattr(level_name, "upper") else str(level_name), FindingSeverity.WARNING)


def adapt_items_validation(
    result: NaimenovanjeValidationResult,
    ordinal: int = 0,
    source: str = "NaimenovanjeValidator",
) -> list[ValidationFinding]:
    """Konvertuj NaimenovanjeValidator.ValidationResult u listu ValidationFinding."""
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
            target="items",
            location=f"naimenovanje {ordinal}" if ordinal > 0 else "naimenovanja",
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
            target="items",
            location=f"naimenovanje {ordinal}" if ordinal > 0 else "naimenovanja",
            message=message,
            evidence={"field": field_name},
            source=source,
            suggested_action=getattr(warning, "suggestion", ""),
        ))

    return findings
