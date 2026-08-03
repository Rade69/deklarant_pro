"""
Test za FakturaView._run_historical_tariff_validation — selekcija redova (2026-07-21).

Korisnička primjedba: kad selektuje N stavki u tabeli i klikne "Provjeri"
(dugme pored Bruto/Neto), očekuje da se provjere SAMO te stavke — isti
obrazac kao Auto-popuni. Prije ove izmjene se uvijek provjeravalo svih
draft.invoice_lines, bez obzira na selekciju.

Ovaj test pokriva i kritičan detalj: HistoricalTariffSearchService.validate_lines
vraća line_index kao POZICIJU unutar liste koja joj je proslijeđena (0..N-1
filtrirane selekcije), ne kao stvarni red u draft.invoice_lines. Bez remapiranja
nazad na pravi red, promjena bi se upisala u POGREŠAN red tabele — tačno
simptom koji je korisnik prijavio ("tarifni brojevi koji su došli iz fakture
su i dalje tu").

AŽURIRANO (§59, HistoricalValidationWorker): _run_historical_tariff_validation
sad samo priprema target_lines/selekciju i DISPATCHUJE pozadinski worker
(_dispatch_worker ispod patchuje worker.start() na no-op da se pravi
QThread nikad ne pokrene — race-free provjera argumenata konstrukcije).
Logika remapiranja/notifikacije/dijaloga je premještena u
_on_historical_validation_finished i testira se direktno, odvojeno od
dispatch-a — worker sad radi taj posao asinhrono, testovi ne čekaju thread.

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.tabs.faktura_view import FakturaView
from services.historical_validation_worker import HistoricalValidationWorker


def _line(tarifni_broj: str = "", naziv: str = "STAVKA") -> MagicMock:
    line = MagicMock()
    line.tarifni_broj = tarifni_broj
    line.naziv_robe = naziv
    return line


def _mock_self_with_selected_rows(num_lines: int, selected_rows: list[int]) -> MagicMock:
    mock_self = MagicMock()
    mock_self.draft.invoice_lines = [_line(naziv=f"STAVKA {i}") for i in range(num_lines)]
    mock_self.historical_validation_worker = None

    row_mocks = []
    for row in selected_rows:
        idx = MagicMock()
        idx.row.return_value = row
        row_mocks.append(idx)
    mock_self.table.selectionModel.return_value.selectedRows.return_value = row_mocks
    return mock_self


def _dispatch_worker(mock_self, auto: bool = False) -> HistoricalValidationWorker:
    """
    Pokreni _run_historical_tariff_validation sa worker.start() patchovanim na
    no-op — vraća stvarni (ali nikad pokrenut) HistoricalValidationWorker da
    se provjere argumenti konstrukcije bez čekanja na pravi QThread/DB poziv.
    """
    with patch.object(HistoricalValidationWorker, "start", lambda self: None):
        FakturaView._run_historical_tariff_validation(mock_self, auto=auto)
    return mock_self.historical_validation_worker


def test_provjeri_selekcija_provjerava_samo_selektovane_redove():
    """Sa 5 stavki i selektovanim redom 3, worker mora dobiti listu od SAMO 1 stavke."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])
    worker = _dispatch_worker(mock_self)
    assert worker.target_lines == [mock_self.draft.invoice_lines[3]]


def test_provjeri_bez_selekcije_provjerava_sve_stavke():
    """Bez selekcije (stari obrazac) - ponašanje ostaje nepromijenjeno, provjeravaju se sve stavke."""
    mock_self = _mock_self_with_selected_rows(num_lines=3, selected_rows=[])
    worker = _dispatch_worker(mock_self)
    assert worker.target_lines == mock_self.draft.invoice_lines


def test_provjeri_bez_stavki_ne_pokrece_worker():
    """Prazan draft (ili prazna selekcija filtrirana na 0 stavki) ne smije pokrenuti worker."""
    mock_self = _mock_self_with_selected_rows(num_lines=0, selected_rows=[])
    worker = _dispatch_worker(mock_self)
    assert worker is None


def _finish(mock_self, **overrides):
    """Pozovi _on_historical_validation_finished sa razumnim defaultima."""
    kwargs = dict(
        matches=[],
        auto_applied=[],
        auto_rejected=[],
        row_indexes=None,
        auto=False,
        modal=False,
        token=mock_self._historical_validation_token,
        generation=mock_self._validation_generation,
    )
    kwargs.update(overrides)
    FakturaView._on_historical_validation_finished(mock_self, **kwargs)


def test_provjeri_selekcija_remapira_auto_applied_na_pravi_red():
    """
    auto_applied vraća lokalni indeks (0, jer je proslijeđena samo 1 stavka) —
    mora se remapirati na stvarni red (3) prije upisa u tabelu/draft/notifikaciju.
    """
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])

    _finish(
        mock_self,
        auto_applied=[(0, "85168080")],  # lokalni indeks unutar target_lines=[red3]
        row_indexes=[3],
    )

    row_arg = mock_self._set_table_item.call_args[0][0]
    assert row_arg == 3

    mock_self._validate_and_color_row.assert_called_once()
    color_row_arg = mock_self._validate_and_color_row.call_args[0][0]
    assert color_row_arg == 3

    mock_self._notify_auto_applied_tariffs.assert_called_once_with([(3, "85168080")])


def test_provjeri_selekcija_auto_applied_upisuje_tarifu_u_draft():
    """KRITIČNO (bug pronađen 2026-08-02, offscreen probe na stvarno
    instanciranom FakturaTab-u): auto_applied petlja poziva _set_table_item
    (mijenja SAMO Qt ćeliju) i _validate_and_color_row, ali NIKAD ne piše
    tarifni_broj u draft.invoice_lines[idx] — za razliku od _on_accepted
    closure-a (dijalog-potvrda putanja), koja to ispravno radi. Rezultat:
    korisnik vidi novi tarifni broj u tabeli, ali export/Kreiraj naimenovanja
    (koji čitaju draft, ne Qt tabelu) i dalje koriste STARU vrijednost.
    Ovaj test bi FAILOVAO na kodu prije fixa jer mock InvoiceLine objekti
    zadržavaju originalnu vrijednost postavljenu u _line() helperu."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])

    _finish(
        mock_self,
        auto_applied=[(0, "85168080")],
        row_indexes=[3],
    )

    assert mock_self.draft.invoice_lines[3].tarifni_broj == "85168080"


def test_provjeri_match_line_index_remapiran_na_pravi_red():
    """match.line_index (lokalni, iz validate_lines) mora biti remapiran prije nego stigne do dijaloga."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[1, 3])

    match = MagicMock()
    match.line_index = 1  # lokalni indeks: pozicija reda 3 unutar target_lines=[red1, red3]

    with patch(
        "gui.tabs.agent.widgets.tariff_validation_dialog.TariffValidationDialog"
    ) as dlg_cls, patch("gui.tabs.faktura_view.show_dialog_preserving_geometry"):
        _finish(
            mock_self,
            matches=[match],
            row_indexes=[1, 3],  # target_lines = [invoice_lines[1], invoice_lines[3]]
        )

    # match.line_index=1 -> stvarni red 3
    assert match.line_index == 3
    dlg_cls.assert_called_once()


def test_provjeri_selekcija_bez_prijedloga_prikazuje_poruku_umjesto_tisine():
    """
    Prije ove izmjene je "nema prijedloga" bilo POTPUNO tiho — kad korisnik
    eksplicitno selektuje stavke i klikne "Provjeri", tišina se lako
    protumači kao da dijalog "nije htio" da se otvori (korisnička primjedba
    2026-07-21). Bez selekcije tišina ostaje namjerna (provjereno niže).
    """
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[2])

    with patch("gui.tabs.faktura_view.QMessageBox") as mock_msgbox:
        _finish(mock_self, row_indexes=[2])

    mock_msgbox.information.assert_called_once()
    message_text = mock_msgbox.information.call_args[0][2]
    assert "1 selektovan" in message_text


def test_provjeri_bez_selekcije_bez_prijedloga_ostaje_tih():
    """Bez selekcije (provjera cijele fakture) tisina ostaje namjerna - nema poruke po svakom kliku."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[])

    with patch("gui.tabs.faktura_view.QMessageBox") as mock_msgbox:
        _finish(mock_self, row_indexes=None)

    mock_msgbox.information.assert_not_called()


def test_provjeri_selekcija_remapira_auto_rejected_na_pravi_red():
    """
    Simetrično sa auto_applied remapiranjem: auto_rejected vraća lokalni
    indeks (0, pozicija unutar target_lines) - mora se remapirati na
    stvarni red (3) prije notifikacije.
    """
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])

    _finish(
        mock_self,
        auto_rejected=[(0, "39269097")],  # lokalni indeks unutar target_lines
        row_indexes=[3],
    )

    mock_self._notify_auto_rejected_tariffs.assert_called_once_with([(3, "39269097")])


def test_provjeri_selekcija_auto_rejected_suprimira_generalnu_poruku():
    """
    Kad postoji auto_rejected, generalna "nema boljeg prijedloga" poruka se
    NE prikazuje - specifičnija poruka (_notify_auto_rejected_tariffs) je
    dovoljna i tačnija (razlog je poznat: ranija odluka "Odbij", ne
    odsustvo bilo kakvog istorijskog traga).
    """
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[2])

    with patch("gui.tabs.faktura_view.QMessageBox") as mock_msgbox:
        _finish(mock_self, auto_rejected=[(0, "39269097")], row_indexes=[2])

    mock_self._notify_auto_rejected_tariffs.assert_called_once()
    mock_msgbox.information.assert_not_called()


def test_provjeri_auto_mod_loguje_auto_rejected_umjesto_dijaloga():
    """auto=True (puna automatizacija): auto_rejected se samo loguje, nikad dijalog."""
    mock_self = _mock_self_with_selected_rows(num_lines=3, selected_rows=[])

    _finish(
        mock_self,
        auto=True,
        auto_rejected=[(0, "39269097")],
        row_indexes=None,
    )

    mock_self._notify_auto_rejected_tariffs.assert_not_called()
