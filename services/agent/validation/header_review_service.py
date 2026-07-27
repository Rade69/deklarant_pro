"""
Servis za provjeru Zaglavlja i međutabnu usklađenost (Faza 5).

Plan §13/§16 (v2.1): dva alata — provjeri_zaglavlje i provjeri_usklađenost_tabova.
Oba READ_ONLY.
"""

from __future__ import annotations

import logging
from typing import Optional

from services.agent.validation.finding_model import (
    FindingCode,
    FindingSeverity,
    ValidationFinding,
    ValidationSummary,
)

logger = logging.getLogger("deklarant_pro.agent.header_review")


def provjeri_zaglavlje(draft) -> ValidationSummary:
    """Provjera popunjenosti i ispravnosti Zaglavlja.

    Provjerava obavezna polja: tip deklaracije, izvoznik, primalac,
    deklarant, valuta, uslovi isporuke, mase, Rb.40.
    """
    findings: list[ValidationFinding] = []

    # 1. Tip deklaracije
    if not getattr(draft, "deklaracija_tip", "").strip():
        findings.append(_blocking("deklaracija_tip", "Tip deklaracije (EX/IM) je obavezan", "zaglavlje"))

    # 2. Izvoznik
    if not getattr(draft, "izvoznik_naziv", "").strip():
        findings.append(_blocking("izvoznik_naziv", "Izvoznik je obavezan", "zaglavlje"))

    # 3. Primalac
    if not getattr(draft, "primalac_naziv", "").strip():
        findings.append(_blocking("primalac_naziv", "Primalac je obavezan", "zaglavlje"))

    # 4. Deklarant
    if not getattr(draft, "deklarant_naziv", "").strip():
        findings.append(_blocking("deklarant_naziv", "Deklarant je obavezan", "zaglavlje"))

    # 5. Valuta
    valuta = getattr(draft, "valuta", "")
    if not valuta or not str(valuta).strip():
        findings.append(_warning("valuta", "Valuta nije unesena", "zaglavlje"))

    # 6. Ukupna bruto masa (iz drafta ili invoice_lines)
    total_bruto = _sum_invoice_weights(draft, "bruto_kg")
    zaglavlje_bruto = getattr(draft, "ukupna_bruto_masa", 0.0) or 0.0
    if total_bruto <= 0 and zaglavlje_bruto <= 0:
        findings.append(_warning("bruto_masa", "Ukupna bruto masa nije unesena", "zaglavlje"))

    revision = getattr(draft, "revision", 0)
    summary = ValidationSummary.from_findings("header", findings, draft_revision=revision)
    summary.checks_run = ("tip_deklaracije", "izvoznik", "primalac", "deklarant", "valuta", "bruto_masa")
    return summary


def provjeri_usklađenost_tabova(draft) -> ValidationSummary:
    """Međutabna provjera — Faktura vs Naimenovanja vs Zaglavlje.

    Provjerava:
    - Zbir faktura iznosa = zbir naimenovanja
    - Zbir masa = naimenovanja = zaglavlje
    - Aktivni draft isti u sva tri taba (isti revision)
    """
    findings: list[ValidationFinding] = []

    # 1. Zbir iznosa: faktura vs naimenovanja
    invoice_total = _sum_invoice_amounts(draft)
    items_total = _sum_items_amounts(draft)
    if invoice_total > 0 and items_total > 0 and abs(invoice_total - items_total) > 0.01:
        findings.append(ValidationFinding(
            severity=FindingSeverity.BLOCKING,
            code=FindingCode.CROSS_TAB_MISMATCH,
            target="declaration",
            location="faktura ↔ naimenovanja",
            message=f"Zbir iznosa faktura ({invoice_total:.2f}) ≠ zbir naimenovanja ({items_total:.2f})",
            evidence={"invoice_total": invoice_total, "items_total": items_total},
            source="cross_tab_check",
            blocking=True,
        ))

    # 2. Zbir bruto masa
    invoice_bruto = _sum_invoice_weights(draft, "bruto_kg")
    items_bruto = _sum_items_mass(draft, "gross_mass_kg")
    if invoice_bruto > 0 and items_bruto > 0 and abs(invoice_bruto - items_bruto) > 1.0:
        findings.append(ValidationFinding(
            severity=FindingSeverity.WARNING,
            code=FindingCode.WEIGHT_TOTAL_MISMATCH,
            target="declaration",
            location="faktura ↔ naimenovanja",
            message=f"Bruto masa faktura ({invoice_bruto:.1f}) ≠ naimenovanja ({items_bruto:.1f})",
            evidence={"invoice_bruto": invoice_bruto, "items_bruto": items_bruto},
            source="cross_tab_check",
        ))

    # 3. Miješanje draft.items i draft.invoice_lines
    inv_count = len(getattr(draft, "invoice_lines", []) or [])
    item_count = len(getattr(draft, "items", []) or [])
    if item_count == 0 and inv_count > 0:
        findings.append(ValidationFinding(
            severity=FindingSeverity.WARNING,
            code=FindingCode.ITEM_GROUPING_MISMATCH,
            target="declaration",
            location="naimenovanja",
            message="Naimenovanja nisu kreirana — pokrenite 'Kreiraj naimenovanja'",
            source="cross_tab_check",
            suggested_action="Kreiraj naimenovanja",
        ))

    revision = getattr(draft, "revision", 0)
    summary = ValidationSummary.from_findings("declaration", findings, draft_revision=revision)
    summary.checks_run = ("invoice_items_total", "weight_cross_tab", "items_exist")
    return summary


def _blocking(field: str, message: str, location: str) -> ValidationFinding:
    return ValidationFinding(
        severity=FindingSeverity.BLOCKING,
        code=FindingCode.HEADER_REQUIRED_FIELD,
        target="header",
        location=location,
        message=message,
        evidence={"field": field},
        source="header_check",
        blocking=True,
    )


def _warning(field: str, message: str, location: str) -> ValidationFinding:
    return ValidationFinding(
        severity=FindingSeverity.WARNING,
        code=FindingCode.HEADER_REQUIRED_FIELD,
        target="header",
        location=location,
        message=message,
        evidence={"field": field},
        source="header_check",
    )


def _sum_invoice_amounts(draft) -> float:
    lines = getattr(draft, "invoice_lines", []) or []
    return sum(getattr(line, "iznos", 0.0) or 0.0 for line in lines)


def _sum_items_amounts(draft) -> float:
    items = getattr(draft, "items", []) or []
    return sum(getattr(item, "statistical_value", 0.0) or 0.0 for item in items)


def _sum_invoice_weights(draft, field: str) -> float:
    lines = getattr(draft, "invoice_lines", []) or []
    return sum(getattr(line, field, 0.0) or 0.0 for line in lines)


def _sum_items_mass(draft, field: str) -> float:
    items = getattr(draft, "items", []) or []
    return sum(getattr(item, field, 0.0) or 0.0 for item in items)
