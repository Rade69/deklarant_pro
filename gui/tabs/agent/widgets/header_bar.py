"""
Header bar sa statusom, parserom i sesija informacijama.
Botanički Sage Green dizajn.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Signal
import qtawesome as qta
from ..constants import *


class HeaderBar(QWidget):
    """Header bar — sage green, lagana i čista linija."""

    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

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
            btn.setFixedSize(32, 32)
            btn.setToolTip(tooltip)
            btn.setObjectName("iconBtn")
            layout.addWidget(btn)

        self.setStyleSheet(f"""
            HeaderBar {{
                background-color: {COLOR_SAGE_BG};
                border-bottom: 2px solid {COLOR_SAGE_PALE};
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
                border-radius: 16px;
                background-color: white;
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
            STATUS_READY:      (COLOR_SUCCESS,  "#d4edda"),
            STATUS_PROCESSING: (COLOR_INFO,     "#d0e8ff"),
            STATUS_COMPLETED:  (COLOR_SUCCESS,  "#d4edda"),
            STATUS_PAUSED:     (COLOR_WARNING,  "#fff3cd"),
            STATUS_ERROR:      (COLOR_DANGER,   "#f8d7da"),
        }
        fg, bg = colors.get(status, ("#333", "#e9ecef"))
        self.status_badge.setText(f"● {status}")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 10px;
                padding: 3px 12px;
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
