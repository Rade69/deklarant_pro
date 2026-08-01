"""
Testovi za selekcijsko skopiranje opšte validacije (_validate_all_items, 2026-07-22).

Prije ove izmjene je "Provjeri" scopirao SAMO istorijsku tarifnu provjeru na
selekciju (vidi test_faktura_view_provjeri_selekcija.py) — opšta validacija
(broj grešaka/upozorenja u sažetku) je uvijek prijavljivala stanje SVIH
stavki na fakturi, čak i kad je korisnik selektovao konkretne redove. Ovo je
dopunjeno da bude konzistentno: sažetak/brojevi se odnose SAMO na selekciju
kad je aktivna, dok bojenje redova ostaje na SVIM redovima (jeftino,
održava tabelu vizuelno ažurnom).

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.tabs.faktura_view import FakturaView


def _validation_result(has_errors: bool = False, has_warnings: bool = False, valid: bool = True):
    result = MagicMock()
    result.has_blocking_errors.return_value = has_errors
    result.warnings = ["upozorenje"] if has_warnings else []
    result.valid = valid
    return result


def _mock_self_with_selection(num_lines: int, selected_rows: list[int]) -> MagicMock:
    mock_self = MagicMock()
    mock_self.draft.invoice_lines = [MagicMock() for _ in range(num_lines)]
    mock_self.table.rowCount.return_value = num_lines

    row_mocks = []
    for row in selected_rows:
        idx = MagicMock()
        idx.row.return_value = row
        row_mocks.append(idx)
    mock_self.table.selectionModel.return_value.selectedRows.return_value = row_mocks

    mock_self._validation_issue_counts.return_value = ({}, {})
    mock_self._run_historical_tariff_validation.return_value = None
    return mock_self


def test_validation_issue_counts_scoped_na_row_indexes():
    mock_self = MagicMock()
    mock_self.draft.invoice_lines = [MagicMock() for _ in range(5)]

    error_result = _validation_result(has_errors=True)
    ok_result = _validation_result()

    def fake_get(row):
        return error_result if row == 1 else ok_result

    mock_self.validation_cache.get.side_effect = fake_get
    mock_self._validation_issue_label.return_value = "greska"
    error_result.errors = [MagicMock(field="tarifni_broj", message="obavezan")]
    ok_result.errors = []

    errors, warnings = FakturaView._validation_issue_counts(mock_self, [1, 3])

    # Samo redovi 1 i 3 su provjereni - validation_cache.get pozvan tacno 2x
    assert mock_self.validation_cache.get.call_count == 2
    assert errors.get("greska") == 1


def test_validate_all_items_broji_samo_selektovane_stavke():
    """
    5 stavki, selektovani redovi [1, 3]: red 1 ima blokirajucu gresku,
    red 3 ima upozorenje. Sazetak mora prijaviti error_count=1,
    warning_count=1, total_count=2 (NE 5) - iako redovi 0/2/4 (van
    selekcije) takodje imaju gresku u cache-u.
    """
    mock_self = _mock_self_with_selection(num_lines=5, selected_rows=[1, 3])

    def fake_get(row):
        if row == 1:
            return _validation_result(has_errors=True)
        if row == 3:
            return _validation_result(has_warnings=True, valid=False)
        # Redovi van selekcije - namjerno "gresni" da dokazu da se NE racunaju
        return _validation_result(has_errors=True)

    mock_self.validation_cache.get.side_effect = fake_get

    with patch("gui.tabs.faktura_view.QMessageBox"):
        ok, error_count, warning_count = FakturaView._validate_all_items(mock_self, auto=False)

    assert ok is True
    assert error_count == 1
    assert warning_count == 1

    mock_self._validation_issue_counts.assert_called_once_with([1, 3])
    message = mock_self.error_handler.method_calls  # nije koristen (nema izuzetka)
    assert message == []


def test_validate_all_items_bez_selekcije_broji_sve_stavke():
    """Bez selekcije (staro ponasanje) - koristi se globalni validation_cache brojac."""
    mock_self = _mock_self_with_selection(num_lines=3, selected_rows=[])
    mock_self.validation_cache.get_error_count.return_value = 2
    mock_self.validation_cache.get_warning_count.return_value = 1
    mock_self.validation_cache.get_valid_count.return_value = 0

    with patch("gui.tabs.faktura_view.QMessageBox"):
        ok, error_count, warning_count = FakturaView._validate_all_items(mock_self, auto=False)

    assert ok is True
    assert error_count == 2
    assert warning_count == 1
    mock_self._validation_issue_counts.assert_called_once_with(None)
