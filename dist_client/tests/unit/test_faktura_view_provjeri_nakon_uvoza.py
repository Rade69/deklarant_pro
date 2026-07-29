"""
Testovi za automatski poziv istorijske tarifne provjere ODMAH nakon uvoza
fakture (2026-07-22).

Korisnička primjedba (SUSSINA slučaj): pogrešna tarifa se lako provuče ako
se čeka na ručni klik "Provjeri" nakon uvoza — korisnik pređe dalje i
zaboravi kliknuti. Odlučeno (uz eksplicitnu korisnikovu potvrdu): ponovo
iskoristiti POSTOJEĆI _run_historical_tariff_validation (isti kod kao ručni
klik "Provjeri") automatski na kraju uvoza, umjesto da se čeka klik.

ISPRAVKA (isti dan): prvobitna verzija je preskakala poziv kad je
self._agent_mode aktivan, pod pretpostavkom da puna automatizacija
(import_pipeline_service._puna_auto_pipeline) uvijek sama pokrene
_on_validate_all(auto=True) kasnije. Korisnik je testirao uvoz kroz agent
mod (rutu "Uvezi u deklaraciju", NE "Puna automatizacija") i dobio potpunu
tišinu — self._agent_mode je aktivan za SVE tri agent rute uvoza ("Analiza",
"Uvezi u deklaraciju", "Puna automatizacija"), a samo "Puna automatizacija"
ima taj naknadni poziv. Fix: poziv se sad IZVRŠAVA UVIJEK, bez obzira na
agent_mode — _puna_auto_pipeline se pokreće odvojeno i kasnije (radi na već
uvezenom draft-u, ne uvozi sam), a njegov auto=True poziv ostaje tih (samo
log) bez obzira da li je ovaj eager poziv već nešto prikazao, pa nema
stvarnog preklapanja/duplikata.

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.draft.draft import DeclarationDraft, InvoiceLine
from gui.tabs.faktura_view import FakturaView
from importers.import_result import ImportResult


def _mock_self_for_import_finished(agent_mode: bool) -> MagicMock:
    mock_self = MagicMock()
    mock_self._agent_mode = agent_mode
    mock_self.draft.invoice_lines = []
    mock_self.assembly.master_list_loaded = False

    items = [MagicMock(naziv_robe="SUSSINA 650 tbl.", tarifni_broj="")]
    mock_self._extract_import_result_data.return_value = (
        items, 0.0, 0.0, "faktura1.pdf", False, "invoice", False, False,
        "IZVOZNIK", "UVOZNIK",
    )
    mock_self._get_invoice_name.return_value = "faktura1.pdf"
    mock_self._check_partner_consistency.return_value = True
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._append_imported_files_message.side_effect = lambda msg, min_files=1: msg
    mock_self._auto_handle_povlastice_agent.return_value = {"pe2": 0, "eur1_pending": 0}
    mock_self.weight_manager.accumulated_bruto_kg = 0.0
    mock_self.weight_manager.accumulated_neto_kg = 0.0
    mock_self.on_dirty = None
    return mock_self


def test_uvoz_pojedinacne_fakture_pokrece_provjeru_bez_agent_moda():
    mock_self = _mock_self_for_import_finished(agent_mode=False)

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound"
    ) as play_sound:
        FakturaView._on_import_finished(mock_self, [])

    mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)
    play_sound.assert_called_once_with("success")


def test_uvoz_pojedinacne_fakture_pokrece_provjeru_i_u_agent_modu():
    """
    Regresija: self._agent_mode=True ne znači da je "Puna automatizacija"
    pipeline u toku - agent_mode je aktivan i za "Uvezi u deklaraciju" rutu,
    koja NEMA naknadni poziv. Provjera mora raditi u SVIM agent rutama.
    """
    mock_self = _mock_self_for_import_finished(agent_mode=True)

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound"
    ):
        FakturaView._on_import_finished(mock_self, [])

    mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


def test_zvuk_se_cuje_prije_eur1_dijaloga():
    mock_self = _mock_self_for_import_finished(agent_mode=False)
    mock_self._should_show_eur1_dialog.return_value = True
    events = []
    mock_self._show_eur1_dialog.side_effect = lambda: events.append("eur1")

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound",
        side_effect=lambda outcome: events.append(f"sound:{outcome}"),
    ):
        FakturaView._on_import_finished(mock_self, [])

    assert events[:2] == ["sound:success", "eur1"]


def _mock_self_for_batch_records(agent_mode: bool) -> MagicMock:
    mock_self = MagicMock()
    mock_self._agent_mode = agent_mode
    mock_self._batch_failed = []
    mock_self.assembly.master_list_loaded = False
    mock_self.draft = DeclarationDraft()
    mock_self.imported_excel_count = 0
    mock_self.imported_pdf_count = 0
    mock_self._postprocess_master_frigo_pairs_records.return_value = None
    mock_self._normalize_item_tariffs.return_value = None
    mock_self._distribute_invoice_weights.return_value = None
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._offer_split_by_country.return_value = None
    mock_self.on_dirty = None
    return mock_self


def _batch_records():
    result = ImportResult(
        items=[
            InvoiceLine(
                invoice_number="faktura1.pdf",
                naziv_robe="SUSSINA 650 tbl.",
                tarifni_broj="",
            )
        ],
        invoice_name="faktura1.pdf",
    )
    return [{
        "skipped": False,
        "items": result.items,
        "bruto_kg": 0.0,
        "neto_kg": 0.0,
        "invoice_name": "faktura1.pdf",
        "filepath": "faktura1.pdf",
        "parser_warnings": [],
        "_import_result": result,
    }]


def test_grupni_uvoz_pokrece_provjeru_bez_agent_moda():
    mock_self = _mock_self_for_batch_records(agent_mode=False)

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound"
    ):
        FakturaView._process_batch_records(mock_self, _batch_records())

    mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


def test_grupni_uvoz_pokrece_provjeru_i_u_agent_modu():
    mock_self = _mock_self_for_batch_records(agent_mode=True)

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound"
    ):
        FakturaView._process_batch_records(mock_self, _batch_records())

    mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


def test_grupni_uvoz_sa_glavnom_listom_ima_zvuk_zavrsetka():
    mock_self = _mock_self_for_batch_records(agent_mode=False)
    mock_self.assembly.master_list_loaded = True

    with patch("gui.tabs.faktura_view.QMessageBox"), patch(
        "services.process_completion_sound.play_process_completion_sound"
    ) as play_sound:
        FakturaView._process_batch_records(mock_self, _batch_records())

    play_sound.assert_called_once_with("success")
