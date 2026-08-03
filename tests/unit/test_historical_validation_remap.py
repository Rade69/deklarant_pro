"""
Karakterizacioni testovi za HistoricalValidationWorker.remap_local_indices()
— Faza 7c (2026-08-02), izdvojeno iz FakturaView._on_historical_validation_finished
(KRITIČNO: match.line_index i auto_applied/auto_rejected indeksi su pozicije
UNUTAR target_lines, ne stvarni red u draft.invoice_lines — bez remapiranja
promjena se upisuje u POGREŠAN red, vidi
tests/unit/test_faktura_view_provjeri_selekcija.py i
project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md).
"""
from unittest.mock import MagicMock

from services.historical_validation_worker import remap_local_indices


def _match(line_index: int):
    m = MagicMock()
    m.line_index = line_index
    return m


def test_row_indexes_none_vraca_ulaze_nepromijenjene():
    matches = [_match(0)]
    auto_applied = [(0, "85168080")]
    auto_rejected = [(1, "39269097")]

    r_matches, r_applied, r_rejected = remap_local_indices(matches, auto_applied, auto_rejected, None)

    assert r_matches is matches
    assert r_applied is auto_applied
    assert r_rejected is auto_rejected


def test_match_line_index_remapiran_na_stvarni_red():
    match = _match(1)  # lokalni indeks: pozicija unutar target_lines=[red1, red3]
    remap_local_indices([match], [], [], row_indexes=[1, 3])
    assert match.line_index == 3


def test_auto_applied_remapiran_na_stvarni_red():
    _, applied, _ = remap_local_indices([], [(0, "85168080")], [], row_indexes=[3])
    assert applied == [(3, "85168080")]


def test_auto_rejected_remapiran_na_stvarni_red():
    _, _, rejected = remap_local_indices([], [], [(0, "39269097")], row_indexes=[3])
    assert rejected == [(3, "39269097")]


def test_van_opsega_lokalni_indeks_se_preskace():
    _, applied, _ = remap_local_indices([], [(0, "x"), (5, "y")], [], row_indexes=[3])
    assert applied == [(3, "x")]


def test_match_van_opsega_line_index_ostaje_nepromijenjen():
    match = _match(5)
    remap_local_indices([match], [], [], row_indexes=[3])
    assert match.line_index == 5


def test_originalne_liste_se_ne_mijenjaju_u_mjestu():
    """auto_applied/auto_rejected vracaju se kao NOVE liste - originalne liste
    (koje worker/signal proslijedi) ostaju netaknute."""
    original_applied = [(0, "85168080")]
    _, remapped, _ = remap_local_indices([], original_applied, [], row_indexes=[3])
    assert original_applied == [(0, "85168080")]
    assert remapped == [(3, "85168080")]
