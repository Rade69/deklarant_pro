from core.draft.draft import InvoiceLine
from importers.vendors.blagic import blagic_attos_importer


def test_attos_invoice_marks_matching_packing_list_as_combined(monkeypatch, tmp_path):
    invoice_path = tmp_path / "Faktura 2419 - Blagic.pdf"
    packing_path = tmp_path / "Pak lista 2419 - Blagic.pdf"

    monkeypatch.setattr(blagic_attos_importer, "is_blagic_attos_packing_list", lambda _path: False)
    monkeypatch.setattr(
        blagic_attos_importer,
        "parse_blagic_attos_invoice",
        lambda _path: ({"invoice_number": "2419/2026", "currency": "EUR"}, [{}]),
    )
    monkeypatch.setattr(
        blagic_attos_importer,
        "find_matching_packing_list",
        lambda _path: str(packing_path),
    )
    monkeypatch.setattr(blagic_attos_importer, "parse_blagic_attos_packing_list", lambda _path: [{}])
    monkeypatch.setattr(
        blagic_attos_importer,
        "combine_invoice_and_packing",
        lambda *_args: [InvoiceLine(line_no=1, naziv_robe="Termostat")],
    )

    result = blagic_attos_importer.parse_blagic_attos_with_auto_combine(str(invoice_path))

    assert result.is_combined is True
    assert result.consumed_paths == [str(packing_path)]
    assert len(result.items) == 1
