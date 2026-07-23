"""
Upload area sa drag & drop i card-style mode selectorom.
Botanički Sage Green dizajn.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
import qtawesome as qta
from ..constants import *


class ModeCard(QFrame):
    """Jedna mode kartica — ikona + naslov + opis."""

    clicked = Signal(str)  # mode name

    def __init__(self, mode: str, icon_name: str, description: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._selected = False
        self._setup_ui(icon_name, description)

    def _setup_ui(self, icon_name: str, description: str):
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(102)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 7, 14, 7)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignHCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=COLOR_SAGE_DARK).pixmap(28, 28))
        icon_lbl.setFixedHeight(30)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent;")

        title_lbl = QLabel(self.mode)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {COLOR_TEXT};
            background: transparent;
        """)

        desc_lbl = QLabel(description)
        desc_lbl.setMinimumHeight(28)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"""
            font-size: 11px;
            color: {COLOR_TEXT_LIGHT};
            background: transparent;
        """)

        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)

        self._apply_style(False)

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                ModeCard {{
                    background-color: #eef5f9;
                    border: 2px solid {COLOR_SAGE};
                    border-radius: 8px;
                }}
                ModeCard:hover {{
                    background-color: {COLOR_SAGE_CARD};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ModeCard {{
                    background-color: {COLOR_SAGE_CARD};
                    border: 1px solid {COLOR_SAGE_PALE};
                    border-radius: 8px;
                }}
                ModeCard:hover {{
                    background-color: white;
                    border-color: {COLOR_SAGE_MID};
                }}
            """)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style(selected)

    def mousePressEvent(self, event):
        self.clicked.emit(self.mode)
        super().mousePressEvent(event)


class UploadArea(QWidget):
    """Upload + mode selektor."""

    files_dropped = Signal(list)
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode_cards = {}
        self._current_mode = "Analiza"
        self._setup_ui()

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"UploadArea {{ background-color: {COLOR_SAGE_BG}; }}")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ── Drop zona ─────────────────────────────────────────────────────────
        self.drop_frame = QFrame()
        self.drop_frame.setAcceptDrops(True)
        self.drop_frame.setMinimumHeight(145)
        self.drop_frame.setCursor(Qt.PointingHandCursor)
        self.drop_frame.mousePressEvent = lambda e: self._on_select_files()
        self._reset_drop_style()

        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setAlignment(Qt.AlignCenter)
        drop_layout.setSpacing(6)

        upload_icon = QLabel()
        upload_icon.setPixmap(qta.icon(ICON_UPLOAD, color=COLOR_SAGE).pixmap(44, 44))
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("background: transparent; border: none;")

        drop_title = QLabel("Prevuci dokumente ovdje")
        drop_title.setAlignment(Qt.AlignCenter)
        drop_title.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {COLOR_TEXT};
            background: transparent;
            border: none;
        """)

        drop_sub = QLabel(
            "PDF, Excel i XML fajlovi za automatsku analizu,\n"
            "tarifiranje i kreiranje naimenovanja"
        )
        drop_sub.setAlignment(Qt.AlignCenter)
        drop_sub.setStyleSheet(f"""
            font-size: 12px;
            color: {COLOR_TEXT_MUTED};
            background: transparent;
            border: none;
        """)

        drop_layout.addWidget(upload_icon)
        drop_layout.addWidget(drop_title)
        drop_layout.addWidget(drop_sub)

        layout.addWidget(self.drop_frame)

        # ── Dugmad ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_select = QPushButton(
            qta.icon(ICON_UPLOAD, color='white'), " Odaberi fajlove"
        )
        self.btn_select.clicked.connect(self._on_select_files)
        self.btn_select.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: white;
                padding: 9px 20px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2b648c; }}
        """)

        self.btn_analyze = QPushButton(
            qta.icon(ICON_PLAY, color='white'), " Pokreni analizu"
        )
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SECONDARY};
                color: white;
                padding: 9px 20px;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover:enabled {{ background-color: #583d86; }}
            QPushButton:disabled {{
                background-color: {COLOR_SAGE_PALE};
                color: {COLOR_TEXT_MUTED};
            }}
        """)

        btn_row.addWidget(self.btn_select)
        btn_row.addWidget(self.btn_analyze)
        btn_row.addStretch()

        # Clear btn
        self.btn_clear = QPushButton(qta.icon(ICON_TRASH, color=COLOR_DANGER), "")
        self.btn_clear.setFixedSize(36, 36)
        self.btn_clear.setToolTip("Očisti listu")
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 6px;
                background-color: white;
            }}
            QPushButton:hover {{
                background-color: #fde8e8;
                border-color: {COLOR_DANGER};
            }}
        """)
        btn_row.addWidget(self.btn_clear)

        layout.addLayout(btn_row)

        # Format info
        info = QLabel("Podržani formati: PDF, Excel (xlsx, xls), XML")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px; background: transparent;")
        layout.addWidget(info)

        # ── Mode kartice ──────────────────────────────────────────────────────
        mode_label = QLabel("Režim obrade")
        mode_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 12px;
            color: {COLOR_SAGE_DARK};
            background: transparent;
        """)
        layout.addWidget(mode_label)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        modes = [
            ("Analiza",              ICON_SEARCH, "Samo parsiranje i prijedlozi"),
            ("Uvezi u deklaraciju",  ICON_IMPORT, "Prenos validiranih podataka"),
            ("Puna automatizacija",  ICON_MAGIC,  "Parsiranje + prijedlog + unos"),
        ]

        for mode_name, icon_name, desc in modes:
            card = ModeCard(mode_name, icon_name, desc)
            card.set_selected(mode_name == self._current_mode)
            card.clicked.connect(self._on_mode_clicked)
            self._mode_cards[mode_name] = card
            cards_row.addWidget(card)

        layout.addLayout(cards_row)

    def _on_mode_clicked(self, mode: str):
        self._current_mode = mode
        for name, card in self._mode_cards.items():
            card.set_selected(name == mode)
        self.mode_changed.emit(mode)

    def get_mode(self) -> str:
        return self._current_mode

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_frame.setStyleSheet(f"""
                QFrame {{
                    border: 2px solid {COLOR_SUCCESS};
                    border-radius: 10px;
                    background-color: #e2f1e9;
                }}
            """)

    def dragLeaveEvent(self, event):
        self._reset_drop_style()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.lower().split('.')[-1] in ['pdf', 'xlsx', 'xls', 'xml']:
                files.append(filepath)
        if files:
            self.files_dropped.emit(files)
        self._reset_drop_style()

    def _reset_drop_style(self):
        self.drop_frame.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLOR_SAGE_MID};
                border-radius: 10px;
                background-color: {COLOR_SAGE_UPLOAD};
            }}
            QFrame:hover {{
                border-color: {COLOR_SAGE};
                background-color: {COLOR_SAGE_PANEL};
            }}
        """)

    def _on_select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Odaberi Fakture", "",
            "Svi podržani (*.pdf *.xlsx *.xls *.xml);;"
            "PDF (*.pdf);;Excel (*.xlsx *.xls);;XML (*.xml)"
        )
        if files:
            self.files_dropped.emit(files)

    def set_loading(self, loading: bool):
        """⭐ Postavi loading state - onemogući dugmad i pokaži spinner."""
        if loading:
            self.btn_analyze.setEnabled(False)
            self.btn_select.setEnabled(False)
            self.btn_analyze.setText(" ⏳ Procesiram...")
            self.btn_analyze.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_TEXT_MUTED};
                    color: white;
                    padding: 9px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            # Onemogući mode kartice
            for card in self._mode_cards.values():
                card.setEnabled(False)
        else:
            self.btn_analyze.setEnabled(True)
            self.btn_select.setEnabled(True)
            self.btn_analyze.setText(" Pokreni analizu")
            self.btn_analyze.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_SECONDARY};
                    color: white;
                    padding: 9px 20px;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover:enabled {{ background-color: #583d86; }}
                QPushButton:disabled {{
                    background-color: {COLOR_SAGE_PALE};
                    color: {COLOR_TEXT_MUTED};
                }}
            """)
            # Omogući mode kartice
            for card in self._mode_cards.values():
                card.setEnabled(True)
