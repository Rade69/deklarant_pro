"""
XML Readiness Service — Faza 6.

Orkestrira sve validatore (Faze 3-5) i XML builder preflight
da bi odgovorio na pitanje: "Da li je deklaracija spremna za ASYCUDA XML?"

Plan §17: jedan autoritativni odgovor. READY / READY_WITH_WARNINGS / BLOCKED.
Koristi draft.revision za invalidaciju zastarjelih readiness rezultata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from services.agent.validation.finding_model import (
    FindingCode,
    FindingSeverity,
    ValidationFinding,
    ValidationSummary,
)

logger = logging.getLogger("deklarant_pro.agent.xml_readiness")


class ReadinessStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


@dataclass
class XmlReadinessResult:
    """Rezultat provjere spremnosti za XML izvoz."""
    status: ReadinessStatus
    draft_revision: int = 0
    summaries: list[ValidationSummary] = field(default_factory=list)
    all_findings: list[ValidationFinding] = field(default_factory=list)
    checks_run: tuple[str, ...] = ()
    checks_skipped: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status in (ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS)

    @property
    def blocking_count(self) -> int:
        return sum(s.blocking_count for s in self.summaries)

    @property
    def warning_count(self) -> int:
        return sum(s.warning_count for s in self.summaries)


def provjeri_spremnost_za_xml(draft) -> XmlReadinessResult:
    """Provjeri sve kapije za ASYCUDA XML izvoz.

    Orkestrira validatore iz Faza 3, 4, 5.
    Ne duplira pravila — samo ih redom poziva i agregira.
    """
    revision = getattr(draft, "revision", 0)
    summaries: list[ValidationSummary] = []
    all_findings: list[ValidationFinding] = []
    checks_run: list[str] = []
    checks_skipped: list[str] = []

    # 1. Faktura validacija (Faza 3)
    try:
        from services.agent.validation.invoice_review_service import provjeri_fakturu
        inv_summary = provjeri_fakturu(draft)
        summaries.append(inv_summary)
        all_findings.extend(inv_summary.findings)
        checks_run.append("invoice_validation")
    except Exception as e:
        _record_failed_check(
            "invoice_validation", e, all_findings, checks_skipped
        )

    # 2. Naimenovanja validacija (Faza 4)
    try:
        from services.agent.validation.items_review_service import provjeri_naimenovanja
        items_summary = provjeri_naimenovanja(draft)
        summaries.append(items_summary)
        all_findings.extend(items_summary.findings)
        checks_run.append("items_validation")
    except Exception as e:
        _record_failed_check(
            "items_validation", e, all_findings, checks_skipped
        )

    # 3. Zaglavlje validacija (Faza 5)
    try:
        from services.agent.validation.header_review_service import provjeri_zaglavlje
        header_summary = provjeri_zaglavlje(draft)
        summaries.append(header_summary)
        all_findings.extend(header_summary.findings)
        checks_run.append("header_validation")
    except Exception as e:
        _record_failed_check(
            "header_validation", e, all_findings, checks_skipped
        )

    # 4. Međutabna usklađenost (Faza 5)
    try:
        from services.agent.validation.header_review_service import provjeri_usklađenost_tabova
        cross_summary = provjeri_usklađenost_tabova(draft)
        summaries.append(cross_summary)
        all_findings.extend(cross_summary.findings)
        checks_run.append("cross_tab")
    except Exception as e:
        _record_failed_check(
            "cross_tab", e, all_findings, checks_skipped
        )

    # 5. XML builder preflight — može li se izgraditi XML?
    try:
        builder_ok = _xml_preflight(draft)
        if not builder_ok:
            all_findings.append(ValidationFinding(
                severity=FindingSeverity.BLOCKING,
                code="XML_PREFLIGHT_BLOCKED",
                target="xml",
                location="xml_export",
                message="XML builder ne može izgraditi dokument",
                source="xml_preflight",
                blocking=True,
            ))
        checks_run.append("xml_preflight")
    except Exception as e:
        _record_failed_check(
            "xml_preflight", e, all_findings, checks_skipped
        )

    # Odredi status
    blocking = sum(1 for f in all_findings if f.blocking)
    warnings = sum(1 for f in all_findings if f.severity == FindingSeverity.WARNING)

    if blocking > 0:
        status = ReadinessStatus.BLOCKED
    elif warnings > 0:
        status = ReadinessStatus.READY_WITH_WARNINGS
    else:
        status = ReadinessStatus.READY

    return XmlReadinessResult(
        status=status,
        draft_revision=revision,
        summaries=summaries,
        all_findings=all_findings,
        checks_run=tuple(checks_run),
        checks_skipped=tuple(checks_skipped),
    )


def _record_failed_check(
    check_name: str,
    error: Exception,
    all_findings: list[ValidationFinding],
    checks_skipped: list[str],
) -> None:
    logger.error("Obavezna XML readiness provjera '%s' nije izvršena: %s", check_name, error)
    checks_skipped.append(check_name)
    all_findings.append(ValidationFinding(
        severity=FindingSeverity.BLOCKING,
        code=FindingCode.REQUIRED_CHECK_FAILED,
        target="xml",
        location=check_name,
        message=f"Obavezna provjera '{check_name}' nije izvršena",
        evidence={"error_type": type(error).__name__},
        source="xml_readiness",
        suggested_action="Otkloni tehničku grešku i ponovi provjeru prije izvoza",
        blocking=True,
    ))


def _xml_preflight(draft) -> bool:
    """Provjeri da li XML builder stvarno može izgraditi dokument.

    Prije popravke ova funkcija je samo provjeravala da li 'items' postoji —
    export_to_xml je bio uvezen ali nikad pozvan, pa je prava greška u
    builderu (npr. loš Rub.31 format) bila prijavljena kao READY. Vidi
    agent_reports/2026-07-27_popravka-wiring-gapova-agent-v2.md.

    AsycudaXMLBuilder.build() poziva _apply_known_tariff_corrections() koja
    MUTIRA draft.items u hodu (ispravlja poznate pogrešne tarifne kodove) —
    zato se builder ovdje nikad ne poziva nad produkcionim draftom, nego nad
    JSON round-trip kopijom (serialize_draft/deserialize_draft). XML se ne
    piše na disk (poziva se samo .build(), ne export_to_xml()).
    """
    try:
        from exporters.asycuda_xml_builder import AsycudaXMLBuilder
        from services.declaration_draft_service import serialize_draft, deserialize_draft

        items = getattr(draft, "items", []) or []
        if not items:
            return False

        draft_copy = deserialize_draft(serialize_draft(draft))
        AsycudaXMLBuilder(draft_copy).build()
        return True
    except ImportError as e:
        logger.error("XML preflight — builder nije dostupan: %s", e)
        return False
    except Exception as e:
        logger.warning(f"XML preflight — builder ne može izgraditi dokument: {e}")
        return False
