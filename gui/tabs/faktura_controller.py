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
        from services.validation.validation_service import FakturaItemValidator
        from services.naimenovanja.declaration_assembly import DeclarationAssembly
        self.validator = FakturaItemValidator()
        self.assembly = DeclarationAssembly()
        from services.faktura.import_workflow_service import ImportWorkflowService
        self.import_workflow = ImportWorkflowService()

    @property
    def draft(self) -> DeclarationDraft:
        return self._get_draft()

    # ── Validacija i bojenje (Faza 3) ──────────────────────────

    def validate_and_color_rows(self, draft, rows: list[int] | None = None) -> dict:
        """Validiraj sve redove i vrati boje + tooltip.
        """
        from services.faktura.validation_service import ValidationService

        svc = ValidationService()
        lines = getattr(draft, "invoice_lines", []) or []
        color_map = {}
        style_map = {}
        errors = 0
        warnings = 0
        valid = 0
        target_rows = set(rows or range(len(lines)))

        for idx, line in enumerate(lines):
            try:
                style = svc.validate_and_get_style(line)
                color, tooltip = style.row_color, style.row_tooltip
                color_map[idx] = (color, tooltip)
                style_map[idx] = style
                if idx in target_rows:
                    if style.result.has_blocking_errors():
                        errors += 1
                    elif style.result.warnings:
                        warnings += 1
                    elif style.result.valid:
                        valid += 1
            except Exception:
                color_map[idx] = ("#ffffff", "")

        return {
            "validated_count": len(lines),
            "error_count": errors,
            "warning_count": warnings,
            "valid_count": valid,
            "color_map": color_map,
            "style_map": style_map,
            "target_rows": sorted(target_rows),
        }

    def validate_line(self, line):
        return self.validator.validate(line)

    def assembly_completion_status(self) -> dict | None:
        if not getattr(self.assembly, "master_list_loaded", False):
            return None
        return self.assembly.get_completion_status()

    def reset_assembly(self):
        from services.naimenovanja.declaration_assembly import DeclarationAssembly
        self.assembly = DeclarationAssembly()
        return self.assembly

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

    def can_use_unified_manual_import(self, result, draft) -> bool:
        return self.import_workflow.can_use_unified_manual_import(
            result, draft, self.assembly
        )

    def can_use_unified_batch_import(self, draft) -> bool:
        return self.import_workflow.can_use_unified_batch_import(draft, self.assembly)

    def manual_import_source_path(self, import_worker) -> str:
        return self.import_workflow.manual_import_source_path(import_worker)

    def existing_invoice_keys_for_import_workflow(self, draft) -> set[str]:
        return self.import_workflow.existing_invoice_keys(draft)

    def expected_import_partners(
        self,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ) -> tuple[str, str]:
        return self.import_workflow.expected_import_partners(
            draft, expected_exporter, expected_importer
        )

    def prepare_manual_import_plan(
        self,
        result,
        source_path: str,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ):
        return self.import_workflow.prepare_manual_import_plan(
            result, source_path, draft, expected_exporter, expected_importer
        )

    def batch_record_to_import_candidate(self, record: dict):
        return self.import_workflow.batch_record_to_import_candidate(record)

    def prepare_manual_batch_import_plan(
        self,
        records: list,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ):
        return self.import_workflow.prepare_manual_batch_import_plan(
            records, draft, expected_exporter, expected_importer
        )

    def sync_import_workflow_state_after_apply(self, draft, plan, apply_result):
        return self.import_workflow.sync_state_after_apply(draft, plan, apply_result)

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
        from services.faktura.create_naimenovanja_workflow_service import (
            CreateNaimenovanjaWorkflowService,
        )
        workflow_result = CreateNaimenovanjaWorkflowService().create_for_drafts([draft])
        if workflow_result.error:
            e = workflow_result.error
            logger.exception("create_naimenovanja failed")
            result["error"] = str(e)
            return result
        if workflow_result.draft_results:
            result["count"] = workflow_result.draft_results[0].count
        return result

    # ── Mase (Faza 6) ────────────────────────────────────────

    def calculate_masses(self, items: list, bruto_kg: float, neto_kg: float):
        """Rasporedi ukupne težine na stavke."""
        from services.faktura.mass_calculator import MassCalculator
        MassCalculator.calculate_masses(items, bruto_kg, neto_kg)

    def calculate_masses_for_draft(self, draft, request):
        from services.faktura.mass_workflow_service import MassWorkflowService
        return MassWorkflowService().calculate(draft, request)

    def auto_fill_workflow(self, request):
        from services.faktura.auto_fill_workflow_service import AutoFillWorkflowService
        return AutoFillWorkflowService().run(request)

    def prepare_auto_fill_preview(self, request):
        from services.faktura.auto_fill_workflow_service import AutoFillWorkflowService
        return AutoFillWorkflowService().prepare_preview(request)

    def empty_auto_fill_result(self, total_items: int, skipped_details: list):
        from services.faktura.auto_fill_workflow_service import AutoFillWorkflowService
        return AutoFillWorkflowService().empty_result(total_items, skipped_details)

    def sync_auto_fill_decision_state(self, target_lines: list, supplier_name: str) -> None:
        from services.faktura.auto_fill_workflow_service import AutoFillWorkflowService
        AutoFillWorkflowService().sync_decision_state(target_lines, supplier_name)

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
