"""
ASYCUDA Pro - Naimenovanja Tab
Wrapper za naimenovanja_tab_OPTIMIZED.ui
"""

import os
import sys
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile


class NaimenovanjaTab(QWidget):
    """
    Naimenovanja Tab - sve rubrike 31-46
    Optimizovani layout sa Material Design stilovima
    """
    
    def __init__(self, draft=None, on_dirty=None):
        super().__init__()
        self.draft = draft
        self.on_dirty = on_dirty
        self.current_item_index = 0
        
        # Load UI
        self._load_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Load data
        if self.draft and getattr(self.draft, "items", None):
            self.load_from_item(self.draft.items[0])
            self._update_nav_state()
    
    def _load_ui(self):
        """Load .ui file"""
        ui_file_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "ui", "naimenovanja_tab_OPTIMIZED.ui"
        )
        
        if not os.path.exists(ui_file_path):
            raise FileNotFoundError(f"UI fajl ne postoji: {ui_file_path}")
        
        ui_file = QFile(ui_file_path)
        ui_file.open(QFile.ReadOnly)
        
        loader = QUiLoader()
        self.ui = loader.load(ui_file, self)
        ui_file.close()
        
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        # Spusti QGroupBox-ove ispod ostalih widgeta da budu pozadina
        self._lower_groupboxes()

    def _lower_groupboxes(self):
        """Spusti QGroupBox-ove ispod da budu pozadina"""
        groupbox_names = ['group_31', 'group_32_39', 'group_40', 'group_41_43', 'group_44', 'group_45_46']
        for name in groupbox_names:
            if hasattr(self.ui, name):
                groupbox = getattr(self.ui, name)
                groupbox.lower()

    def _connect_signals(self):
        """Connect signals"""
        # Navigation
        if hasattr(self.ui, 'btn_first'):
            self.ui.btn_first.clicked.connect(lambda: self._go_to_item(0))
        if hasattr(self.ui, 'btn_prev'):
            self.ui.btn_prev.clicked.connect(lambda: self._go_to_item(self.current_item_index - 1))
        if hasattr(self.ui, 'btn_next'):
            self.ui.btn_next.clicked.connect(lambda: self._go_to_item(self.current_item_index + 1))
        if hasattr(self.ui, 'btn_last'):
            self.ui.btn_last.clicked.connect(lambda: self._go_to_item(len(self.draft.items) - 1) if self.draft and self.draft.items else None)
        
        # Actions
        if hasattr(self.ui, 'btn_novo_lg'):
            self.ui.btn_novo_lg.clicked.connect(self._on_new_item)
        if hasattr(self.ui, 'btn_dodaj_lg'):
            self.ui.btn_dodaj_lg.clicked.connect(self._on_add_item)
        if hasattr(self.ui, 'btn_brisi_sm'):
            self.ui.btn_brisi_sm.clicked.connect(self._on_delete_item)
        
        # Input fields
        input_fields = [
            'le_r31_oznake_br', 'le_r31_paketa', 'le_r31_broj', 'le_r31_vrsta',
            'le_r31_kontejner_1', 'le_r31_kontejner_2', 'te_r31_opis', 'le_r31_trg_naziv',
            'te_rubrika32', 'le_rubrika33', 'le_rubrika34_zemlja', 'le_rubrika35',
            'le_rubrika36', 'le_rubrika37_1', 'le_rubrika38', 'le_rubrika39',
            'le_rubrika40_1', 'te_rubrika41', 'le_rubrika42', 'le_rubrika43',
            'le_rubrika44_1', 'le_rubrika45_sifra', 'le_rubrika46'
        ]
        
        for field_name in input_fields:
            if hasattr(self.ui, field_name):
                widget = getattr(self.ui, field_name)
                if hasattr(widget, 'textChanged'):
                    widget.textChanged.connect(self._on_change)
    
    def load_from_item(self, item):
        """Load data from NaimenovanjeDraft"""
        # Rubrika 31
        if hasattr(self.ui, 'le_r31_oznake_br'):
            self.ui.le_r31_oznake_br.setText(str(getattr(item, "package_marks", "")))
        if hasattr(self.ui, 'le_r31_paketa'):
            self.ui.le_r31_paketa.setText(str(getattr(item, "package_qty", "")))
        if hasattr(self.ui, 'le_r31_broj'):
            self.ui.le_r31_broj.setText(str(getattr(item, "package_qty", "")))
        if hasattr(self.ui, 'le_r31_vrsta'):
            self.ui.le_r31_vrsta.setText(str(getattr(item, "package_code", "")))
        if hasattr(self.ui, 'te_r31_opis'):
            widget = self.ui.te_r31_opis
            text = str(getattr(item, "goods_description", ""))
            if hasattr(widget, 'setPlainText'):
                widget.setPlainText(text)
            else:
                widget.setText(text)
        if hasattr(self.ui, 'le_r31_trg_naziv'):
            self.ui.le_r31_trg_naziv.setText(str(getattr(item, "goods_trade_name", "")))
        if hasattr(self.ui, 'le_r31_kontejner_1'):
            self.ui.le_r31_kontejner_1.setText(str(getattr(item, "container_number1", "")))
        if hasattr(self.ui, 'le_r31_kontejner_2'):
            self.ui.le_r31_kontejner_2.setText(str(getattr(item, "container_number2", "")))

        # Rubrike 32-46
        if hasattr(self.ui, 'te_rubrika32'):
            widget = self.ui.te_rubrika32
            text = str(getattr(item, "ordinal_no", ""))
            if hasattr(widget, 'setPlainText'):
                widget.setPlainText(text)
            else:
                widget.setText(text)
        if hasattr(self.ui, 'le_rubrika33'):
            self.ui.le_rubrika33.setText(str(getattr(item, "tariff_code", "")))
        if hasattr(self.ui, 'le_rubrika34_zemlja'):
            self.ui.le_rubrika34_zemlja.setText(str(getattr(item, "origin_country_code", "")))
        if hasattr(self.ui, 'le_rubrika35'):
            self.ui.le_rubrika35.setText(str(getattr(item, "gross_mass_kg", "")))
        if hasattr(self.ui, 'le_rubrika36'):
            self.ui.le_rubrika36.setText(str(getattr(item, "preference_code", "")))
        if hasattr(self.ui, 'le_rubrika37_1'):
            self.ui.le_rubrika37_1.setText(str(getattr(item, "procedure_code", "")))
        if hasattr(self.ui, 'le_rubrika38'):
            self.ui.le_rubrika38.setText(str(getattr(item, "net_mass_kg", "")))
        if hasattr(self.ui, 'le_rubrika39'):
            self.ui.le_rubrika39.setText(str(getattr(item, "quota_code", "")))
        if hasattr(self.ui, 'le_rubrika40_1'):
            self.ui.le_rubrika40_1.setText(str(getattr(item, "previous_document", "")))
        if hasattr(self.ui, 'te_rubrika41'):
            widget = self.ui.te_rubrika41
            text = str(getattr(item, "supplementary_unit_qty", ""))
            if hasattr(widget, 'setPlainText'):
                widget.setPlainText(text)
            else:
                widget.setText(text)
        if hasattr(self.ui, 'le_rubrika42'):
            self.ui.le_rubrika42.setText(str(getattr(item, "item_value", "")))
        if hasattr(self.ui, 'le_rubrika46'):
            self.ui.le_rubrika46.setText(str(getattr(item, "statistical_value", "")))

        self._update_displays()
    
    def save_to_item(self, item):
        """Save data to NaimenovanjeDraft"""
        # Rubrika 31
        if hasattr(self.ui, 'le_r31_oznake_br'):
            item.package_marks = self.ui.le_r31_oznake_br.text()
        if hasattr(self.ui, 'le_r31_paketa'):
            try:
                item.package_qty = float(self.ui.le_r31_paketa.text() or "0")
            except ValueError:
                item.package_qty = 0.0
        if hasattr(self.ui, 'le_r31_vrsta'):
            item.package_code = self.ui.le_r31_vrsta.text()
        if hasattr(self.ui, 'te_r31_opis'):
            widget = self.ui.te_r31_opis
            if hasattr(widget, 'toPlainText'):
                item.goods_description = widget.toPlainText()
            else:
                item.goods_description = widget.text()
        if hasattr(self.ui, 'le_r31_trg_naziv'):
            item.goods_trade_name = self.ui.le_r31_trg_naziv.text()
        if hasattr(self.ui, 'le_r31_kontejner_1'):
            item.container_number1 = self.ui.le_r31_kontejner_1.text()
        if hasattr(self.ui, 'le_r31_kontejner_2'):
            item.container_number2 = self.ui.le_r31_kontejner_2.text()

        # Rubrike 32-46
        if hasattr(self.ui, 'te_rubrika32'):
            widget = self.ui.te_rubrika32
            if hasattr(widget, 'toPlainText'):
                try:
                    item.ordinal_no = int(widget.toPlainText() or "0")
                except ValueError:
                    item.ordinal_no = 0
            else:
                try:
                    item.ordinal_no = int(widget.text() or "0")
                except ValueError:
                    item.ordinal_no = 0
        if hasattr(self.ui, 'le_rubrika33'):
            item.tariff_code = self.ui.le_rubrika33.text()
        if hasattr(self.ui, 'le_rubrika34_zemlja'):
            item.origin_country_code = self.ui.le_rubrika34_zemlja.text()
        if hasattr(self.ui, 'le_rubrika35'):
            try:
                item.gross_mass_kg = float(self.ui.le_rubrika35.text().replace(",", ".") or "0")
            except ValueError:
                item.gross_mass_kg = 0.0
        if hasattr(self.ui, 'le_rubrika36'):
            item.preference_code = self.ui.le_rubrika36.text()
        if hasattr(self.ui, 'le_rubrika37_1'):
            item.procedure_code = self.ui.le_rubrika37_1.text()
        if hasattr(self.ui, 'le_rubrika38'):
            try:
                item.net_mass_kg = float(self.ui.le_rubrika38.text().replace(",", ".") or "0")
            except ValueError:
                item.net_mass_kg = 0.0
        if hasattr(self.ui, 'le_rubrika39'):
            item.quota_code = self.ui.le_rubrika39.text()
        if hasattr(self.ui, 'le_rubrika40_1'):
            item.previous_document = self.ui.le_rubrika40_1.text()
        if hasattr(self.ui, 'te_rubrika41'):
            widget = self.ui.te_rubrika41
            if hasattr(widget, 'toPlainText'):
                try:
                    item.supplementary_unit_qty = float(widget.toPlainText().replace(",", ".") or "0")
                except ValueError:
                    item.supplementary_unit_qty = 0.0
            else:
                try:
                    item.supplementary_unit_qty = float(widget.text().replace(",", ".") or "0")
                except ValueError:
                    item.supplementary_unit_qty = 0.0
        if hasattr(self.ui, 'le_rubrika42'):
            try:
                item.item_value = float(self.ui.le_rubrika42.text().replace(",", ".") or "0")
            except ValueError:
                item.item_value = 0.0
        if hasattr(self.ui, 'le_rubrika46'):
            try:
                item.statistical_value = float(self.ui.le_rubrika46.text().replace(",", ".") or "0")
            except ValueError:
                item.statistical_value = 0.0
    
    def _on_change(self):
        """Handle changes"""
        if not self.draft or not getattr(self.draft, "items", None):
            return
        
        if self.current_item_index < len(self.draft.items):
            self.save_to_item(self.draft.items[self.current_item_index])
        
        self._update_displays()
        
        if self.on_dirty:
            self.on_dirty()
    
    def _update_displays(self):
        """Update brutto/netto displays"""
        try:
            if hasattr(self.ui, 'le_rubrika35') and hasattr(self.ui, 'lbl_brutto_val'):
                brutto = float(self.ui.le_rubrika35.text().replace(",", ".") or 0)
                self.ui.lbl_brutto_val.setText(f"{brutto:.2f}")
        except ValueError:
            pass
        
        try:
            if hasattr(self.ui, 'le_rubrika38') and hasattr(self.ui, 'lbl_netto_val'):
                netto = float(self.ui.le_rubrika38.text().replace(",", ".") or 0)
                self.ui.lbl_netto_val.setText(f"{netto:.2f}")
        except ValueError:
            pass
    
    def _go_to_item(self, index):
        """Navigate to item"""
        if not self.draft or not self.draft.items:
            return
        if index < 0 or index >= len(self.draft.items):
            return
        
        if self.current_item_index < len(self.draft.items):
            self.save_to_item(self.draft.items[self.current_item_index])
        
        self.current_item_index = index
        self.load_from_item(self.draft.items[index])
        self._update_nav_state()
    
    def _on_new_item(self):
        """New item"""
        if not self.draft:
            return
        
        if self.draft.items and self.current_item_index < len(self.draft.items):
            self.save_to_item(self.draft.items[self.current_item_index])
        
        self.draft.add_item()
        self.current_item_index = len(self.draft.items) - 1
        
        if self.draft.items:
            self.load_from_item(self.draft.items[self.current_item_index])
        
        self._update_nav_state()
        
        if self.on_dirty:
            self.on_dirty()
    
    def _on_add_item(self):
        """Add item"""
        self._on_new_item()
    
    def _on_delete_item(self):
        """Delete item"""
        if not self.draft or not self.draft.items or len(self.draft.items) <= 1:
            return
        
        del self.draft.items[self.current_item_index]
        
        if self.current_item_index >= len(self.draft.items):
            self.current_item_index = len(self.draft.items) - 1
        
        if self.draft.items:
            self.load_from_item(self.draft.items[self.current_item_index])
        
        self._update_nav_state()
        
        if self.on_dirty:
            self.on_dirty()
    
    def _update_nav_state(self):
        """Update navigation state"""
        total = len(self.draft.items) if self.draft and self.draft.items else 0
        current = self.current_item_index + 1 if total > 0 else 0
        
        if hasattr(self.ui, 'lbl_item_counter'):
            self.ui.lbl_item_counter.setText(f"{current} / {total}")
        
        if hasattr(self.ui, 'btn_first'):
            self.ui.btn_first.setEnabled(self.current_item_index > 0)
        if hasattr(self.ui, 'btn_prev'):
            self.ui.btn_prev.setEnabled(self.current_item_index > 0)
        if hasattr(self.ui, 'btn_next'):
            self.ui.btn_next.setEnabled(self.current_item_index < total - 1)
        if hasattr(self.ui, 'btn_last'):
            self.ui.btn_last.setEnabled(self.current_item_index < total - 1)
        if hasattr(self.ui, 'btn_brisi_sm'):
            self.ui.btn_brisi_sm.setEnabled(total > 1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NaimenovanjaTab()
    window.show()
    sys.exit(app.exec())
