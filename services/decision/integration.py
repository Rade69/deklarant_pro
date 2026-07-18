"""
Decision Service Integration — pomocne funkcije za migraciju GUI-ja.

Obezbedjuje sigurnu integraciju DeclarationDecisionService u postojece
GUI tokove (Faktura tab, Agent pipeline, dijalozi) BEZ uklanjanja
postojeceg koda.

Faza 4 migracije — agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.decision.decision_model import DecisionField, DecisionStatus
from services.decision.declaration_decision_service import (
    Authorization,
    DeclarationDecisionService,
)
from services.decision.decision_policy import PolicyContext

if TYPE_CHECKING:
    from core.draft.draft import InvoiceLine

logger = logging.getLogger("deklarant_pro.decision_integration")


def _make_service() -> DeclarationDecisionService:
    return DeclarationDecisionService()


def sync_decision_state_after_autofill(
    lines: list["InvoiceLine"],
    supplier: str = "",
    action_type: str = "auto_fill_clicked",
) -> int:
    """
    Sinhronizuj decision_state za sve InvoiceLine nakon auto-popune.

    Poziva se nakon TariffMappingService.auto_populate_tariffs() ili
    AutoFillService.fill_tariff_numbers() da bi decision_state odrazavao
    novo stanje tarifnih brojeva.

    Returns:
        Broj azuriranih linija
    """
    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=supplier,
        action_type=action_type,
    )
    updated = 0

    for line in lines:
        # Ako linija ima tarifni_broj, potvrdi ga kao primijenjen
        if line.tarifni_broj:
            auth = Authorization(
                action_type=action_type,
                user_identity="deklarant",
            )
            try:
                # Prvo evaluiraj da dobijemo kandidate
                state = svc.evaluate_line(line, ctx, fields=[DecisionField.TARIFF])

                # Ako ima kandidata koji odgovara trenutnoj tarifi, primijeni ga
                applied = False
                for c in state.tariff.candidates:
                    if c.value == line.tarifni_broj:
                        line.decision_state = state
                        svc.apply_candidate(line, DecisionField.TARIFF, c.candidate_id, auth)
                        applied = True
                        break

                if not applied:
                    # Nema matching kandidata — potvrdi rucno
                    svc.confirm_manual_value(line, DecisionField.TARIFF, line.tarifni_broj, auth)

                updated += 1
            except Exception as e:
                logger.debug("Decision sync za liniju %d nije uspio: %s", line.line_no, e)
                continue

    return updated


def sync_decision_state_after_preference(
    line: "InvoiceLine",
    preference_code: str,
    eur1_number: str = "",
    invoice_number: str = "",
    action_type: str = "dialog_confirmed",
) -> bool:
    """
    Sinhronizuj decision_state nakon EUR.1/PE2 dijaloga.

    Poziva se nakon sto je deklarant potvrdio povlasticu kroz
    EUR.1 ili PE2 dijalog.

    Returns:
        True ako je sinhronizacija uspjela
    """
    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=line.exporter.name if line.exporter else "",
        invoice_number=invoice_number,
        action_type=action_type,
    )
    auth = Authorization(
        action_type=action_type,
        user_identity="deklarant",
    )

    try:
        if preference_code:
            svc.confirm_manual_value(line, DecisionField.PREFERENCE, preference_code, auth)

            # Ako ima EUR.1 broj, azuriraj ga
            if eur1_number:
                line.eur1_number = eur1_number

        return True
    except Exception as e:
        logger.debug("Decision sync za povlasticu nije uspio: %s", e)
        return False


def evaluate_line_for_display(line: "InvoiceLine", supplier: str = "") -> dict:
    """
    Evaluacija jedne linije za UI prikaz — vraca dict sa statusima
    pogodnim za prikaz u tabeli (badge boje, labele).

    Returns:
        Dict sa kljucevima: tariff_status, tariff_label, tariff_color,
        origin_status, origin_label, preference_status, preference_label
    """
    from core.decision.evidence import evidence_badge_colors, tariff_confidence_label

    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=supplier or (line.exporter.name if line.exporter else ""),
        action_type="preview",
    )

    try:
        state = svc.evaluate_line(line, ctx)
    except Exception:
        return {}

    result = {}

    # Tarifa
    fd = state.tariff
    result["tariff_status"] = fd.status.value
    if fd.candidates and fd.candidates[0].evidence:
        ev = fd.candidates[0].evidence
        result["tariff_label"] = tariff_confidence_label(ev)
        fg, bg = evidence_badge_colors(ev)
        result["tariff_color_fg"] = fg
        result["tariff_color_bg"] = bg
        result["tariff_source"] = ev.source.value
        result["tariff_score"] = ev.score

    # Porijeklo
    fd = state.origin_country
    result["origin_status"] = fd.status.value
    if fd.status == DecisionStatus.CONFLICT:
        result["origin_conflict"] = True

    # Povlastica
    fd = state.preference
    result["preference_status"] = fd.status.value
    if fd.candidates and fd.candidates[0].evidence:
        ev = fd.candidates[0].evidence
        result["preference_doc_code"] = ev.data.get("doc_code", "")

    return result