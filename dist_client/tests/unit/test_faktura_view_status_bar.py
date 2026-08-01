"""
Testovi za FakturaView statusnu traku (2026-07-21).

Korisnička primjedba nakon testiranja: (1) "Komada" je prikazivalo decimalan
broj (npr. "8,045.0") iako u carinskom postupku kolicina mora biti cio broj;
(2) "Porijeklo" je prikazivalo samo "9 zemalja" umjesto ranijeg breakdown-a
po zemlji ("DE:9 | IT:8..."), izgubljenog u komitu 735400a
("style(faktura): sažmi statusnu traku").

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gui.tabs.faktura_view import FakturaView


def _stub_invoice_line(
    kolicina: float = 0.0,
    iznos: float = 0.0,
    bruto_kg: float = 0.0,
    neto_kg: float = 0.0,
    valuta: str = "EUR",
    zemlja_porijekla: str = "",
    tarifni_broj: str = "12345678",
    povlastica: str = "",
) -> MagicMock:
    line = MagicMock()
    line.kolicina = kolicina
    line.iznos = iznos
    line.bruto_kg = bruto_kg
    line.neto_kg = neto_kg
    line.valuta = valuta
    line.zemlja_porijekla = zemlja_porijekla
    line.tarifni_broj = tarifni_broj
    line.povlastica = povlastica
    line.has_origin_statement = False
    line.eur1_number = ""
    return line


def _mock_self_for_status_bar(invoice_lines: list) -> MagicMock:
    mock_self = MagicMock()
    mock_self.draft.invoice_lines = invoice_lines
    mock_self.validation_cache.get_error_count.return_value = 0
    mock_self.validation_cache.get_warning_count.return_value = 0
    mock_self.validation_cache.get_valid_count.return_value = len(invoice_lines)
    mock_self._validation_issue_counts.return_value = ({}, {})
    mock_self.imported_excel_count = 0
    mock_self.imported_pdf_count = 0
    mock_self.input_bruto.text.return_value = "0"
    mock_self.input_neto.text.return_value = "0"
    mock_self._parse_weight_input.return_value = 0.0
    mock_self._format_weight.return_value = "0.000"
    mock_self.controller = None
    mock_self._assembly_completion_status_for_status_bar.return_value = None
    mock_self.assembly.master_list_loaded = False
    return mock_self


def test_komada_prikazan_kao_cio_broj_bez_decimale():
    """Zbir float kolicina (4022.5 + 4022.5 = 8045.0) ne smije prikazati '.0'."""
    mock_self = _mock_self_for_status_bar(
        [_stub_invoice_line(kolicina=4022.5), _stub_invoice_line(kolicina=4022.5)]
    )

    FakturaView._update_status_bar(mock_self)

    text = mock_self.lbl_total_quantity.setText.call_args[0][0]
    assert text == "📦 Komada: 8,045"
    assert "." not in text


def test_komada_zaokruzuje_necio_zbir_a_ne_odsjeca():
    """Ako zbir ipak ispadne necio (npr. 10.4), zaokruzi umjesto da odsijece."""
    mock_self = _mock_self_for_status_bar([_stub_invoice_line(kolicina=10.4)])

    FakturaView._update_status_bar(mock_self)

    text = mock_self.lbl_total_quantity.setText.call_args[0][0]
    assert text == "📦 Komada: 10"


def test_update_status_bar_ukljucuje_analysis_summary_latch_kad_ima_stavki():
    """
    Regresija (korisnička prijava, screenshot statusne trake): ručni uvoz
    nikad nije prikazivao 🌍 podjelu po zemljama jer se _analysis_summary_auto
    postavljao SAMO iz AgentController-a nakon Agent uvoza. _update_status_bar
    sad jednosmjerno uključuje taj flag čim ima bar jedna stavka u draftu —
    bez obzira na to kako je stavka stigla (ručni uvoz, Agent uvoz, ručni unos).
    """
    mock_self = _mock_self_for_status_bar([_stub_invoice_line(zemlja_porijekla="DE")])
    mock_self._analysis_summary_auto = False

    FakturaView._update_status_bar(mock_self)

    assert mock_self._analysis_summary_auto is True
    mock_self._refresh_analysis_summary_from_draft.assert_called_once()


def test_update_status_bar_prazan_draft_ne_ukljucuje_latch():
    """Prazan draft ne smije uključiti latch — nema šta prikazati."""
    mock_self = _mock_self_for_status_bar([])
    mock_self._analysis_summary_auto = False

    FakturaView._update_status_bar(mock_self)

    assert mock_self._analysis_summary_auto is False


def test_update_status_bar_ne_iskljucuje_vec_ukljucen_latch():
    """Latch je jednosmjeran — ako je već True (npr. iz ranijeg Agent uvoza), ostaje True."""
    mock_self = _mock_self_for_status_bar([_stub_invoice_line()])
    mock_self._analysis_summary_auto = True

    FakturaView._update_status_bar(mock_self)

    assert mock_self._analysis_summary_auto is True


def test_update_status_bar_assembly_status_dolazi_iz_controllera():
    mock_self = _mock_self_for_status_bar([_stub_invoice_line()])
    mock_self._assembly_completion_status_for_status_bar.return_value = {
        "completion_percentage": 50.0,
        "imported_invoices_count": 2,
    }

    FakturaView._update_status_bar(mock_self)

    mock_self.lbl_assembly.setText.assert_called_with("⚠️ 50% (2 faktura)")


def test_assembly_status_helper_koristi_controller():
    mock_self = MagicMock()
    mock_self.controller.assembly_completion_status.return_value = {
        "completion_percentage": 100.0,
        "imported_invoices_count": 3,
    }

    status = FakturaView._assembly_completion_status_for_status_bar(mock_self)

    assert status == {"completion_percentage": 100.0, "imported_invoices_count": 3}
    mock_self.controller.assembly_completion_status.assert_called_once()


def test_analysis_summary_prikazuje_breakdown_po_zemlji_ne_samo_broj():
    """
    Regresija iz komita 735400a ("sažmi statusnu traku") je zamijenila
    breakdown ("DE:9 | IT:8") sa golim brojem ("9 zemalja") - korisnik je
    eksplicitno trazio da se breakdown vrati.
    """
    mock_self = MagicMock()
    mock_self.table = None
    lines = (
        [_stub_invoice_line(zemlja_porijekla="DE") for _ in range(9)]
        + [_stub_invoice_line(zemlja_porijekla="IT") for _ in range(8)]
    )
    mock_self.draft.invoice_lines = lines

    text, level = FakturaView._build_analysis_summary_from_draft(mock_self)

    assert "DE:9" in text
    assert "IT:8" in text
    assert "zemalja" not in text
    assert level == "success"
