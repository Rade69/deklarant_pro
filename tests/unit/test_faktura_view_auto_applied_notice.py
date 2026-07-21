"""
Test za FakturaView._notify_auto_applied_tariffs (2026-07-21).

Korisnička primjedba: kad se tarifa automatski upiše zbog RANIJE ručne
potvrde (user_feedback), to se ranije dešavalo potpuno tiho — korisnik
nikad nije vidio DA se nešto promijenilo niti ZAŠTO (a jedna ranija ljudska
odluka, ako je bila pogrešna, se od tad ponavlja bez ikad ponovnog
pregleda — isti obrazac kao poznat bug GREJAC SPIRALA/Plamenik).

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
    # invoice_lines mora podržati indeksiranje kao lista (idx < len(...))
    max_idx = max(nazivi.keys(), default=-1)
    invoice_lines = [lines.get(i, MagicMock(naziv_robe="")) for i in range(max_idx + 1)]
    mock_self.draft.invoice_lines = invoice_lines
    return mock_self


def test_notify_navodi_da_je_ranija_rucna_potvrda_razlog():
    mock_self = _mock_self_with_lines({0: "GREJAC KVARCNI 1000W"})

    FakturaView._notify_auto_applied_tariffs(mock_self, [(0, "85168080")])

    mock_self._show_scrollable_info_dialog.assert_called_once()
    title, text = mock_self._show_scrollable_info_dialog.call_args[0]
    assert "RANIJE RUČNO potvrdili" in text
    assert "Rb.1" in text
    assert "GREJAC KVARCNI 1000W" in text
    assert "85168080" in text


def test_notify_nabraja_sve_auto_primijenjene_stavke():
    mock_self = _mock_self_with_lines({0: "STAVKA A", 2: "STAVKA C"})

    FakturaView._notify_auto_applied_tariffs(mock_self, [(0, "11112222"), (2, "33334444")])

    _, text = mock_self._show_scrollable_info_dialog.call_args[0]
    assert "Rb.1: STAVKA A → 11112222" in text
    assert "Rb.3: STAVKA C → 33334444" in text
    assert "2" in text  # broj auto-primijenjenih stavki spomenut u poruci
