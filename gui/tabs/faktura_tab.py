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
        """Import handler — koristi postojeći unified import workflow."""
        for fp in filepaths:
            try:
                from services.faktura.import_service import ImportService
                svc = ImportService()
                result = svc.import_file(fp)
                self.view._on_import_finished(result)
            except Exception as e:
                logger.error(f"Import failed for {fp}: {e}")

    def _on_validate_requested(self, scope: str, rows: list):
        """Validacija — delegira na Controller, primjenjuje boje na tabelu."""
        result = self.controller.validate_and_color_rows(self.controller.draft)
        if result and result.get("color_map"):
            for row_idx, (color, tooltip) in result["color_map"].items():
                if row_idx < self.view.table.rowCount():
                    for col in range(self.view.table.columnCount()):
                        cell = self.view.table.item(row_idx, col)
                        if cell:
                            from gui.delegates.validation_delegate import ValidationDelegate
                            cell.setData(ValidationDelegate.ValidationColorRole, color)
                            if tooltip:
                                cell.setToolTip(tooltip)

    def _on_auto_fill_requested(self):
        """Auto-popuna tarifa — delegira na postojeći View handler."""
        if hasattr(self.view, "_on_auto_fill"):
            self.view._on_auto_fill()

    def _on_create_naimenovanja_requested(self, auto: bool):
        """Kreiranje naimenovanja — delegira na Controller."""
        result = self.controller.create_naimenovanja(self.controller.draft)
        if result.get("error"):
            from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
            QMessageBox.warning(self, "Greška", f"Kreiranje naimenovanja nije uspjelo:\n{result['error']}")
        elif result.get("count", 0) > 0:
            self.view._load_data_from_draft()
            self.view.naimenovanja_created.emit()

    def _on_calculate_masses_requested(self):
        """Računanje masa — delegira na postojeći View handler."""
        if hasattr(self.view, "_on_calculate_masses"):
            self.view._on_calculate_masses()

    def _on_delete_item_requested(self, row: int):
        """Brisanje stavke — Controller + View refresh."""
        if self.controller.delete_item(self.controller.draft, row):
            self.view._load_data_from_draft()

    def _on_tariff_bulk_change_requested(self, rows: list, tariff: str):
        """Bulk izmjena tarife — Controller + View refresh."""
        updated = self.controller.bulk_change_tariff(self.controller.draft, rows, tariff)
        if updated:
            self.view._load_data_from_draft()
