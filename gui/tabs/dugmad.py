"""Helper methods for creating company groups."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
from PySide6.QtGui import QFont


def _create_company_group(self, title, prefix, with_search=False, auto=False):
    """Create company input group (Izvoznik, Primalac, Deklarant)."""
    group = QWidget()
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)

    # Title row with search/add buttons and ID field
    title_row = QWidget()
    title_layout = QHBoxLayout(title_row)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    title_layout.addWidget(title_label)

    if with_search:
        # Search button - now with magnifying glass icon and larger size
        search_btn = QPushButton()
        search_btn.setFixedSize(30, 26)  # Increased size
        search_btn.setIcon(
            search_btn.style().standardIcon(40)
        )  # Standard icon for search (QStyle.SP_FindIcon)
        search_btn.setToolTip("Pretraži")
        search_btn.clicked.connect(lambda: self._on_search_company(prefix))
        title_layout.addWidget(search_btn)

        # Add button - now with save icon (diskette) and larger size
        add_btn = QPushButton()
        add_btn.setFixedSize(30, 26)  # Increased size
        add_btn.setIcon(
            add_btn.style().standardIcon(39)
        )  # Standard icon for save (QStyle.SP_DriveFDIcon)
        add_btn.setToolTip("Dodaj novi")
        add_btn.setStyleSheet(
            "background: #5cb85c; color: white; border: 1px solid #449d44;"
        )
        add_btn.clicked.connect(lambda: self._on_add_company(prefix))
        title_layout.addWidget(add_btn)

    if auto:
        # AUTO badge
        auto_label = QLabel("AUTO")
        auto_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        auto_label.setStyleSheet(
            """
            background: #5cb85c;
            color: white;
            padding: 2px 5px;
            border-radius: 2px;
        """
        )
        title_layout.addWidget(auto_label)

    # ID field
    id_field = QLineEdit()
    id_field.setPlaceholderText(
        "Šifra" if prefix == "izvoznik" else "JIB" if prefix == "primalac" else "Šifra"
    )
    id_field.setFixedWidth(150)
    if auto:
        id_field.setReadOnly(True)
        id_field.setText("400338660009")  # Default
    title_layout.addStretch()
    title_layout.addWidget(id_field)

    self.field_widgets[f"{prefix}_id"] = id_field

    layout.addWidget(title_row)

    # Address fields (5 lines) with proper placeholders
    placeholders = ["Naziv firme", "Adresa", "Grad", "Poštanski broj", "Država"]
    for i, placeholder in enumerate(placeholders, 1):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if auto:
            field.setReadOnly(True)
            if i == 1:
                field.setText("DM-PROMET DOO")
            elif i == 2:
                field.setText("TRNJAKI-BIJELJINA")
            elif i == 3:
                field.setText("RAČA BB, GRANIČNI PRELAZ")
        layout.addWidget(field)
        self.field_widgets[f"{prefix}_r{i}"] = field

    return group
