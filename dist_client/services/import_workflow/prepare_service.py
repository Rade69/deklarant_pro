"""
Servis pripreme uvoza (Faza 3).

Plan §16 Faza 3:
  1. Deduplikacija i consumed_paths
  2. Stabilno sortiranje
  3. Identitet fakture
  4. Grupisanje fizičkih fajlova u logičke fakture
  5. Partner/valuta/header konflikti
  6. Normalizacija tarifa
  7. Priprema težina
  8. Priprema PE2/PE3/EUR1 zahtjeva
  9. Plan ADD/REPLACE/SKIP

Izlaz: determinističan ImportPlan bez izmjene drafta.

Bitno: servis NE mijenja draft, NE otvara dijaloge, NE dira Qt widgete.
Sve poslovne odluke (koje postojeće metode u faktura_view.py rade) ovde
se samo PRIPREME — primjena je Faza 5.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Optional

from core.draft.draft import InvoiceLine, Party
from services.import_workflow.models import ImportCandidate
from services.import_workflow.plan_models import (
    CurrencyConflict,
    DraftOperation,
    FailedFile,
    ImportPlan,
    OriginDialogType,
    PartnerConflict,
    PreparedInvoice,
    SkippedFile,
)


# ── Konstante (preuzete iz postojećeg koda) ────────────────────────────────

EUR1_THRESHOLD = 6000.0  # EUR — iznad ove vrijednosti treba EUR.1 (ne PE2)


# ── Pomoćne funkcije (preuzete iz postojećih metoda, bez Qt zavisnosti) ────


def normalize_tariff_number(code: str) -> str:
    """Normalizuj tarifni broj (delegira na importers.invoice_line_utils).

    Plan §19 scope lock: ne mijenja se format tarife.
    """
    from importers.invoice_line_utils import normalize_tariff_number as _normalize
    normalized = _normalize(code or "")
    # Excel gubi vodeće nule (npr. "03824999" → "3824999") — zfill vraća ih za 4-7 cifara
    if normalized and normalized.isdigit() and 4 <= len(normalized) < 8:
        normalized = normalized.zfill(8)
    return normalized


def normalize_partner_name(name: str) -> str:
    """Normalizuj naziv partnera za poređenje (preuzeto iz FakturaView)."""
    name = (name or "").lower().strip()
    name = re.sub(r"[.\-,;:'/\\()]", " ", name)
    name = re.sub(r"\b(doo|d\.o\.o|dd|a\.d|ad|llc|ltd|gmbh|srl)\b", "", name)
    return re.sub(r"\s+", " ", name).strip()


def partners_similar(a: str, b: str, threshold: float = 0.6) -> bool:
    """Da li su dva partnera "isti" (token overlap >= threshold).

    Preuzeto iz FakturaView._check_partner_consistency.
    """
    na, nb = normalize_partner_name(a), normalize_partner_name(b)
    if not na or not nb:
        return True  # Nema podataka — ne blokiraj
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return True
    overlap = len(ta & tb) / max(len(ta), len(tb))
    return overlap >= threshold


def invoice_keys_match(a: str, b: str, min_len: int = 5) -> bool:
    """Da li su dva invoice identifikatora "ista" (preuzeto iz _is_same_combined_invoice)."""
    if not (a and b):
        return False
    last_norm = a.replace(" ", "").replace("-", "").lower()
    current_norm = b.replace(" ", "").replace("-", "").lower()
    min_l = min(len(last_norm), len(current_norm))
    if min_l < min_len:
        return False
    prefix_match = last_norm[:min_l] == current_norm[:min_l]
    substring_match = last_norm in current_norm or current_norm in last_norm
    return prefix_match or substring_match


def determine_origin_dialog(
    invoice_lines: list[InvoiceLine],
    has_origin_statement: bool,
    is_authorized_exporter: bool,
    eur1_suggested: bool = False,
) -> OriginDialogType:
    """Odredi tip dijaloga za porijeklo robe.

    Preuzeto iz import_pipeline_service._origin_dialog_type — ista logika,
    ali vraća enum umjesto stringa.
    """
    if eur1_suggested:
        return OriginDialogType.EUR1
    if has_origin_statement:
        if is_authorized_exporter:
            return OriginDialogType.PE3
        # Standardna izjava — provjeri ukupnu vrijednost robe s porijeklom
        val = sum(l.iznos or 0 for l in invoice_lines if getattr(l, "zemlja_porijekla", None))
        if val == 0:
            val = sum(l.iznos or 0 for l in invoice_lines)
        return OriginDialogType.PE2 if val <= EUR1_THRESHOLD else OriginDialogType.EUR1
    # Nema izjave — EUR.1 potreban ako stavke imaju zemlja_porijekla
    has_pending = any(
        getattr(l, "zemlja_porijekla", None)
        and not getattr(l, "has_origin_statement", False)
        and not getattr(l, "eur1_number", None)
        for l in invoice_lines
    )
    return OriginDialogType.EUR1 if has_pending else OriginDialogType.NONE


# ── Glavni servis pripreme ─────────────────────────────────────────────────


def prepare_import(
    candidates: list[ImportCandidate],
    existing_invoice_keys: Optional[set[str]] = None,
    expected_exporter: str = "",
    expected_importer: str = "",
    expected_currency: str = "",
) -> ImportPlan:
    """Pripremi deterministički ImportPlan bez izmjene drafta.

    Args:
        candidates: Lista ImportCandidate (iz adaptera Faze 2).
        existing_invoice_keys: Normalizovani invoice ključevi koji već postoje
                               u draftu (za REPLACE/EXTEND odluku). Može biti None.
        expected_exporter: Očekivani izvoznik (iz postojećeg drafta). Prazno = prvi uvoz.
        expected_importer: Očekivani uvoznik.
        expected_currency: Očekivana valuta.

    Returns:
        ImportPlan — spreman za Fazu 4 (korisničke odluke) i Fazu 5 (primjena).
    """
    plan = ImportPlan()
    existing_keys = existing_invoice_keys or set()

    # ── Korak 1: Deduplikacija (consumed_paths + normalized_path) ──
    consumed = set()
    for c in candidates:
        for p in c.consumed_paths:
            import os
            from pathlib import Path
            try:
                consumed.add(os.path.normcase(str(Path(p).resolve())))
            except (OSError, ValueError):
                consumed.add(p)

    deduped: list[ImportCandidate] = []
    seen_paths: set[str] = set()
    for c in candidates:
        # Preskoči ako je putanja već potrošena (consumed_paths)
        if c.normalized_path in consumed:
            plan.skipped.append(SkippedFile(
                source_path=c.source_path,
                reason="consumed",
            ))
            continue
        # Preskoči ako je ista putanja već viđena (duplikat)
        if c.normalized_path in seen_paths:
            plan.skipped.append(SkippedFile(
                source_path=c.source_path,
                reason="duplicate_path",
            ))
            continue
        seen_paths.add(c.normalized_path)
        deduped.append(c)

    # ── Korak 2: Stabilno sortiranje ────────────────────────────────
    # Sortiraj po display_name pa po source_path — deterministički redoslijed.
    deduped.sort(key=lambda c: (c.display_name, c.source_path))

    # ── Korak 3: Grupisanje u logičke fakture ──────────────────────
    # Kombinovani rezultat (is_combined=True) je već jedna logička faktura.
    groups: list[list[ImportCandidate]] = []
    for c in deduped:
        # Neuspjeli (bez stavki) idu u failed
        if not c.has_items:
            plan.failed.append(FailedFile(
                source_path=c.source_path,
                errors=c.errors or ["Parser nije vratio nijednu stavku"],
            ))
            continue
        # Kombinovani = zasebna grupa (već je spojen Excel+PDF)
        if c.is_combined:
            groups.append([c])
            continue
        groups.append([c])

    # ── Korak 4-9: Pripremi svaku logičku fakturu ──────────────────
    seen_invoice_numbers: set[str] = set()
    for idx, group in enumerate(groups):
        prepared = _prepare_invoice(group, idx, existing_keys, seen_invoice_numbers)
        if prepared is not None:
            plan.invoices.append(prepared)
            if prepared.invoice_number:
                seen_invoice_numbers.add(_normalize_invoice_key(prepared.invoice_number))
            plan.warnings.extend(prepared.warnings)

    # ── Provjeri konflikte partnera/valute ──────────────────────────
    _detect_conflicts(plan, expected_exporter, expected_importer, expected_currency)

    # ── Sažmi brojeve za završnu poruku ─────────────────────────────
    for inv in plan.invoices:
        if inv.draft_operation == DraftOperation.ADD:
            plan.expected_add_count += 1
        elif inv.draft_operation == DraftOperation.REPLACE:
            plan.expected_replace_count += 1
        else:
            plan.expected_skip_count += 1
            continue
        plan.expected_total_items += inv.item_count
        plan.expected_total_bruto += inv.bruto_kg
        plan.expected_total_neto += inv.neto_kg
        # Pripremi origin_dialogs_needed (samo one koje nisu NONE)
        if inv.origin_dialog != OriginDialogType.NONE:
            plan.origin_dialogs_needed.append((inv.internal_key, inv.origin_dialog))

    return plan


def _prepare_invoice(
    group: list[ImportCandidate],
    idx: int,
    existing_keys: set[str],
    seen_numbers: set[str],
) -> Optional[PreparedInvoice]:
    """Pripremi jednu logičku fakturu iz grupe kandidata."""
    # Objedini stavke iz svih fajlova grupe
    all_lines: list[InvoiceLine] = []
    for c in group:
        all_lines.extend(deepcopy(c.invoice_lines))

    # Normalizuj tarifne brojeve (Korak 6)
    for line in all_lines:
        if getattr(line, "tarifni_broj", ""):
            line.tarifni_broj = normalize_tariff_number(line.tarifni_broj)

    # Identitet fakture (Korak 3)
    # Uzmi pouzdani broj iz prvog kandidata koji ga ima
    invoice_number = ""
    for c in group:
        if c.has_explicit_invoice_number:
            invoice_number = c.explicit_invoice_number.strip()
            break
    display_name = group[0].display_name or invoice_number or f"faktura_{idx + 1}"

    # Interni ključ (stabilan, za grupisanje — ne poslovni broj)
    if invoice_number:
        internal_key = f"inv:{_normalize_invoice_key(invoice_number)}:{idx + 1}"
    else:
        internal_key = f"path:{group[0].normalized_path}"

    # Težine (Korak 7 — samo sakupi, raspodjela je Faza 5)
    bruto = sum(c.bruto_kg for c in group)
    neto = sum(c.neto_kg for c in group)

    # Partneri i valuta (Korak 5 — uzmi prvi neprazni)
    exporter = None
    importer = None
    currency = ""
    incoterm_code = ""
    has_origin_statement = False
    eur1_suggested = False
    is_authorized_exporter = False
    origin_statements = None
    source_paths = [c.source_path for c in group]
    warnings: list[str] = []

    for c in group:
        if exporter is None and c.exporter is not None:
            exporter = c.exporter
        if importer is None and c.importer is not None:
            importer = c.importer
        if not currency and c.currency:
            currency = c.currency
        if not incoterm_code and c.incoterm_code:
            incoterm_code = c.incoterm_code
        if c.has_origin_statement:
            has_origin_statement = True
        if c.eur1_suggested:
            eur1_suggested = True
        if c.is_authorized_exporter:
            is_authorized_exporter = True
        if c.origin_statements:
            origin_statements = c.origin_statements
        warnings.extend(c.warnings)
        warnings.extend(c.errors)

    # PE2/PE3/EUR1 zahtjev (Korak 8)
    origin_dialog = determine_origin_dialog(
        all_lines, has_origin_statement, is_authorized_exporter, eur1_suggested
    )

    # Plan ADD/REPLACE/SKIP (Korak 9)
    # Ako invoice_number već postoji u draftu → REPLACE
    # Ako je već viđen u ovom batchu → SKIP (duplikat)
    # Inače → ADD
    normalized_invoice = _normalize_invoice_key(invoice_number)
    normalized_existing = {_normalize_invoice_key(key) for key in existing_keys}
    if invoice_number and normalized_invoice in normalized_existing:
        draft_op = DraftOperation.REPLACE
    elif invoice_number and normalized_invoice in seen_numbers:
        draft_op = DraftOperation.SKIP
    else:
        draft_op = DraftOperation.ADD

    # Postavi invoice_number na stavke (samo ako je pouzdano utvrđen)
    if invoice_number:
        for line in all_lines:
            if not getattr(line, "invoice_number", ""):
                line.invoice_number = invoice_number

    return PreparedInvoice(
        internal_key=internal_key,
        invoice_number=invoice_number,
        display_name=display_name,
        invoice_lines=all_lines,
        bruto_kg=bruto,
        neto_kg=neto,
        exporter=exporter,
        importer=importer,
        currency=currency,
        incoterm_code=incoterm_code,
        has_origin_statement=has_origin_statement,
        eur1_suggested=eur1_suggested,
        is_authorized_exporter=is_authorized_exporter,
        origin_statements=origin_statements,
        source_paths=source_paths,
        origin_dialog=origin_dialog,
        draft_operation=draft_op,
        warnings=warnings,
    )


def _normalize_invoice_key(invoice_number: str) -> str:
    """Normalizuj invoice_number za poređenje sa draft-om."""
    from services.faktura.weight_guards import normalize_invoice_key
    return normalize_invoice_key(invoice_number or "")


def _detect_conflicts(
    plan: ImportPlan,
    expected_exporter: str,
    expected_importer: str,
    expected_currency: str,
) -> None:
    """Detektuj konflikte partnera/valute (zahtijevaju korisničku odluku)."""
    # Prva faktura postavlja očekivanja ako su prazna
    first_exporter = ""
    first_importer = ""
    first_currency = ""

    for inv in plan.invoices:
        exp_name = inv.exporter.name if inv.exporter else ""
        imp_name = inv.importer.name if inv.importer else ""
        if not first_exporter and exp_name:
            first_exporter = exp_name
        if not first_importer and imp_name:
            first_importer = imp_name
        if not first_currency and inv.currency:
            first_currency = inv.currency

    # Očekivani = postojeći iz drafta, ili prvi iz batcha ako draft nema
    check_exporter = expected_exporter or first_exporter
    check_importer = expected_importer or first_importer
    check_currency = expected_currency or first_currency

    # Provjeri svaku fakturu protiv očekivanja
    for inv in plan.invoices:
        exp_name = inv.exporter.name if inv.exporter else ""
        imp_name = inv.importer.name if inv.importer else ""
        if check_exporter and exp_name and not partners_similar(check_exporter, exp_name):
            plan.partner_conflicts.append(PartnerConflict(
                invoice_key=inv.internal_key,
                field_name="exporter",
                expected=check_exporter,
                actual=exp_name,
            ))
        if check_importer and imp_name and not partners_similar(check_importer, imp_name):
            plan.partner_conflicts.append(PartnerConflict(
                invoice_key=inv.internal_key,
                field_name="importer",
                expected=check_importer,
                actual=imp_name,
            ))
        if check_currency and inv.currency and inv.currency.upper() != check_currency.upper():
            plan.currency_conflicts.append(CurrencyConflict(
                invoice_key=inv.internal_key,
                expected=check_currency,
                actual=inv.currency,
            ))
