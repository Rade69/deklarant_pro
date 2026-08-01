# gui/tabs/faktura_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable
import logging

logger = logging.getLogger("deklarant_pro.faktura_tab")

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
        self.view.set_controller(self.controller)

        # ── Signal wiring (Faza 4-7B) ──────────────────────────
        # Ručna validacija je aktivan Controller tok; ostali signali su još
        # pasivna migraciona infrastruktura dok ne dobiju zasebne test kapije.
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

    def validate(self, auto: bool = False) -> tuple[bool, int, int]:
        if auto:
            return self.view.validate(auto=True)
        self.view.validate_requested.emit("all", [])
        return (
            True,
            self.view.validation_cache.get_error_count(),
            self.view.validation_cache.get_warning_count(),
        )

    def create_naimenovanja(self, auto: bool = False) -> bool:
        return self.view.create_naimenovanja(auto=auto)

    def calculate_masses(self, auto: bool = False) -> bool:
        return self.view.calculate_masses(auto=auto, controller=self.controller)

    def auto_fill(self, auto: bool = False):
        return self.view.auto_fill(auto=auto, controller=self.controller)

    def _on_import_requested(self, filepaths: list):
        """Import handler — delegira na postojeći FakturaView._start_import."""
        for fp in filepaths:
            try:
                if hasattr(self.view, "_start_import"):
                    self.view._start_import(fp)
            except Exception as e:
                logger.error(f"Import failed for {fp}: {e}")

    def _on_validate_requested(self, scope: str, rows: list):
        """Validacija — delegira na Controller, primjenjuje boje na tabelu.
        Koristi blockSignals da spriječi neželjene itemChanged događaje."""
        from gui.delegates.validation_delegate import ValidationDelegate
        from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

        draft = self.controller.draft
        if not getattr(draft, "invoice_lines", None):
            QMessageBox.information(self, "Nema stavki", "Nema stavki za validaciju.")
            return

        self.view._sync_table_to_draft()
        selected_rows = rows if rows and scope != "all" else None
        result = self.controller.validate_and_color_rows(draft, selected_rows)
        style_map = result.get("style_map") or {}
        table = self.view.table
        table.blockSignals(True)
        try:
            for row_idx, style in style_map.items():
                if row_idx < table.rowCount():
                    self.view.validation_cache.set(row_idx, style.result)
                    for col in range(table.columnCount()):
                        cell = table.item(row_idx, col)
                        if cell:
                            cell.setData(
                                ValidationDelegate.ValidationColorRole,
                                style.row_color,
                            )
                            cell.setToolTip(style.row_tooltip)
                    self.view._apply_country_confidence_color(
                        row_idx, draft.invoice_lines[row_idx]
                    )
                    self.view._apply_preference_confidence_color(
                        row_idx, draft.invoice_lines[row_idx]
                    )
                    for col, (cell_color, cell_tooltip) in style.cell_overrides.items():
                        cell = table.item(row_idx, col)
                        if cell:
                            cell.setData(ValidationDelegate.ValidationColorRole, cell_color)
                            cell.setToolTip(cell_tooltip)
        finally:
            table.blockSignals(False)
            table.viewport().update()

        self.view._update_status_bar()
        error_count = result.get("error_count", 0)
        warning_count = result.get("warning_count", 0)
        valid_count = result.get("valid_count", 0)
        total_count = len(selected_rows) if selected_rows is not None else len(draft.invoice_lines)
        error_issues, warning_issues = self.view._validation_issue_counts(selected_rows)

        message = ""
        if selected_rows is not None:
            message += f"📌 Prikazano samo za {len(selected_rows)} selektovanih stavki.\n\n"
        message += "╔══════════════════════════════════════╗\n"
        message += "║      REZULTAT VALIDACIJE             ║\n"
        message += "╠══════════════════════════════════════╣\n"
        message += f"║  Ukupno stavki: {total_count:>4}                ║\n"
        message += f"║  ✅ Validne:     {valid_count:>4}                ║\n"
        message += f"║  ❌ Nevažeće:    {error_count:>4}                ║\n"
        message += "╠══════════════════════════════════════╣\n"
        message += f"║  🔴 Greške:      {error_count:>4}                ║\n"
        message += f"║  🟡 Upozorenja:  {warning_count:>4}                ║\n"
        message += "╚══════════════════════════════════════╝\n"
        if error_issues:
            message += "\nGreške po tipu:\n"
            for label, count in sorted(error_issues.items(), key=lambda item: (-item[1], item[0])):
                message += f"  • {count} {label}\n"
        if warning_issues:
            message += "\nUpozorenja po tipu:\n"
            for label, count in sorted(warning_issues.items(), key=lambda item: (-item[1], item[0])):
                message += f"  • {count} {label}\n"

        if error_count > 0:
            message += "\n⚠️  NAPOMENA:\nProvjerite crveno označene stavke!"
            QMessageBox.warning(self, "Validacija", message)
        elif warning_count > 0:
            message += "\n💡 SAVJET:\nProvjerite žuto označene stavke."
            QMessageBox.information(self, "Validacija", message)
        else:
            message += "\n🎉 SVE STAVKE SU VALIDNE!"
            QMessageBox.information(self, "Validacija", message)

        self.view._run_historical_tariff_validation(auto=False)

    def _on_auto_fill_requested(self):
        """Auto-popuna tarifa — delegira na javni legacy adapter."""
        return self.auto_fill(auto=False)

    def _on_create_naimenovanja_requested(self, auto: bool):
        """Kreiranje naimenovanja — delegira na javni legacy adapter."""
        return self.create_naimenovanja(auto=auto)

    def _on_calculate_masses_requested(self):
        """Računanje masa — delegira na javni legacy adapter."""
        return self.calculate_masses(auto=False)

    def _on_delete_item_requested(self, row: int):
        """Brisanje stavke — Controller + View refresh."""
        if self.controller.delete_item(self.controller.draft, row):
            self.view._load_data_from_draft()

    def _on_tariff_bulk_change_requested(self, rows: list, tariff: str):
        """Bulk izmjena tarife — Controller + View refresh."""
        updated = self.controller.bulk_change_tariff(self.controller.draft, rows, tariff)
        if updated:
            self.view._load_data_from_draft()
