import pytest

from importers.vendors.master_frigo import master_frigo_importer as mfi


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Faktura broj: 0504-3-2026-00010", "0504-3-2026-00010"),
        ("INVOICE NO: INV/2026/001", "INV/2026/001"),
        ("broj: 12345", "12345"),
        ("broj: 26/04/2026", ""),
    ],
)
def test_extract_invoice_no_formats(line, expected):
    assert mfi._extract_invoice_no([line]) == expected


def test_import_master_frigo_prefers_header_invoice_number(monkeypatch):
    def fake_parse_master_frigo_pdf(pdf_path, mapping=None):
        return {"invoice_no": "MF-2026/77", "currency": "EUR"}, []

    def fake_convert_to_invoice_lines(imported_lines, currency="EUR"):
        return []

    monkeypatch.setattr(mfi, "parse_master_frigo_pdf", fake_parse_master_frigo_pdf)
    monkeypatch.setattr(mfi, "convert_to_invoice_lines", fake_convert_to_invoice_lines)

    result = mfi.import_master_frigo("/tmp/master_frigo_ime_fajla.pdf")

    assert result.invoice_name == "MF-2026/77"
