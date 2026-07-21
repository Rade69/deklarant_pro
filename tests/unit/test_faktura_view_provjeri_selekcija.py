"""
Test za FakturaView._run_historical_tariff_validation — selekcija redova (2026-07-21).

Korisnička primjedba: kad selektuje N stavki u tabeli i klikne "Provjeri"
(dugme pored Bruto/Neto), očekuje da se provjere SAMO te stavke — isti
obrazac kao Auto-popuni. Prije ove izmjene se uvijek provjeravalo SVIH
draft.invoice_lines, bez obzira na selekciju.

Ovaj test pokriva i kritičan detalj: HistoricalTariffSearchService.validate_lines
vraća line_index kao POZICIJU unutar liste koja joj je proslijeđena (0..N-1
filtrirane selekcije), ne kao stvarni red u draft.invoice_lines. Bez remapiranja
nazad na pravi red, promjena bi se upisala u POGREŠAN red tabele — tačno
simptom koji je korisnik prijavio ("tarifni brojevi koji su došli iz fakture
su i dalje tu").

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.tabs.faktura_view import FakturaView


def _line(tarifni_broj: str = "", naziv: str = "STAVKA") -> MagicMock:
    line = MagicMock()
    line.tarifni_broj = tarifni_broj
    line.naziv_robe = naziv
    return line


def _mock_self_with_selected_rows(num_lines: int, selected_rows: list[int]) -> MagicMock:
    mock_self = MagicMock()
    mock_self.draft.invoice_lines = [_line(naziv=f"STAVKA {i}") for i in range(num_lines)]

    row_mocks = []
    for row in selected_rows:
        idx = MagicMock()
        idx.row.return_value = row
        row_mocks.append(idx)
    mock_self.table.selectionModel.return_value.selectedRows.return_value = row_mocks
    return mock_self


def test_provjeri_selekcija_provjerava_samo_selektovane_redove():
    """Sa 5 stavki i selektovanim redom 3, servis mora dobiti listu od SAMO 1 stavke."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])

    svc_instance = MagicMock()
    svc_instance.validate_lines.return_value = []
    svc_instance.last_auto_applied = []

    with patch(
        "services.agent.validation.historical_tariff_search_service.HistoricalTariffSearchService",
        return_value=svc_instance,
    ):
        FakturaView._run_historical_tariff_validation(mock_self, auto=False)

    called_lines = svc_instance.validate_lines.call_args[0][0]
    assert called_lines == [mock_self.draft.invoice_lines[3]]


def test_provjeri_selekcija_remapira_auto_applied_na_pravi_red():
    """
    auto_applied vraća lokalni indeks (0, jer je proslijeđena samo 1 stavka) —
    mora se remapirati na stvarni red (3) prije upisa u tabelu/draft/notifikaciju.
    """
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[3])

    svc_instance = MagicMock()
    svc_instance.validate_lines.return_value = []
    svc_instance.last_auto_applied = [(0, "85168080")]  # lokalni indeks unutar target_lines

    with patch(
        "services.agent.validation.historical_tariff_search_service.HistoricalTariffSearchService",
        return_value=svc_instance,
    ):
        FakturaView._run_historical_tariff_validation(mock_self, auto=False)

    # Mora upisati u PRAVI red (3), ne u lokalni indeks (0)
    mock_self._set_table_item.assert_called_once_with(3, 4, "85168080", align=mock_self._set_table_item.call_args.kwargs.get("align"))
    row_arg = mock_self._set_table_item.call_args[0][0]
    assert row_arg == 3

    mock_self._validate_and_color_row.assert_called_once()
    color_row_arg = mock_self._validate_and_color_row.call_args[0][0]
    assert color_row_arg == 3

    mock_self._notify_auto_applied_tariffs.assert_called_once_with([(3, "85168080")])


def test_provjeri_bez_selekcije_provjerava_sve_stavke():
    """Bez selekcije (stari obrazac) - ponašanje ostaje nepromijenjeno, provjeravaju se sve stavke."""
    mock_self = _mock_self_with_selected_rows(num_lines=3, selected_rows=[])

    svc_instance = MagicMock()
    svc_instance.validate_lines.return_value = []
    svc_instance.last_auto_applied = []

    with patch(
        "services.agent.validation.historical_tariff_search_service.HistoricalTariffSearchService",
        return_value=svc_instance,
    ):
        FakturaView._run_historical_tariff_validation(mock_self, auto=False)

    called_lines = svc_instance.validate_lines.call_args[0][0]
    assert called_lines == mock_self.draft.invoice_lines


def test_provjeri_match_line_index_remapiran_na_pravi_red():
    """match.line_index (lokalni, iz validate_lines) mora biti remapiran prije nego stigne do dijaloga."""
    mock_self = _mock_self_with_selected_rows(num_lines=5, selected_rows=[1, 3])

    match = MagicMock()
    match.line_index = 1  # lokalni indeks: pozicija reda 3 unutar target_lines=[red1, red3]

    svc_instance = MagicMock()
    svc_instance.validate_lines.return_value = [match]
    svc_instance.last_auto_applied = []

    with patch(
        "services.agent.validation.historical_tariff_search_service.HistoricalTariffSearchService",
        return_value=svc_instance,
    ), patch("gui.tabs.agent.widgets.tariff_validation_dialog.TariffValidationDialog") as dlg_cls, \
         patch("gui.tabs.faktura_view.show_dialog_preserving_geometry"):
        FakturaView._run_historical_tariff_validation(mock_self, auto=False)

    # target_lines = [invoice_lines[1], invoice_lines[3]]; match.line_index=1 -> stvarni red 3
    assert match.line_index == 3
    dlg_cls.assert_called_once()
