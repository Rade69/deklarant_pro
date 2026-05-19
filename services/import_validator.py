"""
ImportValidator — zajednički validator za parser rezultate.

Koristi se u oba moda:
  - Manuelni import (faktura_view._import_multiple_files)
  - Agentski mod (import_pipeline_service)

Razlika od poslovne validacije (_validiraj_prije_uvoza):
  - Ovdje se provjeravaju fizičke ispravnosti parsiranog rezultata
  - Nema DB poziva, nema UI zavisnosti
  - Rezultat je strukturiran za prikaz u oba moda
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.validator")


@dataclass
class ParserValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    filename: str = ""

    def summary_line(self) -> str:
        if not self.ok:
            return f"❌ {self.filename}: {'; '.join(self.errors[:2])}"
        if self.warnings:
            return f"⚠️ {self.filename}: {len(self.warnings)} upozorenja"
        return f"✅ {self.filename}: OK"

    def has_issues(self) -> bool:
        return not self.ok or bool(self.warnings)


def validate_import_result(
    result: ImportResult,
    filename: str = "",
) -> ParserValidationResult:
    """
    Poziva result.validate() i pakuje u ParserValidationResult.

    Args:
        result:   ImportResult koji je vratio parser
        filename: Ime fajla (za prikaz u porukama)

    Returns:
        ParserValidationResult sa ok, errors, warnings
    """
    ok, errors, warnings = result.validate()

    if errors:
        logger.warning(
            "Parser validacija NIJE uspješna za '%s': %s",
            filename,
            "; ".join(errors),
        )
    elif warnings:
        logger.info(
            "Parser validacija OK sa upozorenjima za '%s': %s",
            filename,
            "; ".join(warnings),
        )
    else:
        logger.debug("Parser validacija OK: '%s' — %d stavki", filename, len(result.items))

    return ParserValidationResult(
        ok=ok,
        errors=errors,
        warnings=warnings,
        filename=filename,
    )


def validate_batch(
    results: list[tuple[ImportResult, str]],
) -> list[ParserValidationResult]:
    """
    Validira listu (ImportResult, filename) parova.

    Returns:
        Lista ParserValidationResult, jedan po fajlu.
    """
    return [validate_import_result(r, fn) for r, fn in results]


def format_validation_summary(vr_list: list[ParserValidationResult]) -> str:
    """
    Formira sažetak za prikaz korisniku u QMessageBox ili chat panelu.
    """
    failed = [v for v in vr_list if not v.ok]
    warned = [v for v in vr_list if v.ok and v.warnings]

    parts: list[str] = []

    if failed:
        parts.append(f"❌ {len(failed)} fajl(a) nije uspješno parsiran:")
        for v in failed:
            for e in v.errors:
                parts.append(f"  • {v.filename}: {e}")

    if warned:
        parts.append(f"⚠️ {len(warned)} fajl(a) sa upozorenjima:")
        for v in warned:
            for w in v.warnings[:3]:
                parts.append(f"  • {v.filename}: {w}")
            if len(v.warnings) > 3:
                parts.append(f"  • {v.filename}: ... i još {len(v.warnings) - 3}")

    return "\n".join(parts) if parts else ""
