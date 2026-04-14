# core/utils/ui_helper.py

"""
UIHelper — generički helper za UI komponente sa stilizacijom.

Kreira dugmad, akcione widgete i druge UI elemente sa
unified_color_system qss paletom i QtAwesome ikonicama.
"""

from typing import Callable

from PySide6.QtWidgets import QPushButton, QToolButton, QWidget, QHBoxLayout
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

try:
    import qtawesome as qta
    QTAWESOME_AVAILABLE = True
except ImportError:
    QTAWESOME_AVAILABLE = False


# ============================================================
# SECTION: ui-helper
# PURPOSE: Reusable UI component factory with consistent styling
# DOC: docs/sections/ui-helper.md
# ============================================================


class UIHelper:
    """Helper klase za UI komponente sa stilizacijom.

    Mapiranje style_class → objectName odgovara unified_color_system.qss paleti:
    - primary: default plava (base QPushButton) → Uredi
    - success: zelena → Novi / Dodaj
    - danger: crvena → Obriši
    - default: zelena → Snimi
    """

    BUTTON_OBJECT_NAMES = {
        "primary": "",               # default plava (base QPushButton) → Uredi
        "success": "btnDodaj",       # zelena → Novi
        "danger":  "btnObrisi",      # crvena → Obriši
        "default": "btnSnimi",       # zelena → Snimi
    }

    @classmethod
    def create_styled_button(
        cls, text: str, style_class: str = "default", icon_name: str = ""
    ) -> QPushButton:
        """Kreira stilizovano dugme sa QtAwesome ikonicom.

        Args:
            text: Tekst na dugmetu
            style_class: Stil klase (primary, success, danger, default)
            icon_name: QtAwesome ime ikone (npr. 'fa5s.plus-square')

        Returns:
            QPushButton instanca sa objectName za QSS stilizaciju
        """
        btn_text = (" " + text) if icon_name else text
        button = QPushButton(btn_text)
        button.setObjectName(cls.BUTTON_OBJECT_NAMES.get(style_class, ""))

        if icon_name and QTAWESOME_AVAILABLE:
            try:
                qta_icon = qta.icon(icon_name, color="#FFFFFF")
                pixmap = qta_icon.pixmap(QSize(16, 16))
                button.setIcon(QIcon(pixmap))
                button.setIconSize(QSize(16, 16))
            except Exception:
                pass

        return button

    @classmethod
    def create_action_buttons(
        cls, parent, edit_callback: Callable, delete_callback: Callable
    ) -> QWidget:
        """Kreira akciona dugmad (✏️ Uredi, 🗑️ Obriši) za tabelu.

        Args:
            parent: Parent widget
            edit_callback: Callback za edit akciju
            delete_callback: Callback za delete akciju

        Returns:
            QWidget sa akcionim dugmadima
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Edit button
        btn_edit = QToolButton()
        btn_edit.setText("✏️")
        btn_edit.setToolTip("Uredi")
        btn_edit.setStyleSheet(
            """
            QToolButton {
                background: #007bff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background: #0056b3;
            }
        """
        )
        btn_edit.clicked.connect(edit_callback)

        # Delete button
        btn_delete = QToolButton()
        btn_delete.setText("🗑️")
        btn_delete.setToolTip("Obriši")
        btn_delete.setStyleSheet(
            """
            QToolButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background: #bd2130;
            }
        """
        )
        btn_delete.clicked.connect(delete_callback)

        layout.addWidget(btn_edit)
        layout.addWidget(btn_delete)
        layout.addStretch()

        return widget
