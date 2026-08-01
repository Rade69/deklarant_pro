from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from importers.import_result import ImportResult
from services.faktura.weight_guards import normalize_invoice_key
from services.import_workflow.adapters import from_import_result
from services.import_workflow.models import (
    ImportCandidate,
    _detect_file_type,
    _normalize_path,
)
from services.import_workflow.prepare_service import prepare_import
from services.import_workflow.decision_models import (
    InvoiceDecision,
    UserDecisions,
)


@dataclass(frozen=True)
class ImportWorkflowSyncState:
    accumulated_bruto_kg: float
    accumulated_neto_kg: float
    last_invoice_name: str = ""
    last_import_count: int = 0
    expected_exporter: str = ""
    expected_importer: str = ""


class ImportWorkflowService:
    def can_use_unified_manual_import(self, result, draft, assembly) -> bool:
        if not isinstance(result, ImportResult):
            return False
        if getattr(assembly, "master_list_loaded", False):
            return False
        return isinstance(getattr(draft, "invoice_weights", None), dict)

    def can_use_unified_batch_import(self, draft, assembly) -> bool:
        if getattr(assembly, "master_list_loaded", False):
            return False
        return isinstance(getattr(draft, "invoice_weights", None), dict)

    def manual_import_source_path(self, import_worker) -> str:
        return getattr(import_worker, "filepath", "") or ""

    def existing_invoice_keys(self, draft) -> set[str]:
        keys = set(getattr(draft, "invoice_weights", {}) or {})
        for line in getattr(draft, "invoice_lines", []) or []:
            key = normalize_invoice_key(getattr(line, "invoice_number", "") or "")
            if key:
                keys.add(key)
        return keys

    def expected_import_partners(
        self,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ) -> tuple[str, str]:
        exporter = expected_exporter if isinstance(expected_exporter, str) else ""
        importer = expected_importer if isinstance(expected_importer, str) else ""
        draft_exporter = getattr(draft, "izvoznik_naziv", "")
        draft_importer = getattr(draft, "primalac_naziv", "")
        if not exporter and isinstance(draft_exporter, str):
            exporter = draft_exporter
        if not importer and isinstance(draft_importer, str):
            importer = draft_importer
        return exporter or "", importer or ""

    def prepare_manual_import_plan(
        self,
        result: ImportResult,
        source_path: str,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ):
        candidate = from_import_result(result, source_path)
        exporter, importer = self.expected_import_partners(
            draft, expected_exporter, expected_importer
        )
        return prepare_import(
            [candidate],
            existing_invoice_keys=self.existing_invoice_keys(draft),
            expected_exporter=exporter,
            expected_importer=importer,
            expected_currency=getattr(draft, "valuta", "") or "",
        )

    def batch_record_to_import_candidate(self, record: dict) -> ImportCandidate:
        path = record.get("filepath", "") or "unknown"
        result = record.get("_import_result")
        if result is not None:
            candidate = from_import_result(result, path)
            candidate.invoice_lines = deepcopy(list(record.get("items", []) or []))
            candidate.bruto_kg = record.get("bruto_kg", candidate.bruto_kg) or 0.0
            candidate.neto_kg = record.get("neto_kg", candidate.neto_kg) or 0.0
            candidate.warnings = list(record.get("parser_warnings", []) or candidate.warnings)
            return candidate

        invoice_name = (record.get("invoice_name", "") or "").strip()
        source_stem = Path(path).stem if path else ""
        lines = deepcopy(list(record.get("items", []) or []))
        line_numbers = {
            (getattr(line, "invoice_number", "") or "").strip()
            for line in lines
            if (getattr(line, "invoice_number", "") or "").strip()
        }
        explicit_invoice_number = ""
        if invoice_name and (invoice_name != source_stem or invoice_name in line_numbers):
            explicit_invoice_number = invoice_name

        return ImportCandidate(
            source_path=path,
            normalized_path=_normalize_path(path),
            file_type=_detect_file_type(path),
            parser="",
            invoice_lines=lines,
            explicit_invoice_number=explicit_invoice_number,
            display_name=invoice_name or source_stem or "faktura",
            bruto_kg=record.get("bruto_kg", 0.0) or 0.0,
            neto_kg=record.get("neto_kg", 0.0) or 0.0,
            has_origin_statement=record.get("has_origin_statement", False),
            is_authorized_exporter=record.get("is_authorized_exporter", False),
            warnings=list(record.get("parser_warnings", []) or []),
        )

    def prepare_manual_batch_import_plan(
        self,
        records: list,
        draft,
        expected_exporter: str = "",
        expected_importer: str = "",
    ):
        candidates = [
            self.batch_record_to_import_candidate(record)
            for record in records
            if not record.get("skipped") and record.get("items")
        ]
        exporter, importer = self.expected_import_partners(
            draft, expected_exporter, expected_importer
        )
        return prepare_import(
            candidates,
            existing_invoice_keys=self.existing_invoice_keys(draft),
            expected_exporter=exporter,
            expected_importer=importer,
            expected_currency=getattr(draft, "valuta", "") or "",
        )

    def sync_state_after_apply(self, draft, plan, apply_result) -> ImportWorkflowSyncState:
        accumulated_bruto = 0.0
        accumulated_neto = 0.0
        for bruto, neto in (getattr(draft, "invoice_weights", {}) or {}).values():
            accumulated_bruto += bruto or 0.0
            accumulated_neto += neto or 0.0

        applied_keys = set(apply_result.applied_invoice_keys)
        applied = [
            invoice for invoice in plan.invoices
            if invoice.internal_key in applied_keys
        ]
        if not applied:
            return ImportWorkflowSyncState(accumulated_bruto, accumulated_neto)

        last_invoice = applied[-1]
        exporter = last_invoice.exporter.name if last_invoice.exporter else ""
        importer = last_invoice.importer.name if last_invoice.importer else ""
        return ImportWorkflowSyncState(
            accumulated_bruto_kg=accumulated_bruto,
            accumulated_neto_kg=accumulated_neto,
            last_invoice_name=last_invoice.invoice_number or last_invoice.display_name,
            last_import_count=len(last_invoice.invoice_lines),
            expected_exporter=exporter,
            expected_importer=importer,
        )

    def init_import_decisions(self, plan) -> UserDecisions:
        decisions = UserDecisions()
        for invoice in plan.invoices:
            decisions.invoice_decisions[invoice.internal_key] = InvoiceDecision(
                invoice_key=invoice.internal_key
            )
        return decisions
