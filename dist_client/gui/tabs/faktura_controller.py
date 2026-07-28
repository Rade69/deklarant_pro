"""
FakturaController — prazna infrastruktura bez promjene ponašanja.

Faza 1 prema Codex planu §8: composition root.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject

from core.draft import DeclarationDraft
from services.faktura.naimenovanja_service import NaimenovanjaService

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

    def validate_and_color_rows(self, view, draft) -> ValidationPassResult:
        """Validiraj sve redove i vrati boje + tooltip.
        
        Koristi postojeći FakturaValidationService.
        """
        from services.faktura.validation_service import FakturaValidationService
        from services.faktura.models import ValidationPassResult
        
        svc = FakturaValidationService()
        lines = getattr(draft, "invoice_lines", []) or []
        color_map = {}
        errors = 0
        warnings = 0
        
        for idx, line in enumerate(lines):
            try:
                color, tooltip = svc.validate_and_get_color(line)
                color_map[idx] = (color, tooltip)
                if "#ff" in color.lower() or "#F9" in color.upper():  # crvena
                    errors += 1
                elif "#ff" in color.lower() or "#FF" in color.upper():  # žuta
                    warnings += 1
            except Exception:
                color_map[idx] = ("#ffffff", "")
        
        return ValidationPassResult(
            validated_count=len(lines),
            error_count=errors,
            warning_count=warnings,
            color_map=color_map,
        )

    # ── Import tok (Faza 4) ──────────────────────────────────

    def prepare_import_plan(self, draft, result, source_path: str = ""):
        """Kreira ImportPlan iz ImportResult-a."""
        from services.import_workflow.adapters import from_import_result
        from services.import_workflow.prepare_service import prepare_import
        candidate = from_import_result(result, source_path)
        return prepare_import([candidate])

    def apply_import_plan(self, draft, plan, decisions):
        """Primijeni ImportPlan na draft."""
        from services.import_workflow.apply_service import apply_import_plan
        return apply_import_plan(draft, plan, decisions)

    # ── Kreiranje naimenovanja (Faza 5) ───────────────────────

    def create_naimenovanja(self, draft) -> dict:
        """Kreiraj naimenovanja iz invoice_lines."""
        from services.create_naimenovanja_service import CreateNaimenovanjaService
        svc = CreateNaimenovanjaService(draft)
        count = svc.create_smart_group()
        result = {"count": count}
        try:
            from services.tariff_facade import TariffFacade
            TariffFacade.get_instance().learn_from_draft(draft.invoice_lines)
        except Exception:
            pass
        return result

    # ── Mase (Faza 6) ────────────────────────────────────────

    def calculate_masses(self, draft, bruto_kg: float, neto_kg: float, items: list):
        """Rasporedi ukupne težine na stavke."""
        from services.faktura.mass_calculator import MassCalculator
        MassCalculator.calculate_masses(items, bruto_kg, neto_kg)

    def accumulate_weights(self, draft, bruto_kg: float, neto_kg: float):
        """Akumuliraj težine u draft."""
        from services.faktura.weight_guards import normalize_invoice_key
        invoice_name = getattr(draft, "invoice_lines", []) and getattr(draft.invoice_lines[0], "invoice_number", "") if getattr(draft, "invoice_lines", []) else ""
        if invoice_name and (bruto_kg > 0 or neto_kg > 0):
            draft.invoice_weights[normalize_invoice_key(invoice_name)] = (bruto_kg, neto_kg)

    # ── Item edit / undo (Faza 7A) ────────────────────────────

    def bulk_change_tariff(self, draft, rows: list, tariff: str):
        """Bulk izmjena tarifnog broja za selektovane redove."""
        updated = 0
        for row in rows:
            if row < len(draft.invoice_lines):
                old = draft.invoice_lines[row].tarifni_broj
                draft.invoice_lines[row].tarifni_broj = tariff
                if old != tariff:
                    updated += 1
        if updated:
            draft.mark_dirty()
        return updated

    def delete_item(self, draft, row: int) -> bool:
        """Obriši stavku iz drafta."""
        if 0 <= row < len(draft.invoice_lines):
            del draft.invoice_lines[row]
            draft.mark_dirty()
            return True
        return False

    # ── Export / Partneri (Faza 7B) ────────────────────────────

    def check_partner_consistency(self, draft, exporter: str, importer: str,
                                   expected_exporter: str = "", expected_importer: str = ""):
        """Provjeri konzistentnost partnera."""
        from services.faktura.faktura_service import FakturaService
        
        def similar(a: str, b: str) -> bool:
            na = FakturaService.parse_number.__doc__ or ""  # placeholder
            return a.lower().replace(" ", "") == b.lower().replace(" ", "")
        
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
