"""
Test za FakturaView._notify_auto_rejected_tariffs (2026-07-22).

Simetrično sa test_faktura_view_auto_applied_notice.py: kad se istorijski
prijedlog PRESKOČI zbog ranije eksplicitne odluke "Odbij" u 'Provjeri'
dijalogu, to se ranije dešavalo potpuno tiho — korisnik nikad nije vidio
DA je nešto preskočeno niti ZAŠTO (mogla se lako protumačiti kao "nema
prijedloga" umjesto "prijedlog postoji, ali ste ga ranije odbili").

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog FakturaView-a (Qt tabela, DB konekcije, itd.).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gui.tabs.faktura_view import FakturaView


def _mock_self_with_lines(nazivi: dict[int, str]) -> MagicMock:
    mock_self = MagicMock()
    lines = {}
    for idx, naziv in nazivi.items():
        line = MagicMock()
        line.naziv_robe = naziv
        lines[idx] = line
    max_idx = max(nazivi.keys(), default=-1)
    invoice_lines = [lines.get(i, MagicMock(naziv_robe="")) for i in range(max_idx + 1)]
    mock_self.draft.invoice_lines = invoice_lines
    return mock_self


def test_notify_navodi_da_je_ranija_odluka_odbij_razlog():
    mock_self = _mock_self_with_lines({0: "OHP SILICON CEPOVI ZA USI a6"})

    FakturaView._notify_auto_rejected_tariffs(mock_self, [(0, "39269097")])

    mock_self._show_scrollable_info_dialog.assert_called_once()
    title, text = mock_self._show_scrollable_info_dialog.call_args[0]
    assert "RANIJE EKSPLICITNO ODBILI" in text
    assert "Rb.1" in text
    assert "OHP SILICON CEPOVI ZA USI a6" in text
    assert "39269097" in text


def test_notify_nabraja_sve_odbijene_stavke():
    mock_self = _mock_self_with_lines({0: "STAVKA A", 2: "STAVKA C"})

    FakturaView._notify_auto_rejected_tariffs(mock_self, [(0, "11112222"), (2, "33334444")])

    _, text = mock_self._show_scrollable_info_dialog.call_args[0]
    assert "Rb.1: STAVKA A (bio bi predložen: 11112222)" in text
    assert "Rb.3: STAVKA C (bio bi predložen: 33334444)" in text
    assert "2" in text
