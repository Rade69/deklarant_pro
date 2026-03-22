"""
Results viewer - prikaz rezultata za odabrani fajl.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QGridLayout
from PySide6.QtCore import Qt
import qtawesome as qta
from ..models.file_item import FileItem
from ..constants import *


class ResultsViewer(QWidget):
    """Viewer za rezultate procesiranja."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.hide()  # Sakriven dok ne izaberemo fajl

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Group box
        self.group = QGroupBox("📋 Rezultati obrade za:")
        group_layout = QGridLayout()
        group_layout.setSpacing(10)

        # Labels
        self.lbl_faktura = self._create_field_label("Faktura br.")
        self.val_faktura = self._create_value_label()

        self.lbl_datum = self._create_field_label("Datum")
        self.val_datum = self._create_value_label()

        self.lbl_iznos = self._create_field_label("Iznos")
        self.val_iznos = self._create_value_label()

        self.lbl_tarif = self._create_field_label("Tarif broj")
        self.val_tarif = self._create_value_label()

        # Additional info labels
        self.lbl_neto = self._create_field_label("Neto")
        self.val_neto = self._create_value_label()

        self.lbl_bruto = self._create_field_label("Bruto")
        self.val_bruto = self._create_value_label()

        self.lbl_ukupno = self._create_field_label("Ukupno")
        self.val_ukupno = self._create_value_label()

        # Layout grid
        group_layout.addWidget(self.lbl_faktura, 0, 0)
        group_layout.addWidget(self.val_faktura, 0, 1)
        group_layout.addWidget(QLabel(), 0, 2)  # Spacer
        group_layout.addWidget(self.lbl_tarif, 0, 3)
        group_layout.addWidget(self.val_tarif, 0, 4)

        group_layout.addWidget(self.lbl_datum, 1, 0)
        group_layout.addWidget(self.val_datum, 1, 1)

        group_layout.addWidget(self.lbl_iznos, 2, 0)
        group_layout.addWidget(self.val_iznos, 2, 1)
        group_layout.addWidget(self.lbl_neto, 2, 3)
        group_layout.addWidget(self.val_neto, 2, 4)

        group_layout.addWidget(self.lbl_bruto, 3, 3)
        group_layout.addWidget(self.val_bruto, 3, 4)

        group_layout.addWidget(self.lbl_ukupno, 4, 3)
        group_layout.addWidget(self.val_ukupno, 4, 4)

        self.group.setLayout(group_layout)
        layout.addWidget(self.group)

        # Styling
        self.group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #0078d4;
            }
        """)

    def _create_field_label(self, text: str) -> QLabel:
        """Kreiraj field label."""
        label = QLabel(text + ":")
        label.setStyleSheet("font-weight: bold; color: #666;")
        return label

    def _create_value_label(self) -> QLabel:
        """Kreiraj value label."""
        label = QLabel("-")
        label.setStyleSheet("color: #333;")
        return label

    def show_results(self, file_item: FileItem):
        """Prikaži rezultate za fajl."""
        self.group.setTitle(f"📋 Rezultati obrade za: {file_item.filename}")

        # Update values
        self.val_faktura.setText(file_item.invoice_number or "-")
        self.val_datum.setText(file_item.invoice_date or "-")

        # Tarifni broj sa "Potrebna potvrda" oznakom
        if file_item.tariff_code:
            if file_item.needs_review:
                tarif_text = f"{file_item.tariff_code} ⚠️ Potrebna potvrda"
                self.val_tarif.setStyleSheet("color: #ffc107; font-weight: bold;")
            else:
                tarif_text = file_item.tariff_code
                self.val_tarif.setStyleSheet("color: #28a745; font-weight: bold;")

            self.val_tarif.setText(tarif_text)
        else:
            self.val_tarif.setText("-")
            self.val_tarif.setStyleSheet("color: #333;")

        # Other values (placeholder)
        self.val_iznos.setText("1,250.00 HRK")
        self.val_neto.setText("8,00 € / kg")
        self.val_bruto.setText("-")
        self.val_ukupno.setText("80,000.00 HRK")

        self.show()

    def clear(self):
        """Očisti rezultate."""
        self.val_faktura.setText("-")
        self.val_datum.setText("-")
        self.val_tarif.setText("-")
        self.val_iznos.setText("-")
        self.val_neto.setText("-")
        self.val_bruto.setText("-")
        self.val_ukupno.setText("-")
        self.hide()
