from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.licensing.license_importer import import_license
from core.licensing.license_paths import get_license_path
from core.licensing.license_validator import validate_license_file
from core.licensing.machine_id import get_machine_id


class LicensePanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.machine_id_label = QLabel()
        self.status_label = QLabel()
        self.customer_label = QLabel()
        self.valid_to_label = QLabel()
        self.features_label = QLabel()

        self.copy_machine_id_button = QPushButton("Kopiraj Machine ID")
        self.import_license_button = QPushButton("Uvezi licencu")
        self.refresh_button = QPushButton("Osvježi status")

        self._setup_ui()
        self._connect_signals()
        self.refresh_status()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Licenca")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("LicenseCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        card_layout.addWidget(self.machine_id_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.customer_label)
        card_layout.addWidget(self.valid_to_label)
        card_layout.addWidget(self.features_label)

        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_machine_id_button)
        buttons.addWidget(self.import_license_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)

        card_layout.addLayout(buttons)
        root.addWidget(card)
        root.addStretch(1)

    def _connect_signals(self) -> None:
        self.copy_machine_id_button.clicked.connect(self.copy_machine_id)
        self.import_license_button.clicked.connect(self.import_license)
        self.refresh_button.clicked.connect(self.refresh_status)

    def refresh_status(self) -> None:
        machine_id = get_machine_id()
        self.machine_id_label.setText(f"Machine ID: {machine_id}")

        result = validate_license_file(get_license_path())

        if result.payload:
            self.customer_label.setText(f"Firma: {result.payload.customer_name}")
            self.valid_to_label.setText(f"Važi do: {result.payload.valid_to.isoformat()}")
            self.features_label.setText(f"Paket: {', '.join(result.payload.features)}")
        else:
            self.customer_label.setText("Firma: —")
            self.valid_to_label.setText("Važi do: —")
            self.features_label.setText("Paket: —")

        self.status_label.setText(f"Status: {result.message}")

    def copy_machine_id(self) -> None:
        machine_id = get_machine_id()
        QApplication.clipboard().setText(machine_id)
        QMessageBox.information(self, "Machine ID", "Machine ID je kopiran.")

    def import_license(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Izaberi licencni fajl",
            "",
            "License files (*.dat *.json);;All files (*.*)",
        )

        if not file_path:
            return

        success, message = import_license(Path(file_path))

        if success:
            QMessageBox.information(self, "Licenca", message)
        else:
            QMessageBox.warning(self, "Licenca", message)

        self.refresh_status()
