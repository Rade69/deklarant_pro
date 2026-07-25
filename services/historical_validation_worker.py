# services/historical_validation_worker.py

"""
Deklarant Pro - Historical Validation Worker (Threading)
Non-blocking istorijska validacija tarifnih brojeva za PySide6 Qt aplikaciju.
"""

import logging
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger("deklarant_pro.faktura.historical_validation_worker")


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
            auto_applied = list(getattr(svc, "last_auto_applied", []) or [])
            auto_rejected = list(getattr(svc, "last_auto_rejected", []) or [])
            self.finished_validation.emit(matches, auto_applied, auto_rejected)
        except Exception as e:
            logger.error("Istorijska validacija (worker) greška: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))
