from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from typing import Any

from core.draft.draft import DeclarationDraft, InvoiceLine, Party
from services.faktura.mass_calculator import MassCalculator
from services.faktura.weight_guards import normalize_invoice_key
from services.import_workflow.apply_models import ImportApplyResult
from services.import_workflow.decision_models import (
    OriginDialogResolution,
    UserDecisions,
)
from services.import_workflow.decision_service import (
    invoices_to_apply,
    validate_decisions,
)
from services.import_workflow.plan_models import (
    DraftOperation,
    ImportPlan,
    PreparedInvoice,
)


def apply_import_plan(
    draft: DeclarationDraft,
    plan: ImportPlan,
    decisions: UserDecisions,
) -> ImportApplyResult:
    snapshot = _take_snapshot(draft)
    errors = validate_decisions(plan, decisions)
    if errors:
        return ImportApplyResult(success=False, errors=errors)

    invoices = invoices_to_apply(plan, decisions)
    applied_keys = {inv.internal_key for inv in invoices}
    result = ImportApplyResult(
        success=True,
        skipped_invoices=len(plan.invoices) - len(invoices),
        skipped_items=sum(
            inv.item_count for inv in plan.invoices if inv.internal_key not in applied_keys
        ),
        warnings=list(plan.warnings),
    )

    try:
        for invoice in invoices:
            _apply_invoice(draft, invoice, decisions, result)
        _mark_dirty(draft)
        return result
    except Exception as exc:
        _restore_snapshot(draft, snapshot)
        return ImportApplyResult(
            success=False,
            errors=[f"Greška pri primjeni import plana: {exc}"],
            warnings=list(plan.warnings),
        )


def _apply_invoice(
    draft: DeclarationDraft,
    invoice: PreparedInvoice,
    decisions: UserDecisions,
    result: ImportApplyResult,
) -> None:
    lines = deepcopy(invoice.invoice_lines)
    _assign_invoice_number(lines, invoice.invoice_number)
    _apply_origin_decision(lines, invoice, decisions)

    if invoice.bruto_kg > 0 or invoice.neto_kg > 0:
        MassCalculator.calculate_masses(lines, invoice.bruto_kg, invoice.neto_kg)

    replaced_count = 0
    if invoice.draft_operation == DraftOperation.REPLACE:
        replaced_count = _replace_existing_invoice_lines(draft, invoice)
        result.replaced_invoices += 1
        result.replaced_items += replaced_count
    elif invoice.draft_operation == DraftOperation.ADD:
        result.added_invoices += 1
    else:
        result.skipped_invoices += 1
        result.skipped_items += invoice.item_count
        return

    draft.invoice_lines.extend(lines)
    _store_invoice_weight(draft, invoice, result)
    _apply_header_if_empty(draft, invoice)
    _append_source_files(draft, invoice.source_paths)

    result.applied_invoice_keys.append(invoice.internal_key)
    if invoice.invoice_number:
        result.applied_invoice_numbers.append(invoice.invoice_number)
    result.added_items += len(lines)
    result.total_items += len(lines)
    result.total_bruto_kg += invoice.bruto_kg or 0.0
    result.total_neto_kg += invoice.neto_kg or 0.0
    result.warnings.extend(invoice.warnings)


def _replace_existing_invoice_lines(
    draft: DeclarationDraft,
    invoice: PreparedInvoice,
) -> int:
    key = normalize_invoice_key(invoice.invoice_number)
    if not key:
        raise ValueError("REPLACE zahtijeva pouzdan broj fakture")

    kept: list[InvoiceLine] = []
    removed = 0
    for line in draft.invoice_lines:
        line_key = normalize_invoice_key(getattr(line, "invoice_number", ""))
        if line_key == key:
            removed += 1
        else:
            kept.append(line)
    draft.invoice_lines = kept
    draft.invoice_weights.pop(key, None)
    return removed


def _store_invoice_weight(
    draft: DeclarationDraft,
    invoice: PreparedInvoice,
    result: ImportApplyResult,
) -> None:
    if invoice.bruto_kg <= 0 and invoice.neto_kg <= 0:
        return

    key = normalize_invoice_key(invoice.invoice_number)
    if not key:
        result.warnings.append(
            f"Težina za '{invoice.display_name}' nije upisana jer broj fakture nije pouzdan."
        )
        return
    draft.invoice_weights[key] = (invoice.bruto_kg, invoice.neto_kg)


def _assign_invoice_number(lines: list[InvoiceLine], invoice_number: str) -> None:
    if not invoice_number:
        return
    for line in lines:
        if not getattr(line, "invoice_number", ""):
            line.invoice_number = invoice_number


def _apply_origin_decision(
    lines: list[InvoiceLine],
    invoice: PreparedInvoice,
    decisions: UserDecisions,
) -> None:
    decision = decisions.get_invoice_decision(invoice.internal_key)
    response = decision.origin_response
    if response is None or response.resolution != OriginDialogResolution.APPLIED:
        return

    data = response.dialog_data or {}
    if _apply_grouped_origin_data(lines, data):
        return

    preference = _first(data, "povlastica", "preference", "preference_code")
    eur1_number = _first(data, "eur1_number", "eur1", "document_number")
    origin_country = _first(data, "zemlja_porijekla", "origin_country", "origin_country_code")
    has_statement = data.get("has_origin_statement")
    authorized = data.get("is_authorized_exporter")

    for line in lines:
        if preference:
            line.povlastica = preference
        if eur1_number:
            line.eur1_number = eur1_number
        if origin_country and not getattr(line, "zemlja_porijekla", ""):
            line.zemlja_porijekla = origin_country
        if has_statement is not None:
            line.has_origin_statement = bool(has_statement)
        if authorized is not None:
            line.is_authorized_exporter = bool(authorized)


def _apply_grouped_origin_data(lines: list[InvoiceLine], data: dict) -> bool:
    groups = [value for value in data.values() if isinstance(value, dict)]
    if not groups or not any("items" in group for group in groups):
        return False

    line_by_id = {_line_identity(line): line for line in lines}
    for group_key, group in data.items():
        if not isinstance(group, dict):
            continue

        item_ids = {_line_identity(item) for item in group.get("items", [])}
        if not item_ids:
            continue

        preference = _first(group, "povlastica", "preference", "preference_code")
        eur1_number = _first(group, "eur1_number", "eur1", "document_number", "invoice_number")
        origin_country = _first(
            group, "zemlja_porijekla", "origin_country", "origin_country_code", "country"
        ) or _country_from_group_key(str(group_key))
        doc_code = (group.get("code") or "").strip().upper()

        for item_id in item_ids:
            line = line_by_id.get(item_id)
            if line is None:
                continue
            if preference:
                line.povlastica = preference
            if eur1_number:
                line.eur1_number = eur1_number
            if origin_country and not getattr(line, "zemlja_porijekla", ""):
                line.zemlja_porijekla = origin_country
            if doc_code in {"PE2", "PE3"}:
                line.has_origin_statement = True
                line.is_authorized_exporter = doc_code == "PE3"
            elif "eur1_number" in group:
                line.has_origin_statement = False

            if preference or eur1_number:
                line.country_confidence = "HIGH"
                line.country_conflict_details = ""
                if doc_code in {"PE2", "PE3"}:
                    line.country_source = "PDF_IZJAVA"
                elif "eur1_number" in group:
                    line.country_source = "EUR1_POTVRDA"
    return True


def _line_identity(line: InvoiceLine) -> tuple:
    return (
        getattr(line, "line_no", None),
        getattr(line, "invoice_number", ""),
        getattr(line, "product_code", ""),
        getattr(line, "naziv_robe", ""),
        getattr(line, "tarifni_broj", ""),
        getattr(line, "zemlja_porijekla", ""),
        getattr(line, "kolicina", None),
        getattr(line, "iznos", None),
    )


def _country_from_group_key(key: str) -> str:
    if " - " in key:
        country = key.split(" - ")[-1].strip()
    else:
        country = key.strip()
    if "|rb" in country:
        country = country.split("|rb", 1)[0].strip()
    return country


def _apply_header_if_empty(draft: DeclarationDraft, invoice: PreparedInvoice) -> None:
    _apply_party_to_exporter(draft, invoice.exporter)
    _apply_party_to_importer(draft, invoice.importer)
    currency = (invoice.currency or "").strip()
    if currency and currency.upper() != "EUR" and not draft.valuta:
        draft.valuta = currency


def _apply_party_to_exporter(draft: DeclarationDraft, party: Party | None) -> None:
    if party is None:
        return
    if party.name and not draft.izvoznik_naziv:
        draft.izvoznik_naziv = party.name.strip().split("\n")[0].strip()
    if party.address and not draft.izvoznik_adresa:
        draft.izvoznik_adresa = party.address.strip()
    if party.city and not draft.izvoznik_grad:
        draft.izvoznik_grad = party.city.strip()
    if party.country and not draft.izvoznik_drzava:
        draft.izvoznik_drzava = party.country.strip()


def _apply_party_to_importer(draft: DeclarationDraft, party: Party | None) -> None:
    if party is None:
        return
    if party.name and not draft.primalac_naziv:
        draft.primalac_naziv = party.name.strip().split("\n")[0].strip()
    if party.vat_or_id and not draft.primalac_id:
        draft.primalac_id = party.vat_or_id.strip()
    if party.address and not draft.primalac_adresa:
        draft.primalac_adresa = party.address.strip()
    if party.city and not draft.primalac_grad:
        draft.primalac_grad = party.city.strip()
    if party.country and not draft.primalac_drzava:
        draft.primalac_drzava = party.country.strip()


def _append_source_files(draft: DeclarationDraft, source_paths: list[str]) -> None:
    existing = set(draft.source_files or [])
    for path in source_paths:
        if path and path not in existing:
            draft.source_files.append(path)
            existing.add(path)


def _take_snapshot(draft: DeclarationDraft) -> dict[str, Any]:
    return {
        f.name: deepcopy(getattr(draft, f.name))
        for f in fields(draft)
        if f.name != "_data_change_callbacks"
    }


def _restore_snapshot(draft: DeclarationDraft, snapshot: dict[str, Any]) -> None:
    for name, value in snapshot.items():
        setattr(draft, name, value)


def _mark_dirty(draft: DeclarationDraft) -> None:
    mark_dirty = getattr(draft, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty()
    else:
        draft.dirty = True


def _first(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
