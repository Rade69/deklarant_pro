"""
TariffValidationDialog — ne-modalni dijaloški prozor za istorijsku validaciju tarifa.

Prikazuje poređenje trenutnih tarifnih brojeva sa istorijski odobrenim (iz XML deklaracija).
Korisnik može prihvatiti prijedlog per-stavka ili sve odjednom.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication


class TariffValidationDialog(QDialog):
    """
    Ne-modalni dialog za prikaz istorijske validacije tarifnih brojeva.

    Signals:
        tariffs_accepted(list): lista (line_index, tarifni_broj) za prihvaćene promjene
    """

    tariffs_accepted = Signal(list)

    def __init__(self, matches: list, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Istorijska validacija tarifnih brojeva")
        self.setMinimumSize(820, 540)
        self.resize(920, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(False)

        self._matches = matches
        self._checkboxes: dict[int, tuple] = {}  # line_index → (match, btn)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        # Header
        layout.addWidget(self._make_header())

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d0d5dd;")
        layout.addWidget(sep)

        # Scroll area s prijedlozima
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #f9fafb; }
            QScrollBar:vertical { width: 8px; background: #f0f0f0; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #c0c8d8; border-radius: 4px; }
        """)

        content = QWidget()
        content.setAttribute(Qt.WA_StyledBackground, True)
        content.setStyleSheet("QWidget { background: #f9fafb; }")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(8)

        for match in self._matches:
            self._content_layout.addWidget(self._make_row(match))

        self._content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Dugmad
        layout.addWidget(self._make_buttons())

    def _make_header(self) -> QWidget:
        container = QWidget()
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setStyleSheet("""
            QWidget { background: #F0F4FA; border-radius: 8px; }
            QLabel  { background: transparent; }
        """)
        row = QHBoxLayout(container)
        row.setContentsMargins(12, 10, 12, 10)

        n = len(self._matches)
        title = QLabel(f"<b>Istorijska validacija tarifnih brojeva</b>")
        title.setStyleSheet("font-size: 16px;")

        subtitle = QLabel(
            f"{n} stavki ima drugi istorijski tarif (iz odobrenih XML deklaracija)"
        )
        subtitle.setStyleSheet("color: #6b7280; font-size: 14px;")

        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(title)
        left.addWidget(subtitle)

        row.addLayout(left)
        row.addStretch()
        return container

    def _make_row(self, match) -> QWidget:
        """Jedan red u tabeli — jedna stavka fakture."""
        from services.agent.validation.historical_tariff_search_service import TariffHistoryMatch
        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e0e4ea;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(10)

        # Lijeva kolona — info
        info = QVBoxLayout()
        info.setSpacing(3)

        rb = match.line_index + 1
        naziv_label = QLabel(
            f"<b>Rb.{rb}</b> — {match.naziv_robe_original[:60]}"
        )
        naziv_label.setStyleSheet("font-size: 15px;")

        # Poređenje tarifa
        if match.tarifni_broj_trenutni:
            tarif_html = (
                f"Trenutni: <code style='color:#b05050;'>{match.tarifni_broj_trenutni}</code>"
                f" &nbsp;→&nbsp; "
                f"Istorijski: <code style='color:#1E3A5F; font-weight:bold;'>"
                f"{match.tarifni_broj_historijski}</code>"
            )
        else:
            tarif_html = (
                f"Nema tarifa &nbsp;→&nbsp; "
                f"Istorijski: <code style='color:#1E3A5F; font-weight:bold;'>"
                f"{match.tarifni_broj_historijski}</code>"
            )
        tarif_label = QLabel(tarif_html)
        tarif_label.setTextFormat(Qt.RichText)
        tarif_label.setStyleSheet("font-size: 14px;")

        # Meta info
        source_txt = match.source[:40] if match.source else "—"
        pct = int(match.confidence * 100)
        meta_label = QLabel(
            f"<span style='color:#888; font-size:13px;'>"
            f"Izvor: {source_txt} &nbsp;|&nbsp; "
            f"Korišten {match.usage_count}× &nbsp;|&nbsp; "
            f"Pouzdanost: {pct}%"
            f"</span>"
        )
        meta_label.setTextFormat(Qt.RichText)

        reason = getattr(match, "decision_reason", "") or "Istorijski zapis prosao filter pouzdanosti."
        reason_label = QLabel(f"<span style='color:#6b7280; font-size:13px;'>Razlog: {reason[:90]}</span>")
        reason_label.setTextFormat(Qt.RichText)
        reason_label.setWordWrap(True)

        weak_label = None
        if self._is_weak_match(match):
            weak_label = QLabel(
                "<span style='color:#9a6700; font-size:13px;'>Oprez: slabiji prijedlog</span>"
            )
            weak_label.setTextFormat(Qt.RichText)

        hist_naziv = match.naziv_robe_historijski[:70]
        hist_label = QLabel(f"<span style='color:#888; font-size:13px;'>Naziv u bazi: {hist_naziv}</span>")
        hist_label.setTextFormat(Qt.RichText)
        hist_label.setWordWrap(True)

        info.addWidget(naziv_label)
        info.addWidget(tarif_label)
        info.addWidget(meta_label)
        info.addWidget(reason_label)
        if weak_label is not None:
            info.addWidget(weak_label)
        info.addWidget(hist_label)

        # Desna kolona — dugme Prihvati
        accept_btn = QPushButton("Prihvati")
        accept_btn.setCursor(Qt.PointingHandCursor)
        accept_btn.setFixedWidth(110)
        accept_btn.setStyleSheet("""
            QPushButton {
                background: #1E3A5F; color: white;
                border: none; border-radius: 6px;
                padding: 8px 0; font-size: 14px; font-weight: 600;
            }
            QPushButton:hover { background: #2D5A8E; }
            QPushButton:disabled {
                background: #d1fae5; color: #2d6a30;
                border: 1px solid #a7f3d0;
            }
        """)
        accept_btn.clicked.connect(
            lambda _, m=match, b=accept_btn: self._accept_one(m, b)
        )

        self._checkboxes[match.line_index] = (match, accept_btn)

        layout.addLayout(info, stretch=1)
        layout.addWidget(accept_btn, alignment=Qt.AlignVCenter)
        return card

    def _make_buttons(self) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        copy_btn = QPushButton("Kopiraj izvještaj")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(self._btn_style(secondary=True))
        copy_btn.clicked.connect(self._copy_report)

        strong_count = self._accept_all_pending_count()
        accept_all_btn = QPushButton(f"Prihvati jake ({strong_count})")
        accept_all_btn.setCursor(Qt.PointingHandCursor)
        accept_all_btn.setStyleSheet(self._btn_style(secondary=False))
        accept_all_btn.clicked.connect(self._accept_all)
        self._accept_all_btn = accept_all_btn
        self._update_accept_all_btn()

        close_btn = QPushButton("Zatvori")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(self._btn_style(secondary=True))
        close_btn.clicked.connect(self.close)

        row.addWidget(copy_btn)
        row.addStretch()
        row.addWidget(accept_all_btn)
        row.addWidget(close_btn)
        return container

    # ------------------------------------------------------------------
    # Akcije
    # ------------------------------------------------------------------

    def _accept_one(self, match, btn: QPushButton):
        btn.setText("✓ Prihvaceno")
        btn.setEnabled(False)
        self.tariffs_accepted.emit([(match.line_index, match.tarifni_broj_historijski)])
        self._update_accept_all_btn()

    def _accept_all(self):
        changes = []
        for line_index, (match, btn) in self._checkboxes.items():
            if btn.isEnabled() and self._can_accept_all(match):
                btn.setText("✓ Prihvaceno")
                btn.setEnabled(False)
                changes.append((line_index, match.tarifni_broj_historijski))
        if changes:
            self.tariffs_accepted.emit(changes)
        self._update_accept_all_btn()

    def _update_accept_all_btn(self):
        pending = self._accept_all_pending_count()
        if pending == 0:
            self._accept_all_btn.setEnabled(False)
            self._accept_all_btn.setText("Svi jaki prihvaceni")
        else:
            self._accept_all_btn.setText(f"Prihvati jake ({pending})")

    def _accept_all_pending_count(self) -> int:
        return sum(
            1 for match, btn in self._checkboxes.values()
            if btn.isEnabled() and self._can_accept_all(match)
        )

    @staticmethod
    def _is_weak_match(match) -> bool:
        return getattr(match, "decision_outcome", "") == "show_weak"

    def _can_accept_all(self, match) -> bool:
        return not self._is_weak_match(match)

    def _copy_report(self):
        lines = []
        for match in self._matches:
            rb = match.line_index + 1
            lines.append(
                f"Rb.{rb} — {match.naziv_robe_original[:50]}\n"
                f"  Trenutni: {match.tarifni_broj_trenutni or '—'} → "
                f"Istorijski: {match.tarifni_broj_historijski} "
                f"(korišten {match.usage_count}×, {int(match.confidence*100)}%)\n"
                f"  Razlog: {getattr(match, 'decision_reason', '') or 'prosao filter pouzdanosti'}"
            )
        QGuiApplication.clipboard().setText("\n\n".join(lines))

    @staticmethod
    def _btn_style(secondary: bool) -> str:
        if secondary:
            return """
                QPushButton {
                    background: #ffffff; color: #374151;
                    border: 1px solid #d1d5db; border-radius: 6px;
                    padding: 6px 16px; font-size: 13px;
                }
                QPushButton:hover { background: #f3f4f6; }
            """
        return """
            QPushButton {
                background: #1E3A5F; color: #ffffff;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #2D5A8E; }
            QPushButton:disabled { background: #9ca3af; }
        """
