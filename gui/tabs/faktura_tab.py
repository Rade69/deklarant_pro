# gui/tabs/faktura_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.faktura_view import FakturaView
from gui.tabs.faktura_controller import FakturaController


class FakturaTab(QWidget):
    """Wrapper koji eksponuje FakturaView prema MainWindow-u.

    Faza 1 (Codex plan §8): composition root.
    """

    data_changed = Signal()

    def __init__(
        self,
        draft: DeclarationDraft,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.view = FakturaView(draft=draft, on_dirty=on_dirty)
        self.view.data_changed.connect(self.data_changed)

        # Composition root (Faza 1)
        self.controller = FakturaController(
            get_draft_fn=lambda: self.view.draft,
        )

        # ── Signal wiring (Faza 4-7B) ──────────────────────────
        # Signali su definisani u View-u, povezani na Controller.
        # View JOŠ NE emituje ove signale — stari handleri ostaju aktivni.
        # Prespajanje zahtijeva testiranje na stvarnoj aplikaciji.
        self.view.import_requested.connect(self._on_import_requested)
        self.view.validate_requested.connect(self._on_validate_requested)
        self.view.auto_fill_requested.connect(self._on_auto_fill_requested)
        self.view.create_naimenovanja_requested.connect(self._on_create_naimenovanja_requested)
        self.view.calculate_masses_requested.connect(self._on_calculate_masses_requested)
        self.view.delete_item_requested.connect(self._on_delete_item_requested)
        self.view.tariff_bulk_change_requested.connect(self._on_tariff_bulk_change_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    # ── Signal handleri (delegiraju na Controller) ────────────────

    def _on_import_requested(self, filepaths: list):
        for fp in filepaths:
            self.controller.draft  # koristi get_draft_fn

    def _on_validate_requested(self, scope: str, rows: list):
        self.controller.validate_and_color_rows(self.view, self.controller.draft)

    def _on_auto_fill_requested(self):
        pass  # delegira na TariffFacade kroz View postojeći handler

    def _on_create_naimenovanja_requested(self, auto: bool):
        self.controller.create_naimenovanja(self.controller.draft)
        self.view.naimenovanja_created.emit()

    def _on_calculate_masses_requested(self):
        pass

    def _on_delete_item_requested(self, row: int):
        if self.controller.delete_item(self.controller.draft, row):
            self.view._load_data_from_draft()

    def _on_tariff_bulk_change_requested(self, rows: list, tariff: str):
        self.controller.bulk_change_tariff(self.controller.draft, rows, tariff)
        self.view._load_data_from_draft()
