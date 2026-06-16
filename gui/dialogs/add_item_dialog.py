# gui/dialogs/add_item_dialog.py

"""
Add Item Dialog - Dialog za ručno dodavanje nove stavke u fakturu.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from typing import Optional

from core.draft import InvoiceLine
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
from ..classic_style import ClassicFonts


class AddItemDialog(QDialog):
    """
    Dialog za ručno dodavanje nove fakturne stavke.

    Omogućava unos svih polja:
    - Naimenovanje (opcionalno)
    - Naziv robe (obavezno)
    - Tarifni broj (obavezno)
    - Količina (obavezno)
    - Cijena (obavezno)
    - Bruto (kg)
    - Neto (kg)
    - Zemlja porijekla (obavezno)
    - Povlastica
    - Valuta (obavezno)
    """

    def __init__(self, parent=None, next_line_no: int = 1):
        super().__init__(parent)
        self.next_line_no = next_line_no
        self.result_item: Optional[InvoiceLine] = None

        self.setWindowTitle("Dodaj Novu Stavku")
        self.setModal(True)
        self.resize(500, 600)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI layout."""
        # Apply larger fonts for better readability
        normal_font = ClassicFonts.normal()
        bold_font = ClassicFonts.bold()

        # Apply fonts to all widgets
        self.setFont(normal_font)
        """Setup UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel(f"<h3>Nova Stavka #{self.next_line_no}</h3>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Naimenovanje (optional)
        self.naimenovanje_input = QLineEdit()
        self.naimenovanje_input.setPlaceholderText("Opcionalno...")
        form_layout.addRow("Naimenovanje:", self.naimenovanje_input)

        # Naziv robe (required)
        self.naziv_input = QLineEdit()
        self.naziv_input.setPlaceholderText("Obavezno *")
        form_layout.addRow("Naziv robe: *", self.naziv_input)

        # Tarifni broj (required)
        self.tariff_input = QLineEdit()
        self.tariff_input.setPlaceholderText("8 cifara (npr. 02013000)")
        self.tariff_input.setMaxLength(10)
        form_layout.addRow("Tarifni broj: *", self.tariff_input)

        # Količina (required)
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0.01, 999999.99)
        self.qty_input.setDecimals(2)
        self.qty_input.setValue(1.0)
        self.qty_input.setSuffix(" ")
        form_layout.addRow("Količina: *", self.qty_input)

        # Cijena (required)
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.01, 999999.99)
        self.price_input.setDecimals(2)
        self.price_input.setValue(1.0)
        self.price_input.setSuffix(" ")
        form_layout.addRow("Cijena: *", self.price_input)

        # Bruto (kg) - optional
        self.bruto_input = QDoubleSpinBox()
        self.bruto_input.setRange(0.0, 999999.99)
        self.bruto_input.setDecimals(2)
        self.bruto_input.setValue(0.0)
        self.bruto_input.setSuffix(" kg")
        form_layout.addRow("Bruto (kg):", self.bruto_input)

        # Neto (kg) - optional
        self.neto_input = QDoubleSpinBox()
        self.neto_input.setRange(0.0, 999999.99)
        self.neto_input.setDecimals(2)
        self.neto_input.setValue(0.0)
        self.neto_input.setSuffix(" kg")
        form_layout.addRow("Neto (kg):", self.neto_input)

        # Zemlja porijekla (required)
        self.origin_input = QComboBox()
        self.origin_input.setEditable(True)
        self.origin_input.addItems([
            "",  # Empty first
            "BA", "RS", "HR", "ME", "MK", "SI",  # Balkan
            "DE", "IT", "FR", "ES", "NL", "BE",  # EU West
            "PL", "CZ", "HU", "SK", "RO", "BG",  # EU East
            "GB", "US", "CN", "TR", "RU", "UA",  # Other
        ])
        form_layout.addRow("Zemlja porijekla: *", self.origin_input)

        # Povlastica (preference)
        self.preference_input = QComboBox()
        self.preference_input.addItems(["", "P1", "P2", "P3", "P4"])
        form_layout.addRow("Povlastica:", self.preference_input)

        # Valuta (required)
        self.currency_input = QComboBox()
        self.currency_input.addItems(["EUR", "USD", "BAM", "GBP", "CHF"])
        form_layout.addRow("Valuta: *", self.currency_input)

        layout.addLayout(form_layout)

        # Required fields note
        note = QLabel("<i>* Obavezna polja</i>")
        note.setProperty("class", "form-note")  # CSS in typography.qss
        layout.addWidget(note)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Otkaži")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        add_btn = QPushButton("Dodaj Stavku")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._on_add)
        button_layout.addWidget(add_btn)

        layout.addLayout(button_layout)

    def _on_add(self):
        """Validate and create InvoiceLine."""
        # Validate required fields
        errors = []

        naziv = self.naziv_input.text().strip()
        if not naziv:
            errors.append("Naziv robe je obavezan")

        tariff = self.tariff_input.text().strip()
        if not tariff:
            errors.append("Tarifni broj je obavezan")
        elif len(tariff) not in [8, 10]:
            errors.append("Tarifni broj mora imati 8 ili 10 cifara")

        origin = self.origin_input.currentText().strip()
        if not origin:
            errors.append("Zemlja porijekla je obavezna")

        qty = self.qty_input.value()
        if qty <= 0:
            errors.append("Količina mora biti veća od 0")

        price = self.price_input.value()
        if price <= 0:
            errors.append("Cijena mora biti veća od 0")

        # Show errors if any
        if errors:
            QMessageBox.warning(
                self,
                "Greška u unosu",
                "Molimo ispravite sljedeće greške:\\n\\n" + "\\n".join(f"• {e}" for e in errors)
            )
            return

        # Create InvoiceLine
        iznos = qty * price

        self.result_item = InvoiceLine(
            line_no=self.next_line_no,
            naimenovanje=self.naimenovanje_input.text().strip() or None,
            naziv_robe=naziv,
            tarifni_broj=tariff,
            kolicina=qty,
            cijena_jed=price,
            iznos=iznos,
            bruto_kg=self.bruto_input.value() if self.bruto_input.value() > 0 else None,
            neto_kg=self.neto_input.value() if self.neto_input.value() > 0 else None,
            zemlja_porijekla=origin,
            povlastica=self.preference_input.currentText().strip() or None,
            valuta=self.currency_input.currentText(),
            jm="KOM",  # Default unit
        )

        self.accept()

    def get_item(self) -> Optional[InvoiceLine]:
        """Return created item if dialog was accepted."""
        return self.result_item
