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

    mock_self._show_tariff_table_info_dialog.assert_called_once()
    title, intro_html, rows = mock_self._show_tariff_table_info_dialog.call_args[0]
    assert title == "Automatski ažurirane tarife (ranija potvrda)"
    assert "RANIJE RUČNO potvrdili" in intro_html
    assert len(rows) == 1
    assert rows[0]["rb"] == 1
    assert rows[0]["naziv"] == "GREJAC KVARCNI 1000W"
    assert rows[0]["tarif"] == "85168080"
    # Opis tarife (korisnička primjedba 2026-07-21/26): dijalog mora nositi
    # opis nove tarife, ne samo goli kod — deklarant ga inače mora sam tražiti.
    assert "opis" in rows[0]
    mock_self._get_tariff_description.assert_called_once_with("85168080")


def test_notify_nabraja_sve_auto_primijenjene_stavke():
    mock_self = _mock_self_with_lines({0: "STAVKA A", 2: "STAVKA C"})

    FakturaView._notify_auto_applied_tariffs(mock_self, [(0, "11112222"), (2, "33334444")])

    _, intro_html, rows = mock_self._show_tariff_table_info_dialog.call_args[0]
    assert rows == [
        {
            "rb": 1,
            "naziv": "STAVKA A",
            "tarif": "11112222",
            "izvor": "Ranija ručna potvrda (100%)",
            "opis": mock_self._get_tariff_description.return_value,
        },
        {
            "rb": 3,
            "naziv": "STAVKA C",
            "tarif": "33334444",
            "izvor": "Ranija ručna potvrda (100%)",
            "opis": mock_self._get_tariff_description.return_value,
        },
    ]
    assert "2" in intro_html  # broj auto-primijenjenih stavki spomenut u poruci
