"""
Navigator za kretanje između više draftova deklaracija (po zemljama porijekla).

Prikazuje se između toolbar-a i tabele u FakturaView, vidljiv samo kad
postoje 2+ drafta. Emituje signal draft_changed(int) pri navigaciji.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from core.draft.draft import DeclarationDraft
from services.faktura.declaration_split_service import group_label


class MultiDraftNavigator(QWidget):
    """
    Traka oblika:
      ◀  Deklaracija 1 od 3: Turska (TR) • 29 stavki  ▶
    """

    draft_changed = Signal(int)  # index novog drafta

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drafts: List[DeclarationDraft] = []
        self._index: int = 0
        self._build_ui()
        self.hide()

    # ------------------------------------------------------------------
    # Javni API
    # ------------------------------------------------------------------

    def load_drafts(self, drafts: List[DeclarationDraft], start_index: int = 0) -> None:
        """Postavi listu draftova i prikaži navigator ako ih ima više od 1."""
        self._drafts = drafts
        self._index = max(0, min(start_index, len(drafts) - 1))
        self._refresh()
        self.setVisible(len(drafts) > 1)

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def current_draft(self) -> DeclarationDraft | None:
        if not self._drafts:
            return None
        return self._drafts[self._index]

    # ------------------------------------------------------------------
    # Interna implementacija
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Frame koji vizuelno ograničava traku
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #EDE4F5; border: 1px solid #C4A8E8; border-radius: 6px; }"
        )
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 4, 10, 4)
        frame_layout.setSpacing(10)

        # Ikona razdvajanja
        icon_label = QLabel("📂")
        icon_label.setFixedWidth(24)
        frame_layout.addWidget(icon_label)

        # Labela "Deklaracija po zemljama:"
        prefix = QLabel("Deklaracija po zemljama:")
        prefix.setStyleSheet("color: #4A2E6B; font-weight: bold;")
        frame_layout.addWidget(prefix)

        # Dugme nazad
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedSize(28, 28)
        self._btn_prev.setStyleSheet(
            "QPushButton { background: #C4A8E8; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #A87ED8; }"
            "QPushButton:disabled { background: #E0D0F5; color: #AAA; }"
        )
        self._btn_prev.clicked.connect(self._on_prev)
        frame_layout.addWidget(self._btn_prev)

        # Centralna labela sa informacijom
        self._lbl_info = QLabel()
        self._lbl_info.setAlignment(Qt.AlignCenter)
        self._lbl_info.setStyleSheet("color: #4A2E6B; font-size: 13px; min-width: 280px;")
        frame_layout.addWidget(self._lbl_info, stretch=1)

        # Dugme naprijed
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedSize(28, 28)
        self._btn_next.setStyleSheet(
            "QPushButton { background: #C4A8E8; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #A87ED8; }"
            "QPushButton:disabled { background: #E0D0F5; color: #AAA; }"
        )
        self._btn_next.clicked.connect(self._on_next)
        frame_layout.addWidget(self._btn_next)

        # Kratki pregled svih deklaracija
        self._lbl_summary = QLabel()
        self._lbl_summary.setStyleSheet("color: #7A5A9B; font-size: 11px;")
        self._lbl_summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        frame_layout.addWidget(self._lbl_summary)

        layout.addWidget(frame)

    def _refresh(self) -> None:
        if not self._drafts:
            return

        total = len(self._drafts)
        draft = self._drafts[self._index]
        country_group = getattr(draft, "_country_group", "")
        stavki = len(draft.invoice_lines)

        self._lbl_info.setText(
            f"<b>{self._index + 1} od {total}</b>  —  {group_label(country_group)}  •  {stavki} stavki"
        )

        # Summary svih deklaracija
        parts = []
        for i, d in enumerate(self._drafts):
            g = getattr(d, "_country_group", "")
            marker = "●" if i == self._index else "○"
            parts.append(f"{marker} {group_label(g)} ({len(d.invoice_lines)})")
        self._lbl_summary.setText("  ".join(parts))

        self._btn_prev.setEnabled(self._index > 0)
        self._btn_next.setEnabled(self._index < total - 1)

    def _on_prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._refresh()
            self.draft_changed.emit(self._index)

    def _on_next(self) -> None:
        if self._index < len(self._drafts) - 1:
            self._index += 1
            self._refresh()
            self.draft_changed.emit(self._index)
