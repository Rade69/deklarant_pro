"""
FakturaController — 3-layer refaktor.

Faza 1-7B prema Codex planu.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject

from core.draft import DeclarationDraft

logger = logging.getLogger("deklarant_pro.faktura.controller")


class FakturaController(QObject):

    def __init__(
        self,
        get_draft_fn: Callable[[], DeclarationDraft],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._get_draft = get_draft_fn

    @property
    def draft(self) -> DeclarationDraft:
        return self._get_draft()

    # ── Validacija i bojenje (Faza 3) ──────────────────────────

    def validate_and_color_rows(self, draft) -> dict:
        """Validiraj sve redove i vrati boje + tooltip.
        """
        from services.faktura.validation_service import ValidationService

        svc = ValidationService()
        lines = getattr(draft, "invoice_lines", []) or []
        color_map = {}
        errors = 0
        warnings = 0

        for idx, line in enumerate(lines):
            try:
                color, tooltip = svc.validate_and_get_color(line)
                color_map[idx] = (color, tooltip)
                # Crvena = #F9E4E3 ili #ffcccc
                if "F9E4E3" in color.upper() or "FFCCCC" in color.upper():
                    errors += 1
                # Žuta = #FFF4D6 ili #fff9c4 ili #ffffcc
                elif "FFF4D6" in color.upper() or "FFF9C4" in color.upper() or "FFFFCC" in color.upper():
                    warnings += 1
            except Exception:
                color_map[idx] = ("#ffffff", "")

        return {
            "validated_count": len(lines),
            "error_count": errors,
            "warning_count": warnings,
            "color_map": color_map,
        }

    # ── Import tok (Faza 4) ──────────────────────────────────

    def prepare_import_plan(self, result, source_path: str = ""):
        """Kreira ImportPlan iz ImportResult-a."""
        from services.import_workflow.adapters import from_import_result
        from services.import_workflow.prepare_service import prepare_import
        candidate = from_import_result(result, source_path)
        return prepare_import([candidate])

    def apply_import_plan(self, draft, plan, decisions):
        """Primijeni ImportPlan na draft."""
        from services.import_workflow.apply_service import apply_import_plan
        return apply_import_plan(draft, plan, decisions)

    def normalize_item_tariffs(self, items: list) -> None:
        """Normalizuj tarifne brojeve na 8/10 cifara.
        Kodovi kraći od 8 cifara OSTAJU nepromijenjeni — mjesto
        nedostajuće cifre se ne smije nagađati (projektno pravilo).
        """
        from importers.invoice_line_utils import normalize_tariff_number
        for item in items:
            code = getattr(item, "tarifni_broj", "") or ""
            if not code:
                continue
            item.tarifni_broj = normalize_tariff_number(code)

    # ── Kreiranje naimenovanja (Faza 5) ───────────────────────

    def create_naimenovanja(self, draft) -> dict:
        """Kreiraj naimenovanja iz invoice_lines."""
        result = {"count": 0, "error": None}
        try:
            from services.naimenovanja.create_naimenovanja_service import CreateNaimenovanjaService
            svc = CreateNaimenovanjaService(draft)
            count = svc.create_smart_group()
            result["count"] = count
            try:
                from services.tariff_facade import TariffFacade
                TariffFacade.get_instance().learn_from_draft(
                    draft.invoice_lines,
                    draft_uid=getattr(draft, "draft_uid", "") or "",
                )
            except Exception as e:
                logger.warning("TariffFacade.learn_from_draft failed: %s", e)
        except Exception as e:
            logger.exception("create_naimenovanja failed")
            result["error"] = str(e)
        return result

    # ── Mase (Faza 6) ────────────────────────────────────────

    def calculate_masses(self, items: list, bruto_kg: float, neto_kg: float):
        """Rasporedi ukupne težine na stavke."""
        from services.faktura.mass_calculator import MassCalculator
        MassCalculator.calculate_masses(items, bruto_kg, neto_kg)

    def accumulate_weights(self, draft, bruto_kg: float, neto_kg: float, invoice_name: str = ""):
        """Akumuliraj težine za fakturu u draft.invoice_weights."""
        if not invoice_name or (bruto_kg <= 0 and neto_kg <= 0):
            return
        from services.faktura.weight_guards import normalize_invoice_key
        key = normalize_invoice_key(invoice_name)
        draft.invoice_weights[key] = (bruto_kg, neto_kg)

    # ── Item edit / undo (Faza 7A) ────────────────────────────

    def bulk_change_tariff(self, draft, rows: list, tariff: str):
        """Bulk izmjena tarifnog broja za selektovane redove.

        Uključuje normalizaciju tarife i mark_dirty.
        """
        from importers.invoice_line_utils import normalize_tariff_number
        normalized = normalize_tariff_number(tariff)
        updated = 0
        for row in rows:
            if 0 <= row < len(draft.invoice_lines):
                old = draft.invoice_lines[row].tarifni_broj
                draft.invoice_lines[row].tarifni_broj = normalized
                if old != normalized:
                    updated += 1
        if updated:
            draft.mark_dirty()
        return updated

    def delete_item(self, draft, row: int) -> bool:
        """Obriši stavku iz drafta (sa mark_dirty)."""
        if 0 <= row < len(draft.invoice_lines):
            del draft.invoice_lines[row]
            draft.mark_dirty()
            return True
        return False

    # ── Partneri (Faza 7B) ─────────────────────────────────────

    def check_partner_consistency(self, exporter: str, importer: str,
                                   expected_exporter: str = "", expected_importer: str = ""):
        """Provjeri konzistentnost partnera — delegira na postojeći View metod."""
        import re

        def _normalize(name: str) -> str:
            name = name.lower().strip()
            name = re.sub(r"[.\-,;:'/\\()]", " ", name)
            name = re.sub(r"\b(doo|d\.o\.o|dd|a\.d|ad|llc|ltd|gmbh|srl)\b", "", name)
            return re.sub(r"\s+", " ", name).strip()

        def similar(a: str, b: str) -> bool:
            na, nb = _normalize(a), _normalize(b)
            if not na or not nb:
                return True
            ta, tb = set(na.split()), set(nb.split())
            if not ta or not tb:
                return True
            return len(ta & tb) / max(len(ta), len(tb)) >= 0.6

        warnings = []
        if expected_exporter and exporter and not similar(exporter, expected_exporter):
            warnings.append(f"Pošiljalac se razlikuje: '{expected_exporter}' vs '{exporter}'")
        if expected_importer and importer and not similar(importer, expected_importer):
            warnings.append(f"Uvoznik se razlikuje: '{expected_importer}' vs '{importer}'")
        return len(warnings) == 0, warnings

    def is_same_invoice(self, last_name: str, current_name: str) -> bool:
        """Da li je isti invoice (REPLACE/EXTEND logika)."""
        a = last_name.replace(" ", "").replace("-", "").lower()
        b = current_name.replace(" ", "").replace("-", "").lower()
        if min(len(a), len(b)) < 5:
            return False
        return a[:min(len(a), len(b))] == b[:min(len(a), len(b))]
