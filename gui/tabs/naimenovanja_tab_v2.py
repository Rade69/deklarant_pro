"""
ASYCUDA Pro - Naimenovanja Tab V2
Kreiran programski da bude identičan drugoj slici
"""

import sys
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTextEdit, QVBoxLayout,
    QHBoxLayout, QGridLayout, QGroupBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class NaimenovanjaTabV2(QWidget):
    """
    Naimenovanja Tab - rubrika 31 i 44
    Programski kreiran layout identičan slici
    """

    def __init__(self, draft=None, on_dirty=None):
        super().__init__()
        self.draft = draft
        self.on_dirty = on_dirty
        self.current_item_index = 0

        self._create_ui()
        self._connect_signals()

        # Load data
        if self.draft and getattr(self.draft, "items", None):
            self.load_from_item(self.draft.items[0])

    def _create_ui(self):
        """Kreiraj UI programski"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Glavni horizontalni layout
        h_layout = QHBoxLayout()
        h_layout.setSpacing(0)
        h_layout.setContentsMargins(0, 0, 0, 0)

        # LEVA STRANA - Rubrika 31
        left_group = self._create_rubrika_31()
        h_layout.addWidget(left_group, stretch=1)

        # DESNA STRANA - Rubrika 44
        right_group = self._create_rubrika_44()
        h_layout.addWidget(right_group, stretch=1)

        main_layout.addLayout(h_layout)

    def _create_rubrika_31(self):
        """Kreiraj rubriku 31 - identično slici 2"""
        group = QGroupBox("31 Pakovanje i naimenovanje robe")
        group.setStyleSheet("background-color: #E8F5E9; border: 1px solid #81C784;")

        layout = QGridLayout(group)
        layout.setVerticalSpacing(2)
        layout.setHorizontalSpacing(5)

        # Red 1: "Oznake i brojevi - broj vrsta pakata"
        lbl1 = QLabel("Oznake i brojevi - broj vrsta\npakata")
        lbl1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl1, 0, 0, 2, 1)  # Span 2 rows

        # Red 1: Polje za oznake i brojevi
        self.le_r31_oznake_br = QLineEdit()
        layout.addWidget(self.le_r31_oznake_br, 0, 1, 1, 3)

        # Red 2: "Oznake i br. pakata" + polje
        lbl2 = QLabel("Oznake i br.\npakata")
        lbl2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl2, 2, 0)

        self.le_r31_paketa = QLineEdit()
        self.le_r31_paketa.setMaximumWidth(60)
        layout.addWidget(self.le_r31_paketa, 2, 1)

        # Red 3: "Broj i vrsta"
        lbl3 = QLabel("Broj i vrsta")
        lbl3.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl3, 3, 0)

        self.le_r31_broj = QLineEdit()
        self.le_r31_broj.setMaximumWidth(60)
        layout.addWidget(self.le_r31_broj, 3, 1)

        self.le_r31_vrsta = QLineEdit()
        self.le_r31_vrsta.setMaximumWidth(60)
        layout.addWidget(self.le_r31_vrsta, 3, 2)

        # Red 4: "Kontejner"
        lbl4 = QLabel("Kontejner")
        lbl4.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl4, 4, 0)

        self.le_r31_kontejner_1 = QLineEdit()
        layout.addWidget(self.le_r31_kontejner_1, 4, 1, 1, 2)

        self.le_r31_kontejner_2 = QLineEdit()
        layout.addWidget(self.le_r31_kontejner_2, 5, 1, 1, 2)

        # VELIKI TEXTAREA za opis robe
        self.te_r31_opis = QTextEdit()
        self.te_r31_opis.setMinimumHeight(200)
        layout.addWidget(self.te_r31_opis, 6, 0, 1, 4)

        return group

    def _create_rubrika_44(self):
        """Kreiraj rubriku 44 - identično slici 2"""
        group = QGroupBox("44 Priložene\nisprave")
        group.setStyleSheet("background-color: #FFF9C4; border: 1px solid #FBC02D;")

        layout = QVBoxLayout(group)

        # Dva polja za priložene isprave
        self.le_rubrika44_1 = QLineEdit()
        layout.addWidget(self.le_rubrika44_1)

        self.le_rubrika44_2 = QLineEdit()
        layout.addWidget(self.le_rubrika44_2)

        layout.addStretch()

        return group

    def _connect_signals(self):
        """Connect signals"""
        if hasattr(self, 'le_r31_oznake_br'):
            self.le_r31_oznake_br.textChanged.connect(self._on_change)
        if hasattr(self, 'le_r31_paketa'):
            self.le_r31_paketa.textChanged.connect(self._on_change)
        if hasattr(self, 'te_r31_opis'):
            self.te_r31_opis.textChanged.connect(self._on_change)

    def load_from_item(self, item):
        """Load data from NaimenovanjeDraft"""
        if hasattr(self, 'le_r31_oznake_br'):
            self.le_r31_oznake_br.setText(str(getattr(item, "package_marks", "")))
        if hasattr(self, 'le_r31_paketa'):
            self.le_r31_paketa.setText(str(getattr(item, "package_qty", "")))
        if hasattr(self, 'te_r31_opis'):
            self.te_r31_opis.setPlainText(str(getattr(item, "goods_description", "")))

    def save_to_item(self, item):
        """Save data to NaimenovanjeDraft"""
        if hasattr(self, 'le_r31_oznake_br'):
            item.package_marks = self.le_r31_oznake_br.text()
        if hasattr(self, 'le_r31_paketa'):
            try:
                item.package_qty = float(self.le_r31_paketa.text() or "0")
            except ValueError:
                item.package_qty = 0.0
        if hasattr(self, 'te_r31_opis'):
            item.goods_description = self.te_r31_opis.toPlainText()

    def _on_change(self):
        """Handle changes"""
        if not self.draft or not getattr(self.draft, "items", None):
            return

        if self.current_item_index < len(self.draft.items):
            self.save_to_item(self.draft.items[self.current_item_index])

        if self.on_dirty:
            self.on_dirty()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Test sa mock draft
    from asycuda_pro.core.draft import DeclarationDraft
    draft = DeclarationDraft()
    draft.ensure_min_items(1)

    window = NaimenovanjaTabV2(draft)
    window.setWindowTitle("Rubrika 31 i 44 Test")
    window.resize(800, 600)
    window.show()

    sys.exit(app.exec())
