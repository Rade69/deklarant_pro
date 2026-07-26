"""
Adapteri za konverziju izvornih modela u neutralni ImportCandidate.

Plan §16 Faza 2:
  - ImportResult (ručni uvoz) → ImportCandidate
  - FileItem (agent uvoz) → ImportCandidate
  - Ne mijenja parser API
  - Ne uvodi zavisnost zajedničkog servisa prema Agent widgetima

Napomena: adapter za FileItem importa gui.tabs.agent.models.file_item
SAMO unutar funkcije (lazy import), da services/ ne zavisi od gui/ na
modul nivou.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from services.import_workflow.models import (
    ImportCandidate,
    _detect_file_type,
    _normalize_path,
)


def from_import_result(result, source_path: str = "") -> ImportCandidate:
    """Konvertuj ImportResult (ručni uvoz) u neutralni ImportCandidate.

    Args:
        result: ImportResult instanca iz importers/import_result.py
        source_path: putanja fajla (ako nije dostupna u ImportResult).
                     Ako prazno, pokušava se izvući iz invoice_name.
    """
    # ImportResult nema filepath polje — koristi source_path ili invoice_name
    path = source_path or getattr(result, "invoice_name", "") or "unknown"
    display_name = getattr(result, "invoice_name", "") or Path(path).stem
    invoice_name = (getattr(result, "invoice_name", "") or "").strip()
    source_stem = Path(source_path).stem if source_path else ""
    line_numbers = {
        (getattr(line, "invoice_number", "") or "").strip()
        for line in getattr(result, "items", []) or []
        if (getattr(line, "invoice_number", "") or "").strip()
    }
    explicit_invoice_number = ""
    if invoice_name and (source_stem and invoice_name != source_stem or invoice_name in line_numbers):
        explicit_invoice_number = invoice_name

    return ImportCandidate(
        source_path=path,
        normalized_path=_normalize_path(path),
        file_type=_detect_file_type(path),
        parser=getattr(result, "import_type", ""),
        invoice_lines=deepcopy(list(result.items)),
        explicit_invoice_number=explicit_invoice_number,
        display_name=display_name,
        bruto_kg=getattr(result, "bruto_kg", 0.0) or 0.0,
        neto_kg=getattr(result, "neto_kg", 0.0) or 0.0,
        exporter=getattr(result, "exporter", None),
        importer=getattr(result, "importer", None),
        currency=getattr(result, "currency", "") or "",
        incoterm_code=getattr(result, "incoterm_code", "") or "",
        has_origin_statement=getattr(result, "has_origin_statement", False),
        eur1_suggested=getattr(result, "eur1_suggested", False),
        is_authorized_exporter=getattr(result, "is_authorized_exporter", False),
        origin_statements=getattr(result, "origin_statements", None),
        is_combined=getattr(result, "is_combined", False),
        consumed_paths=list(getattr(result, "consumed_paths", []) or []),
        warnings=list(getattr(result, "warnings", []) or []),
        errors=[],
    )


def from_file_item(file_item) -> ImportCandidate:
    """Konvertuj Agent FileItem u neutralni ImportCandidate.

    Args:
        file_item: FileItem instanca iz gui/tabs/agent/models/file_item.py
    """
    path = getattr(file_item, "filepath", "") or "unknown"
    # invoice_number je broj koji je parser eksplicitno izvukao (pouzdan)
    explicit_number = getattr(file_item, "invoice_number", "") or ""
    # display_name: koristi invoice_number ako postoji, inače stem fajla
    display_name = explicit_number or getattr(file_item, "filename", "") or Path(path).stem

    return ImportCandidate(
        source_path=path,
        normalized_path=_normalize_path(path),
        file_type=getattr(file_item, "file_type", "") or _detect_file_type(path),
        parser=getattr(file_item, "detected_parser", "") or getattr(file_item, "parser", ""),
        invoice_lines=deepcopy(list(getattr(file_item, "invoice_lines", []) or [])),
        explicit_invoice_number=explicit_number,
        display_name=display_name,
        bruto_kg=getattr(file_item, "bruto_kg", 0.0) or 0.0,
        neto_kg=getattr(file_item, "neto_kg", 0.0) or 0.0,
        exporter=getattr(file_item, "exporter", None),
        importer=getattr(file_item, "importer", None),
        currency=getattr(file_item, "currency", "") or "",
        incoterm_code=getattr(file_item, "incoterm_code", "") or "",
        has_origin_statement=getattr(file_item, "has_origin_statement", False),
        eur1_suggested=getattr(file_item, "eur1_suggested", False),
        is_authorized_exporter=getattr(file_item, "is_authorized_exporter", False),
        origin_statements=getattr(file_item, "origin_statements", None),
        is_combined=getattr(file_item, "is_combined", False),
        consumed_paths=list(getattr(file_item, "consumed_paths", []) or []),
        warnings=[],
        errors=[str(file_item.error_message)] if getattr(file_item, "error_message", None) else [],
    )
