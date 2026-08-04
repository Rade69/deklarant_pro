"""
Header bar sa statusom, parserom i sesija informacijama.
Botanički Sage Green dizajn.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Signal
import qtawesome as qta
from ..constants import (
    COLOR_DANGER, COLOR_INFO, COLOR_SAGE_BG, COLOR_SAGE_DARK,
    COLOR_SAGE_MID, COLOR_SAGE_PALE, COLOR_SAGE_PANEL, COLOR_SUCCESS,
    COLOR_TEXT, COLOR_TEXT_LIGHT, COLOR_TEXT_MUTED, COLOR_WARNING,
    ICON_BELL, ICON_CHAT, ICON_QUESTION,
    STATUS_COMPLETED, STATUS_ERROR, STATUS_PAUSED,
    STATUS_PROCESSING, STATUS_READY,
)


class HeaderBar(QWidget):
    """Header bar — sage green, lagana i čista linija."""

    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)
        self.setMinimumHeight(54)

        # Status badge
        self.status_badge = QLabel(f"● {STATUS_READY}")
        self._set_status_style(STATUS_READY)

        self.status_combo = QComboBox()
        self.status_combo.addItems([
            STATUS_READY, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_PAUSED, STATUS_ERROR
        ])
        self.status_combo.setVisible(False)
        self.status_combo.currentTextChanged.connect(self._on_status_changed)

        layout.addWidget(self.status_badge)

        # Separator
        layout.addWidget(self._sep())

        # Sesija
        sesija_label = QLabel("Sesija:")
        sesija_label.setObjectName("headerLabel")
        self.sesija_value = QLabel("0 aktivnih zadataka")
        self.sesija_value.setObjectName("headerValue")
        layout.addWidget(sesija_label)
        layout.addWidget(self.sesija_value)

        layout.addStretch()

        # Desna strana — ikone za notifikacije
        for icon_name, tooltip in [
            (ICON_BELL, "Obavještenja"),
            (ICON_QUESTION, "Pomoć"),
            (ICON_CHAT, "Chat"),
        ]:
            btn = QPushButton(qta.icon(icon_name, color=COLOR_SAGE_DARK), "")
            btn.setFixedSize(34, 34)
            btn.setToolTip(tooltip)
            btn.setObjectName("iconBtn")
            layout.addWidget(btn)

        self.setStyleSheet(f"""
            HeaderBar {{
                background-color: white;
                border-bottom: 1px solid {COLOR_SAGE_PALE};
            }}
            HeaderBar QLabel {{
                font-size: 13px;
                color: {COLOR_TEXT_LIGHT};
                background: transparent;
            }}
            HeaderBar QLabel#headerLabel {{
                font-weight: bold;
                color: {COLOR_SAGE_DARK};
            }}
            HeaderBar QLabel#headerValue {{
                color: {COLOR_TEXT_MUTED};
            }}
            HeaderBar QComboBox {{
                font-size: 13px;
                background-color: white;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 12px;
                padding: 3px 10px;
                min-width: 120px;
            }}
            HeaderBar QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            HeaderBar QComboBox QAbstractItemView {{
                background-color: white;
                color: {COLOR_TEXT};
                selection-background-color: {COLOR_SAGE_PANEL};
                border: 1px solid {COLOR_SAGE_PALE};
            }}
            QPushButton#iconBtn {{
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 17px;
                background-color: {COLOR_SAGE_BG};
            }}
            QPushButton#iconBtn:hover {{
                background-color: {COLOR_SAGE_PANEL};
                border-color: {COLOR_SAGE_MID};
            }}
        """)

    def _sep(self) -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {COLOR_SAGE_PALE}; background: transparent;")
        return sep

    def _set_status_style(self, status: str):
        colors = {
            STATUS_READY:      (COLOR_SUCCESS,  "#e2f1e9"),
            STATUS_PROCESSING: (COLOR_INFO,     "#e4edf3"),
            STATUS_COMPLETED:  (COLOR_SUCCESS,  "#e2f1e9"),
            STATUS_PAUSED:     (COLOR_WARNING,  "#f7efd9"),
            STATUS_ERROR:      (COLOR_DANGER,   "#f5e3e3"),
        }
        fg, bg = colors.get(status, ("#333", "#e9ecef"))
        self.status_badge.setText(f"● {status}")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 11px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 13px;
            }}
        """)

    def _on_status_changed(self, status: str):
        self._set_status_style(status)
        self.status_changed.emit(status)

    def update_sesija(self, active_tasks: int):
        if active_tasks == 0:
            self.sesija_value.setText("0 aktivnih zadataka")
        elif active_tasks == 1:
            self.sesija_value.setText("1 aktivan zadatak")
        else:
            self.sesija_value.setText(f"{active_tasks} aktivnih zadataka")

    def set_status(self, status: str):
        self._set_status_style(status)
        index = self.status_combo.findText(status)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)
