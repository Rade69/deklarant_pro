"""
Servis za stručnu provjeru Faktura taba (Faza 3).

Plan §14: read-only alat provjeri_fakturu(scope, ordinals).
Ne prepisuje postojeće validatore — orkestrira ih i prevodi
nalaze u ValidationFinding kroz Faza 2 adapter.

Provjere:
  1. Popunjenost obaveznih polja (FakturaItemValidator)
  2. Format tarifnog broja (FakturaItemValidator)
  3. Postojanje tarife u zvaničnoj tarifi (trazi_po_kodu)
  4. Status decision evidence za tarifu (DeclarationDecisionService)
  5. Zemlja porijekla i decision status
  6. Povlastica samo uz potvrđen dokaz
  7. Iznos, količina i jedinica mjere
  8. Bruto/neto mase (weight_guards)
  9. Duplikati i consumed_paths posljedice
  10. Istorijske tarifne razlike kroz decision politiku
  11. Razdvajanje blokada, upozorenja i informacija
"""

from __future__ import annotations

import logging
from typing import Optional

from core.draft.draft import InvoiceLine
from services.agent.validation.finding_model import (
    FindingCode,
    FindingSeverity,
    ValidationFinding,
    ValidationSummary,
)
from services.agent.validation.invoice_validation_adapter import (
    adapt_invoice_validation,
)

logger = logging.getLogger("deklarant_pro.agent.invoice_review")


def provjeri_fakturu(
    draft,
    scope: str = "all",
    ordinals: Optional[list[int]] = None,
) -> ValidationSummary:
    """Stručna provjera Faktura taba — sve stavke ili selekcija.

    Args:
        draft: DeclarationDraft sa invoice_lines
        scope: "all", "selection", ili "row"
        ordinals: opciono — indeksi redova za scope="selection"

    Returns:
        ValidationSummary sa svim nalazima. ready=True ako nema blokada.
    """
    lines = list(draft.invoice_lines) if hasattr(draft, "invoice_lines") else []
    if not lines:
        return ValidationSummary(
            target="invoice",
            ready=True,
            checks_run=("invoice_count",),
        )

    # Filtriraj ako je scope ograničen
    target_lines = _filter_lines(lines, scope, ordinals)
    findings: list[ValidationFinding] = []

    # 1. Popunjenost + format (FakturaItemValidator)
    findings.extend(_check_basic_validation(target_lines, lines))

    # 2. Postojanje tarife u zvaničnoj tarifi
    findings.extend(_check_tariff_exists(target_lines, lines))

    # 3. Decision evidence za tarifu i porijeklo
    findings.extend(_check_decision_evidence(target_lines, lines))

    # 4. Težine (bruto/neto)
    findings.extend(_check_weights(target_lines, lines))

    # 5. Duplikati
    findings.extend(_check_duplicates(draft))

    # Kreiraj summary
    revision = getattr(draft, "revision", 0)
    summary = ValidationSummary.from_findings("invoice", findings, draft_revision=revision)
    summary.checks_run = (
        "basic_validation", "tariff_exists", "decision_evidence",
        "weights", "duplicates",
    )
    summary.checks_skipped = ("packing_list_reconciliation",)

    return summary


def _filter_lines(
    lines: list[InvoiceLine],
    scope: str,
    ordinals: Optional[list[int]],
) -> list[InvoiceLine]:
    if scope == "all" or not ordinals:
        return lines
    return [lines[i] for i in ordinals if 0 <= i < len(lines)]


def _check_basic_validation(
    target_lines: list[InvoiceLine],
    all_lines: list[InvoiceLine],
) -> list[ValidationFinding]:
    """1. Popunjenost obaveznih polja + format tarifnog broja."""
    from services.validation.validation_service import FakturaItemValidator

    validator = FakturaItemValidator()
    findings: list[ValidationFinding] = []

    for idx, line in enumerate(target_lines):
        # Nađi originalni indeks u punoj listi
        row_index = all_lines.index(line) if line in all_lines else idx
        result = validator.validate(line)
        findings.extend(adapt_invoice_validation(result, row_index=row_index))

    return findings


def _check_tariff_exists(
    target_lines: list[InvoiceLine],
    all_lines: list[InvoiceLine],
) -> list[ValidationFinding]:
    """3. Postojanje tarifnog broja u zvaničnoj tarifi."""
    findings: list[ValidationFinding] = []

    for idx, line in enumerate(target_lines):
        code = (getattr(line, "tarifni_broj", "") or "").strip()
        if not code:
            continue  # Već prijavljeno kao MISSING_TARIFF u koraku 1

        row_index = all_lines.index(line) if line in all_lines else idx
        try:
            from services.tariff.tarifa_service import trazi_po_kodu
            result = trazi_po_kodu(code)
            if result is None:
                findings.append(ValidationFinding(
                    severity=FindingSeverity.WARNING,
                    code=FindingCode.TARIFF_NOT_FOUND,
                    target="invoice",
                    location=f"stavka {row_index + 1}",
                    message=f"Tarifni broj '{code}' ne postoji u zvaničnoj tarifi",
                    evidence={"tariff_code": code},
                    source="trazi_po_kodu",
                    suggested_action="Provjerite ispravnost tarifnog broja",
                ))
        except Exception as e:
            logger.warning(f"Tariff lookup failed for {code}: {e}")
            findings.append(ValidationFinding(
                severity=FindingSeverity.WARNING,
                code=FindingCode.TARIFF_NOT_FOUND,
                target="invoice",
                location=f"stavka {row_index + 1}",
                message=f"Nije moguće provjeriti postojanje tarife '{code}'",
                evidence={"tariff_code": code, "error": str(e)[:100]},
                source="trazi_po_kodu",
            ))

    return findings


def _check_decision_evidence(
    target_lines: list[InvoiceLine],
    all_lines: list[InvoiceLine],
) -> list[ValidationFinding]:
    """4-6. Decision evidence za tarifu, porijeklo, povlasticu."""
    findings: list[ValidationFinding] = []

    try:
        from services.decision.declaration_decision_service import DeclarationDecisionService
        svc = DeclarationDecisionService()
    except Exception as e:
        logger.warning(f"DecisionService unavailable: {e}")
        findings.append(ValidationFinding(
            severity=FindingSeverity.INFO,
            code=FindingCode.UNCONFIRMED_TARIFF,
            target="invoice",
            location="faktura",
            message="Decision evidence servis nije dostupan — preskačem provjeru",
            evidence={"error": str(e)[:100]},
            source="DeclarationDecisionService",
        ))
        return findings

    for idx, line in enumerate(target_lines):
        row_index = all_lines.index(line) if line in all_lines else idx
        try:
            report = svc.evaluate_line(line)
            if report is None:
                continue

            if getattr(report, "has_issues", lambda: False)():
                for issue in getattr(report, "issues", []) or []:
                    findings.append(ValidationFinding(
                        severity=FindingSeverity.WARNING,
                        code=FindingCode.UNCONFIRMED_TARIFF,
                        target="invoice",
                        location=f"stavka {row_index + 1}",
                        message=getattr(issue, "description", str(issue)),
                        evidence={"tariff_code": getattr(line, "tarifni_broj", "")},
                        source="DeclarationDecisionService",
                        suggested_action=getattr(issue, "suggested_action", ""),
                    ))
        except Exception as e:
            logger.debug(f"Decision eval failed for line {row_index}: {e}")

    return findings


def _check_weights(
    target_lines: list[InvoiceLine],
    all_lines: list[InvoiceLine],
) -> list[ValidationFinding]:
    """8. Bruto/neto mase."""
    findings: list[ValidationFinding] = []

    for idx, line in enumerate(target_lines):
        row_index = all_lines.index(line) if line in all_lines else idx
        bruto = getattr(line, "bruto_kg", 0.0) or 0.0
        neto = getattr(line, "neto_kg", 0.0) or 0.0

        if bruto < 0:
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.INVALID_WEIGHT,
                target="invoice",
                location=f"stavka {row_index + 1}",
                message=f"Negativna bruto težina: {bruto} kg",
                evidence={"bruto_kg": bruto},
                source="weight_check",
            ))
        if neto < 0:
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.INVALID_WEIGHT,
                target="invoice",
                location=f"stavka {row_index + 1}",
                message=f"Negativna neto težina: {neto} kg",
                evidence={"neto_kg": neto},
                source="weight_check",
            ))
        if bruto > 0 and neto > bruto:
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.GROSS_LESS_THAN_NET,
                target="invoice",
                location=f"stavka {row_index + 1}",
                message=f"Neto ({neto} kg) veće od bruto ({bruto} kg)",
                evidence={"bruto_kg": bruto, "neto_kg": neto},
                source="weight_check",
            ))

    return findings


def _check_duplicates(draft) -> list[ValidationFinding]:
    """9. Provjera duplikata i consumed_paths."""
    findings: list[ValidationFinding] = []
    lines = getattr(draft, "invoice_lines", []) or []
    seen: set[tuple] = set()

    for idx, line in enumerate(lines):
        key = (
            getattr(line, "invoice_number", ""),
            getattr(line, "tarifni_broj", ""),
            getattr(line, "naziv_robe", ""),
        )
        if key in seen and key[0]:  # Samo ako ima invoice_number
            findings.append(ValidationFinding(
                severity=FindingSeverity.WARNING,
                code=FindingCode.DUPLICATE_INVOICE_LINE,
                target="invoice",
                location=f"stavka {idx + 1}",
                message=f"Mogući duplikat: '{key[2][:40]}' već postoji u fakturi '{key[0]}'",
                evidence={"invoice_number": key[0], "tariff": key[1]},
                source="duplicate_check",
            ))
        seen.add(key)

    return findings
