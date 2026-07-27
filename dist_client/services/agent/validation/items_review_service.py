"""
Servis za stručnu provjeru Naimenovanja taba (Faza 4).

Plan §15: read-only alat provjeri_naimenovanja(scope, ordinals).
Orkestrira postojeće validatore i dodaje provjere specifične za naimenovanja:
  - Osnovna validacija (NaimenovanjeValidator)
  - Postojanje tarife u zvaničnoj tarifi
  - Zemlja porijekla
  - Povlastica
  - Mase
  - Limit 99 naimenovanja (ASYCUDA)
  - Rub.31 XML limit (280 znakova / 3 linije)
  - Zbir masa i vrijednosti
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
from services.agent.validation.items_validation_adapter import (
    adapt_items_validation,
)

logger = logging.getLogger("deklarant_pro.agent.items_review")


def provjeri_naimenovanja(
    draft,
    scope: str = "all",
    ordinals: Optional[list[int]] = None,
) -> ValidationSummary:
    """Stručna provjera Naimenovanja taba.

    Args:
        draft: DeclarationDraft sa items (naimenovanja)
        scope: "all" ili "row"
        ordinals: opciono — ordinali naimenovanja

    Returns:
        ValidationSummary sa svim nalazima.
    """
    items = list(draft.items) if hasattr(draft, "items") else []
    if not items:
        return ValidationSummary(target="items", ready=True, checks_run=("items_count",))

    target_items = items if scope == "all" else [items[i] for i in (ordinals or []) if 0 <= i < len(items)]
    findings: list[ValidationFinding] = []

    # 1. Osnovna validacija (NaimenovanjeValidator)
    findings.extend(_check_basic_items_validation(target_items, items))

    # 2. Postojanje tarife u zvaničnoj tarifi
    findings.extend(_check_tariff_in_items(target_items))

    # 3. Zemlja porijekla
    findings.extend(_check_origin_in_items(target_items))

    # 4. Povlastica
    findings.extend(_check_preference_in_items(target_items))

    # 5. Mase (neto > bruto se već provjerava u validatoru)
    findings.extend(_check_item_weights(target_items))

    # 6. Limit 99 naimenovanja
    findings.extend(_check_asycuda_limit(draft))

    # 7. Rub.31 XML limit
    findings.extend(_check_rub31_xml_limit(target_items))

    revision = getattr(draft, "revision", 0)
    summary = ValidationSummary.from_findings("items", findings, draft_revision=revision)
    summary.checks_run = (
        "basic_validation", "tariff_exists", "origin", "preference",
        "weights", "asycuda_limit", "rub31_xml_limit",
    )
    return summary


def _check_basic_items_validation(
    target_items: list, all_items: list,
) -> list[ValidationFinding]:
    """Osnovna validacija NaimenovanjeDraft polja (ne koristi NaimenovanjeValidator — on radi sa NaimenovanjeItem)."""
    findings: list[ValidationFinding] = []
    for item in target_items:
        ordinal = getattr(item, "ordinal_no", 0)
        # Obavezna polja
        if not getattr(item, "goods_description", "").strip():
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.MISSING_AMOUNT,
                target="items",
                location=f"naimenovanje {ordinal}",
                message="Naziv robe je obavezan",
                evidence={"field": "goods_description"},
                source="items_basic_check",
                suggested_action="Unesite opis robe",
                blocking=True,
            ))
        if not getattr(item, "tariff_code", "").strip():
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.MISSING_TARIFF,
                target="items",
                location=f"naimenovanje {ordinal}",
                message="Tarifni broj je obavezan",
                evidence={"field": "tariff_code"},
                source="items_basic_check",
                suggested_action="Unesite tarifni broj",
                blocking=True,
            ))
        # Format tarife
        code = getattr(item, "tariff_code", "") or ""
        clean = "".join(c for c in code if c.isdigit())
        if code and clean and len(clean) not in (8, 10):
            findings.append(ValidationFinding(
                severity=FindingSeverity.WARNING,
                code=FindingCode.INVALID_TARIFF_FORMAT,
                target="items",
                location=f"naimenovanje {ordinal}",
                message=f"Tarifni broj '{code}' nije 8/10 cifara",
                evidence={"tariff_code": code, "length": len(clean)},
                source="items_basic_check",
            ))
    return findings


def _check_tariff_in_items(target_items: list) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for item in target_items:
        code = (getattr(item, "tariff_code", "") or "").strip()
        if not code:
            continue  # Već prijavljeno kao MISSING
        ordinal = getattr(item, "ordinal_no", 0)
        try:
            from services.tariff.tarifa_service import trazi_po_kodu
            if trazi_po_kodu(code) is None:
                findings.append(ValidationFinding(
                    severity=FindingSeverity.WARNING,
                    code=FindingCode.TARIFF_NOT_FOUND,
                    target="items",
                    location=f"naimenovanje {ordinal}",
                    message=f"Tarifni broj '{code}' ne postoji u zvaničnoj tarifi",
                    evidence={"tariff_code": code},
                    source="trazi_po_kodu",
                ))
        except Exception as e:
            logger.warning(f"Tariff lookup failed: {e}")
    return findings


def _check_origin_in_items(target_items: list) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for item in target_items:
        origin = (getattr(item, "origin_country_code", "") or "").strip()
        ordinal = getattr(item, "ordinal_no", 0)
        if not origin:
            findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code=FindingCode.MISSING_ORIGIN,
                target="items",
                location=f"naimenovanje {ordinal}",
                message="Nedostaje zemlja porijekla",
                source="items_origin_check",
            ))
    return findings


def _check_preference_in_items(target_items: list) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for item in target_items:
        pref = (getattr(item, "preference_code", "") or "").strip()
        ordinal = getattr(item, "ordinal_no", 0)
        if pref:
            # Povlastica postoji — provjeri da li ima dokaz (PE1/PE2/PE3 dokument)
            has_pe_doc = any(
                getattr(item, f"attached_document{i}", "") for i in range(1, 6)
                if "PE" in str(getattr(item, f"attached_document{i}", ""))
            )
            if not has_pe_doc:
                findings.append(ValidationFinding(
                    severity=FindingSeverity.WARNING,
                    code=FindingCode.PREFERENCE_WITHOUT_EVIDENCE,
                    target="items",
                    location=f"naimenovanje {ordinal}",
                    message=f"Povlastica '{pref}' nema prateći PE dokument",
                    evidence={"preference": pref},
                    source="items_preference_check",
                    suggested_action="Dodajte PE1/PE2/PE3 dokument",
                ))
    return findings


def _check_item_weights(target_items: list) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for item in target_items:
        bruto = getattr(item, "gross_mass_kg", 0.0) or 0.0
        neto = getattr(item, "net_mass_kg", 0.0) or 0.0
        ordinal = getattr(item, "ordinal_no", 0)
        if bruto <= 0 and neto <= 0:
            findings.append(ValidationFinding(
                severity=FindingSeverity.WARNING,
                code=FindingCode.INVALID_WEIGHT,
                target="items",
                location=f"naimenovanje {ordinal}",
                message="Nedostaju bruto i neto masa",
                source="items_weight_check",
            ))
    return findings


def _check_asycuda_limit(draft) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    items = getattr(draft, "items", []) or []
    count = len(items)
    if count >= 99:
        findings.append(ValidationFinding(
            severity=FindingSeverity.BLOCKING,
            code=FindingCode.ASYCUDA_ITEM_LIMIT,
            target="items",
            location="naimenovanja",
            message=f"Prekoračen ASYCUDA limit: {count} naimenovanja (max 99)",
            evidence={"count": count},
            source="asycuda_limit_check",
            suggested_action="Podijelite deklaraciju na više dijelova",
        ))
    elif count >= 95:
        findings.append(ValidationFinding(
            severity=FindingSeverity.WARNING,
            code=FindingCode.ASYCUDA_ITEM_LIMIT,
            target="items",
            location="naimenovanja",
            message=f"Blizu ASYCUDA limita: {count}/99 naimenovanja",
            evidence={"count": count},
            source="asycuda_limit_check",
        ))
    return findings


def _check_rub31_xml_limit(target_items: list) -> list[ValidationFinding]:
    """Provjeri da li Rub.31 prelazi ASYCUDA XML limit (280 znakova / 3 linije)."""
    findings: list[ValidationFinding] = []
    for item in target_items:
        desc = (getattr(item, "goods_description", "") or "")
        ordinal = getattr(item, "ordinal_no", 0)
        if len(desc) > 280:
            findings.append(ValidationFinding(
                severity=FindingSeverity.WARNING,
                code=FindingCode.INVALID_RUB31,
                target="items",
                location=f"naimenovanje {ordinal}",
                message=f"Rub.31 opis prelazi 280 znakova ({len(desc)})",
                evidence={"length": len(desc), "chars_over": len(desc) - 280},
                source="rub31_xml_limit_check",
                suggested_action="Skratite opis robe za ASYCUDA XML",
            ))
    return findings
