"""
Karakterizacioni testovi za nove helper funkcije u xml_header_extraction.py
— Faza 7b (2026-08-02), izdvojeno iz FakturaView._on_load_previous_declaration
(fallback logika za izvoznika, formatiranje pregleda, upis u draft).
"""
from types import SimpleNamespace

from core.draft import DeclarationDraft, InvoiceLine
from services.faktura.xml_header_extraction import (
    resolve_exporter_name,
    format_header_preview,
    apply_header_to_draft,
)


class TestResolveExporterName:
    def test_koristi_draft_izvoznika_ako_je_popunjen(self):
        line = InvoiceLine(line_no=1, naziv_robe="X")
        line.exporter = SimpleNamespace(name="Ignorisano DOO")
        assert resolve_exporter_name("Draft Izvoznik", [line]) == "Draft Izvoznik"

    def test_fallback_na_prvu_liniju_sa_exporterom(self):
        line1 = InvoiceLine(line_no=1, naziv_robe="X")
        line2 = InvoiceLine(line_no=2, naziv_robe="Y")
        line2.exporter = SimpleNamespace(name="ACME DOO\nAdresa 1")
        assert resolve_exporter_name("", [line1, line2]) == "ACME DOO"

    def test_prazno_kad_nema_ni_draft_ni_linija(self):
        assert resolve_exporter_name("", []) == ""

    def test_prazno_kad_linije_nemaju_exportera(self):
        line = InvoiceLine(line_no=1, naziv_robe="X")
        assert resolve_exporter_name(None, [line]) == ""


class TestFormatHeaderPreview:
    def test_samo_popunjena_polja_u_redoslijedu_field_labels(self):
        header = {"valuta": "EUR", "izvoznik_naziv": "ACME"}
        field_labels = {"izvoznik_naziv": "Izvoznik", "valuta": "Valuta", "uslovi_kod": "Incoterm"}
        result = format_header_preview(header, field_labels)
        assert result == ["  Izvoznik: ACME", "  Valuta: EUR"]

    def test_prazan_header_daje_praznu_listu(self):
        assert format_header_preview({}, {"valuta": "Valuta"}) == []


class TestApplyHeaderToDraft:
    def test_upisuje_samo_postojeca_polja_sa_vrijednoscu(self):
        draft = DeclarationDraft()
        apply_header_to_draft(draft, {"izvoznik_naziv": "ACME", "nepostojece_polje": "x"})
        assert draft.izvoznik_naziv == "ACME"
        assert not hasattr(draft, "nepostojece_polje")

    def test_preskace_prazne_vrijednosti(self):
        draft = DeclarationDraft()
        draft.izvoznik_naziv = "Postojece"
        apply_header_to_draft(draft, {"izvoznik_naziv": ""})
        assert draft.izvoznik_naziv == "Postojece"
