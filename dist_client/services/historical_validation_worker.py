# services/historical_validation_worker.py

"""
Deklarant Pro - Historical Validation Worker (Threading)
Non-blocking istorijska validacija tarifnih brojeva za PySide6 Qt aplikaciju.
"""

import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("deklarant_pro.faktura.historical_validation_worker")


def remap_local_indices(matches: list, auto_applied: list, auto_rejected: list, row_indexes) -> tuple:
    """Remapira lokalne indekse (pozicije unutar target_lines) na stvarne
    redove u draft.invoice_lines.

    KRITIČNO: match.line_index i auto_applied/auto_rejected indeksi su
    pozicije UNUTAR target_lines (0..len(target_lines)-1) koju je Faktura
    view proslijedila workeru, ne stvarni red u draft.invoice_lines — kad
    je target_lines filtrirana selekcija, indeks mora nazad na pravi red
    prije upisa u tabelu/draft, inače se promjena upiše u POGREŠAN red
    (vidi tests/unit/test_faktura_view_provjeri_selekcija.py).

    `matches` se mutira u mjestu (isto ponašanje kao prije ekstrakcije —
    match objekti su prosljeđeni dalje u dijalog); auto_applied/auto_rejected
    se vraćaju kao NOVE liste, originalne ostaju netaknute. Kad je
    row_indexes None (provjera cijele fakture, bez selekcije), indeksi su
    već stvarni redovi — ulazi se vraćaju nepromijenjeni.
    """
    if row_indexes is None:
        return matches, auto_applied, auto_rejected
    for match in matches:
        if 0 <= match.line_index < len(row_indexes):
            match.line_index = row_indexes[match.line_index]
    auto_applied = [
        (row_indexes[local_idx], tarif)
        for local_idx, tarif in auto_applied
        if 0 <= local_idx < len(row_indexes)
    ]
    auto_rejected = [
        (row_indexes[local_idx], tarif)
        for local_idx, tarif in auto_rejected
        if 0 <= local_idx < len(row_indexes)
    ]
    return matches, auto_applied, auto_rejected


class HistoricalValidationWorker(QThread):
    """
    Background thread za HistoricalTariffSearchService.validate_lines() (Faktura tab).

    DB upiti po stavci su predugi za UI thread — validate_lines() se poziva
    poslije svakog importa (vidi Codex analiza faktura taba, nalaz "performanse"),
    pa je UI dosad zamrzavao na svaki uvoz. Cijeli rezultat (matches i
    last_auto_applied/last_auto_rejected side-effect servisa) se emituje
    odjednom kad DB upit završi — primjena na tabelu/draft i dijalozi ostaju
    na glavnom threadu (isto ponašanje kao prije, samo bez blokiranja).

    Signals:
        finished_validation(list, list, list): (matches, auto_applied, auto_rejected)
        error_occurred(str): poruka greške
    """

    finished_validation = Signal(list, list, list)
    error_occurred = Signal(str)

    def __init__(
        self,
        target_lines: list,
        izvoznik_naziv: str = "",
        uvoznik_naziv: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.target_lines = target_lines
        self.izvoznik_naziv = izvoznik_naziv
        self.uvoznik_naziv = uvoznik_naziv
        self._cancelled = False

    def cancel(self):
        """Zatraži prekid — best-effort, ne prekida DB upit koji je već u toku."""
        self._cancelled = True

    def run(self):
        if self._cancelled:
            return
        try:
            from services.agent.validation.historical_tariff_search_service import (
                HistoricalTariffSearchService,
            )

            svc = HistoricalTariffSearchService()
            matches = svc.validate_lines(
                self.target_lines,
                izvoznik_naziv=self.izvoznik_naziv,
                uvoznik_naziv=self.uvoznik_naziv,
            )
            if self._cancelled:
                return
            db_error = getattr(svc, "last_db_error", None)
            if db_error:
                # Provjera NIJE izvršena (DB nedostupna) — ne emitovati
                # finished_validation sa praznim matches, jer bi to izgledalo
                # kao "provjereno, nema prijedloga" umjesto "nije provjereno".
                self.error_occurred.emit(
                    f"Baza podataka nedostupna — istorijska provjera nije izvršena ({db_error})"
                )
                return
            auto_applied = list(getattr(svc, "last_auto_applied", []) or [])
            auto_rejected = list(getattr(svc, "last_auto_rejected", []) or [])
            self.finished_validation.emit(matches, auto_applied, auto_rejected)
        except Exception as e:
            logger.error("Istorijska validacija (worker) greška: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))
