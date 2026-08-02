"""
Karakterizacioni test za FakturaView._process_batch_records_legacy kad je
Assembly (master lista) VEĆ aktivan prije grupnog uvoza — Faza "Assembly
EUR.1 dialog parity" nastavak (2026-08-02,
project_rooms/2026-08-02_assembly-eur1-dialog-parity.md).

Bug koji se testira: grana `else: self.draft.invoice_lines.clear();
self.draft.invoice_lines.extend(all_items)` je ZAOBILAZILA
`assembly.add_invoice()` — Assembly completion status ostajao zamrznut,
i BRISALA prethodno matchovane stavke iz ranijih pojedinačnih uvoza.

Koristi pravi DeclarationAssembly (ne mock — poslovna logika mora biti
stvarna), MagicMock samo za Qt-zavisne dijelove koji se ne mogu headless
testirati (dijalozi, tabela, worker cleanup).
"""
from unittest.mock import MagicMock, patch

from core.draft import InvoiceLine, DeclarationDraft
from services.naimenovanja.declaration_assembly import DeclarationAssembly
from gui.tabs.faktura_view import FakturaView


def _line(naziv="Grejac spirala", tarifa="85168020", zemlja="IT", **kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1, naziv_robe=naziv, tarifni_broj=tarifa,
        zemlja_porijekla=zemlja, kolicina=1.0, jm="kom",
        cijena_jed=10.0, iznos=10.0,
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


def _batch_record(invoice_name: str, items: list, filepath: str) -> dict:
    return {
        "items": items,
        "bruto_kg": 1.0,
        "neto_kg": 0.9,
        "invoice_name": invoice_name,
        "filepath": filepath,
        "_import_result": None,
        "parser_warnings": [],
        "skipped": False,
    }


def _mock_self_with_assembly(assembly: DeclarationAssembly, draft: DeclarationDraft):
    mock_self = MagicMock()
    mock_self.assembly = assembly
    mock_self.draft = draft
    mock_self._batch_failed = []
    mock_self.imported_excel_count = 0
    mock_self.imported_pdf_count = 0
    mock_self.weight_manager = MagicMock()
    mock_self.weight_manager.accumulated_bruto_kg = 0.0
    mock_self.weight_manager.accumulated_neto_kg = 0.0
    # Ne otvaraj stvarne dijaloge — nema origin izjave u test fixture-ima
    # pa se dialog_type == NONE ne poziva, ali mock postoji za sigurnost.
    mock_self._collect_manual_origin_response = MagicMock(return_value=MagicMock(
        resolution="skipped", dialog_data={},
    ))
    return mock_self


class TestGrupniUvozKadJeAssemblyVecAktivan:
    def test_add_invoice_se_poziva_ne_clear_extend(self):
        """Bug fix: assembly.items mora biti azuriran preko add_invoice(),
        ne zaobidjen preko draft.invoice_lines.clear()+extend()."""
        assembly = DeclarationAssembly()
        # Master-liste stavka BEZ cijene (kao stvarna Excel master lista) -
        # nekompletna dok se ne uvede prava faktura.
        assembly.load_master_list_from_lines(
            [_line(naziv="Grejac spirala", tarifa="85168020", cijena_jed=0.0, iznos=0.0)],
            "master",
        )
        assert assembly.get_completion_status()["completion_percentage"] == 0

        draft = DeclarationDraft()
        mock_self = _mock_self_with_assembly(assembly, draft)

        record = _batch_record(
            "INV-100", [_line(naziv="Grejac spirala", tarifa="85168020", cijena_jed=25.0, iznos=25.0)],
            "faktura1.pdf",
        )
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records_legacy(mock_self, [record])

        status = assembly.get_completion_status()
        assert status["imported_invoices_count"] == 1
        assert status["imported_invoices"] == ["INV-100"]
        assert status["completion_percentage"] > 0  # vise nije zamrznuto na 0%

    def test_prethodno_matchovane_stavke_nisu_obrisane(self):
        """Bug fix: grupni uvoz NE SMIJE obrisati vec matchovane stavke iz
        ranijeg pojedinacnog uvoza (add_invoice akumulira, ne brise)."""
        assembly = DeclarationAssembly()
        assembly.load_master_list_from_lines(
            [
                _line(naziv="Grejac spirala", tarifa="85168020"),
                _line(naziv="Termostat", tarifa="90328900"),
            ],
            "master",
        )
        # Simuliraj raniji pojedinacni uvoz - vec matchovano.
        matched1, _, _ = assembly.add_invoice(
            [_line(naziv="Grejac spirala", tarifa="85168020", cijena_jed=5.0, iznos=5.0)],
            "INV-EARLIER",
        )
        assert matched1 == 1
        assert assembly.get_completion_status()["imported_invoices_count"] == 1

        draft = DeclarationDraft()
        draft.invoice_lines = assembly.create_draft().invoice_lines
        mock_self = _mock_self_with_assembly(assembly, draft)

        record = _batch_record(
            "INV-BATCH", [_line(naziv="Termostat", tarifa="90328900", cijena_jed=7.0, iznos=7.0)],
            "faktura2.pdf",
        )
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records_legacy(mock_self, [record])

        status = assembly.get_completion_status()
        # Oba uvoza (raniji pojedinacni + novi grupni) moraju ostati.
        assert status["imported_invoices_count"] == 2
        assert set(status["imported_invoices"]) == {"INV-EARLIER", "INV-BATCH"}
        assert status["complete"] == 2  # obje stavke sad kompletne

    def test_kad_assembly_nije_aktivan_ponasanje_ostaje_isto(self):
        """Kontrolna provjera: kad master lista NIJE ucitana prije grupnog
        uvoza, staro ponasanje (load_master_list_from_lines) ostaje isto."""
        assembly = DeclarationAssembly()
        assert not assembly.master_list_loaded

        draft = DeclarationDraft()
        mock_self = _mock_self_with_assembly(assembly, draft)

        record = _batch_record(
            "INV-1", [_line(naziv="Grejac spirala", tarifa="85168020")], "faktura1.pdf",
        )
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records_legacy(mock_self, [record])

        assert assembly.master_list_loaded  # sad aktiviran iz samog batcha
        assert len(draft.invoice_lines) == 1
