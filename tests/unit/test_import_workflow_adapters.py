"""
Testovi za neutralne adaptere (Faza 2).

Plan §16 Faza 2 izlaz: oba ulaza (ImportResult i FileItem) proizvode
isti neutralni model ImportCandidate.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from services.import_workflow.models import ImportCandidate
from services.import_workflow.adapters import from_import_result, from_file_item


def _make_invoice_line(invoice_number="INV-001", tarifni_broj="08052190"):
    return InvoiceLine(
        tarifni_broj=tarifni_broj,
        naziv_robe="Test proizvod",
        zemlja_porijekla="DE",
        bruto_kg=10.0,
        neto_kg=9.0,
        iznos=100.0,
        kolicina=5,
        jm="kom",
        invoice_number=invoice_number,
    )


def _make_import_result(source_path="/tmp/INV-001.pdf"):
    """Klasičan ImportResult (ručni uvoz)."""
    return ImportResult(
        items=[_make_invoice_line()],
        bruto_kg=100.0,
        neto_kg=90.0,
        invoice_name="INV-001",
        currency="EUR",
        is_combined=False,
        import_type="invoice",
        has_origin_statement=False,
        is_authorized_exporter=False,
        exporter=Party(name="Exporter d.o.o.", address="Export str 1", country="DE"),
        importer=Party(name="Importer d.o.o.", address="Import str 1", country="BA"),
        consumed_paths=[],
        warnings=["Test upozorenje"],
    )


def _make_file_item(source_path="/tmp/INV-001.pdf"):
    """Agent FileItem sa istim podacima kao ImportResult."""
    # FileItem je u gui/, ali adapter radi getattr pa može i MagicMock
    from gui.tabs.agent.models.file_item import FileItem
    return FileItem(
        filepath=source_path,
        filename="INV-001.pdf",
        file_type="PDF",
        size_bytes=1024,
        parser="Auto-detect",
        status="Completed",
        confidence=1.0,
        added_at=datetime.now(),
        invoice_number="INV-001",
        invoice_lines=[_make_invoice_line()],
        detected_parser="test_parser",
        bruto_kg=100.0,
        neto_kg=90.0,
        has_origin_statement=False,
        is_authorized_exporter=False,
        is_combined=False,
        consumed_paths=[],
        exporter=Party(name="Exporter d.o.o.", address="Export str 1", country="DE"),
        importer=Party(name="Importer d.o.o.", address="Import str 1", country="BA"),
        currency="EUR",
    )


# ── ImportResult → ImportCandidate ─────────────────────────────────────────


class TestFromImportResult:
    def test_vraca_import_candidate(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert isinstance(candidate, ImportCandidate)

    def test_cuva_stavke(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert len(candidate.invoice_lines) == 1
        assert candidate.invoice_lines[0].tarifni_broj == "08052190"

    def test_cuva_tezine(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.bruto_kg == 100.0
        assert candidate.neto_kg == 90.0

    def test_cuva_invoice_name_kao_explicit_broj(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.explicit_invoice_number == "INV-001"
        assert candidate.display_name == "INV-001"

    def test_cuva_partnere(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.exporter is not None
        assert candidate.exporter.name == "Exporter d.o.o."
        assert candidate.importer is not None
        assert candidate.importer.name == "Importer d.o.o."

    def test_cuva_valutu(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.currency == "EUR"

    def test_cuva_consumed_paths(self):
        result = _make_import_result()
        result.consumed_paths = ["/tmp/other.pdf"]
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.consumed_paths == ["/tmp/other.pdf"]

    def test_cuva_warnings(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert "Test upozorenje" in candidate.warnings

    def test_normalized_path_je_apsolutna(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        # normalized_path je apsolutna, case-normalized (Windows normcase)
        assert candidate.normalized_path != ""
        assert candidate.normalized_path != candidate.source_path or Path(candidate.source_path).is_absolute()

    def test_kombinovani_flag(self):
        result = _make_import_result()
        result.is_combined = True
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.is_combined is True


# ── FileItem → ImportCandidate ─────────────────────────────────────────────


class TestFromFileItem:
    def test_vraca_import_candidate(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert isinstance(candidate, ImportCandidate)

    def test_cuva_stavke(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert len(candidate.invoice_lines) == 1
        assert candidate.invoice_lines[0].tarifni_broj == "08052190"

    def test_cuva_tezine(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.bruto_kg == 100.0
        assert candidate.neto_kg == 90.0

    def test_cuva_invoice_number_kao_explicit_broj(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.explicit_invoice_number == "INV-001"

    def test_cuva_partnere(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.exporter is not None
        assert candidate.exporter.name == "Exporter d.o.o."
        assert candidate.importer is not None
        assert candidate.importer.name == "Importer d.o.o."

    def test_cuva_valutu(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.currency == "EUR"

    def test_cuva_consumed_paths(self):
        item = _make_file_item()
        item.consumed_paths = ["/tmp/other.pdf"]
        candidate = from_file_item(item)
        assert candidate.consumed_paths == ["/tmp/other.pdf"]

    def test_cuva_source_path(self):
        item = _make_file_item(source_path="/tmp/INV-001.pdf")
        candidate = from_file_item(item)
        assert candidate.source_path == "/tmp/INV-001.pdf"

    def test_cuva_file_type(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.file_type == "PDF"

    def test_cuva_parser(self):
        item = _make_file_item()
        candidate = from_file_item(item)
        assert candidate.parser == "test_parser"

    def test_kombinovani_flag(self):
        item = _make_file_item()
        item.is_combined = True
        candidate = from_file_item(item)
        assert candidate.is_combined is True


# ── Paritet: isti podaci iz oba izvora daju isti ImportCandidate ──────────


class TestAdapterParity:
    """Isti poslovni podaci kroz ImportResult i FileItem moraju proizvesti
    ekvivalentan ImportCandidate."""

    def test_isti_podaci_daju_ekvivalentan_candidate(self):
        result = _make_import_result(source_path="/tmp/INV-001.pdf")
        item = _make_file_item(source_path="/tmp/INV-001.pdf")

        c1 = from_import_result(result, source_path="/tmp/INV-001.pdf")
        c2 = from_file_item(item)

        # Svi poslovni podaci moraju biti jednaki
        assert c1.invoice_lines == c2.invoice_lines
        assert c1.bruto_kg == c2.bruto_kg
        assert c1.neto_kg == c2.neto_kg
        assert c1.explicit_invoice_number == c2.explicit_invoice_number
        assert c1.currency == c2.currency
        assert c1.has_origin_statement == c2.has_origin_statement
        assert c1.is_authorized_exporter == c2.is_authorized_exporter
        assert c1.is_combined == c2.is_combined
        assert c1.consumed_paths == c2.consumed_paths
        assert (c1.exporter.name if c1.exporter else None) == (c2.exporter.name if c2.exporter else None)
        assert (c1.importer.name if c1.importer else None) == (c2.importer.name if c2.importer else None)

    def test_normalized_path_isti_za_istu_putanju(self):
        result = _make_import_result(source_path="/tmp/INV-001.pdf")
        item = _make_file_item(source_path="/tmp/INV-001.pdf")

        c1 = from_import_result(result, source_path="/tmp/INV-001.pdf")
        c2 = from_file_item(item)

        assert c1.normalized_path == c2.normalized_path


# ── Edge cases ────────────────────────────────────────────────────────────


class TestAdapterEdgeCases:
    def test_import_result_bez_source_path_koristi_invoice_name(self):
        result = _make_import_result()
        candidate = from_import_result(result)
        # source_path treba biti invoice_name ("INV-001") jer nije proslijeđen
        assert "INV-001" in candidate.source_path

    def test_file_item_bez_invoice_number_koristi_filename(self):
        from gui.tabs.agent.models.file_item import FileItem
        item = FileItem(
            filepath="/tmp/scan_final_v2.pdf",
            filename="scan_final_v2.pdf",
            file_type="PDF",
            size_bytes=1024,
            parser="Auto-detect",
            status="Completed",
            confidence=1.0,
            added_at=datetime.now(),
            invoice_number=None,
            invoice_lines=[_make_invoice_line()],
        )
        candidate = from_file_item(item)
        # Bez eksplicitnog broja, explicit_invoice_number je prazan
        assert candidate.explicit_invoice_number == ""
        # display_name koristi filename
        assert candidate.display_name == "scan_final_v2.pdf"

    def test_file_item_sa_error_message(self):
        from gui.tabs.agent.models.file_item import FileItem
        item = FileItem(
            filepath="/tmp/bad.pdf",
            filename="bad.pdf",
            file_type="PDF",
            size_bytes=1024,
            parser="Auto-detect",
            status="Error",
            confidence=0.0,
            added_at=datetime.now(),
            error_message="Parse failed",
        )
        candidate = from_file_item(item)
        assert "Parse failed" in candidate.errors

    def test_prazan_import_result(self):
        result = ImportResult()
        candidate = from_import_result(result, source_path="/tmp/empty.pdf")
        assert candidate.invoice_lines == []
        assert candidate.bruto_kg == 0.0
        assert candidate.has_items is False
        assert candidate.item_count == 0

    def test_has_explicit_invoice_number_property(self):
        result = _make_import_result()
        candidate = from_import_result(result, source_path="/tmp/INV-001.pdf")
        assert candidate.has_explicit_invoice_number is True

    def test_nema_explicitni_broj(self):
        result = ImportResult(invoice_name="")
        candidate = from_import_result(result, source_path="/tmp/scan.pdf")
        assert candidate.has_explicit_invoice_number is False
