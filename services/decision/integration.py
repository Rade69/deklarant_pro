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

    Returns:
        Broj azuriranih linija
    """
    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=supplier,
        action_type=action_type,
    )
    updated = 0
    errors = 0

    for line in lines:
        if not line.tarifni_broj:
            continue

        auth = Authorization(action_type=action_type, user_identity="deklarant")
        try:
            state = svc.evaluate_line(line, ctx, fields=[DecisionField.TARIFF])
            applied = False
            for c in state.tariff.candidates:
                if c.value == line.tarifni_broj:
                    line.decision_state = state
                    svc.apply_candidate(line, DecisionField.TARIFF, c.candidate_id, auth)
                    applied = True
                    break

            if not applied:
                svc.confirm_manual_value(line, DecisionField.TARIFF, line.tarifni_broj, auth)

            updated += 1
        except Exception:
            errors += 1
            logger.warning(
                "Decision sync autofill: linija %d nije sinhronizovana — %s",
                line.line_no,
                line.tarifni_broj or "(bez tarife)",
                exc_info=True,
            )

    if errors:
        logger.warning(
            "Decision sync autofill: %d/%d linija nije sinhronizovano",
            errors, len(lines),
        )
    elif updated:
        logger.debug("Decision sync autofill: %d linija azurirano", updated)

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

    Returns:
        True ako je sinhronizacija uspjela
    """
    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=line.exporter.name if line.exporter else "",
        invoice_number=invoice_number,
        action_type=action_type,
    )
    auth = Authorization(action_type=action_type, user_identity="deklarant")

    try:
        if preference_code:
            svc.confirm_manual_value(line, DecisionField.PREFERENCE, preference_code, auth)
            if eur1_number:
                line.eur1_number = eur1_number
        return True
    except Exception:
        logger.warning(
            "Decision sync preference: linija %d, pref=%s — nije sinhronizovano",
            line.line_no, preference_code, exc_info=True,
        )
        return False


def sync_decision_state_after_manual_edit(
    line: "InvoiceLine",
    field: DecisionField,
    value: str,
    user_identity: str = "deklarant",
) -> bool:
    """
    Sinhronizuj decision_state nakon rucne izmjene polja u tabeli.

    Poziva confirm_manual_value() za sintronizaciju decision_state-a
    sa rucno unesenom vrijednoscu.
    """
    svc = _make_service()
    auth = Authorization(action_type="manual_edit", user_identity=user_identity)

    try:
        svc.confirm_manual_value(line, field, value, auth)
        return True
    except Exception:
        logger.warning(
            "Decision sync manual edit: linija %d, field=%s, value=%s — nije sinhronizovano",
            line.line_no, field.value, value, exc_info=True,
        )
        return False


def sync_all_lines_after_draft_restore(
    lines: list["InvoiceLine"],
    supplier: str = "",
) -> int:
    """
    Sinhronizuj sve linije nakon restore-a drafta.
    Kreira decision_state za svaku liniju na osnovu postojecih vrijednosti.
    """
    svc = _make_service()
    ctx = PolicyContext(
        normalized_exporter=supplier,
        action_type="draft_restore",
    )
    auth = Authorization(action_type="draft_restore", user_identity="deklarant")
    updated = 0

    for line in lines:
        try:
            state = svc.evaluate_line(line, ctx)
            line.decision_state = state

            # Potvrdi postojece vrijednosti kao primijenjene
            if line.tarifni_broj:
                svc.confirm_manual_value(line, DecisionField.TARIFF, line.tarifni_broj, auth)
            if line.zemlja_porijekla:
                svc.confirm_manual_value(line, DecisionField.ORIGIN_COUNTRY, line.zemlja_porijekla, auth)
            if line.povlastica:
                svc.confirm_manual_value(line, DecisionField.PREFERENCE, line.povlastica, auth)

            updated += 1
        except Exception:
            logger.warning(
                "Decision sync draft restore: linija %d — nije sinhronizovano",
                line.line_no, exc_info=True,
            )

    logger.debug("Decision sync draft restore: %d/%d linija azurirano", updated, len(lines))
    return updated


def evaluate_line_for_display(line: "InvoiceLine", supplier: str = "") -> dict:
    """
    Evaluacija jedne linije za UI prikaz — vraca dict sa statusima
    pogodnim za prikaz u tabeli (badge boje, labele).

    Returns:
        Dict sa kljucevima: tariff_status, tariff_label, tariff_color_fg,
        tariff_color_bg, tariff_source, tariff_score, origin_status,
        origin_conflict, preference_status, preference_doc_code
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
        logger.debug("Decision display eval: linija %d — nije evaluirana", line.line_no, exc_info=True)
        return {}

    result = {}

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

    fd = state.origin_country
    result["origin_status"] = fd.status.value
    if fd.status == DecisionStatus.CONFLICT:
        result["origin_conflict"] = True

    fd = state.preference
    result["preference_status"] = fd.status.value
    if fd.candidates and fd.candidates[0].evidence:
        ev = fd.candidates[0].evidence
        result["preference_doc_code"] = ev.data.get("doc_code", "")

    return result