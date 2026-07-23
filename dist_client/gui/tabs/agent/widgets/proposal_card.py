# gui/tabs/agent/widgets/proposal_card.py
"""
ProposalCardWidget — editabilna kartica prijedloga u Agent tabu.

Prikazuje se između chat prikaza i input polja kad agent generiše
strukturisani prijedlog. Korisnik može:
  - pregledati prijedlog
  - izmijeniti vrijednosti direktno u kartici
  - kliknuti Potvrdi ili Odbaci

Signal: confirmed(dict)  — emituje {key: value} mapu potvrđenih vrijednosti
Signal: rejected()       — korisnik odbacio prijedlog
"""

from __future__ import annotations
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QScrollArea, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ..constants import (
    COLOR_SAGE_DARK, COLOR_SAGE_PALE, COLOR_SAGE_BG, COLOR_SAGE_CARD,
    COLOR_TEXT, COLOR_TEXT_MUTED, COLOR_SUCCESS, COLOR_DANGER,
    COLOR_WARNING, COLOR_SECONDARY, COLOR_SAGE,
)


class ProposalCardWidget(QFrame):
    """
    Kartica prijedloga sa editabilnim poljima.

    proposal dict format:
    {
        'title': str,
        'subtitle': str,          # opcionalno
        'confidence': float,      # 0.0–1.0, opcionalno
        'fields': [
            {
                'label': str,
                'key': str | None,   # None = prikaz samo (confidence, metoda...)
                'value': str,
                'editable': bool,
                'placeholder': str,  # opcionalno
            },
            ...
        ],
        'apply_label': str,   # tekst dugmeta, default "Potvrdi i primijeni"
        'scope': str,         # info string npr. "sve stavke", "stavka 3"
    }
    """

    confirmed = Signal(dict)   # {key: value, ...}
    rejected = Signal()

    def __init__(self, proposal: Dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self._proposal = proposal
        self._inputs: Dict[str, QLineEdit] = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("ProposalCard")
        self.setStyleSheet(f"""
            QFrame#ProposalCard {{
                background-color: {COLOR_SAGE_CARD};
                border-top: 2px solid {COLOR_SAGE};
                border-bottom: 1px solid {COLOR_SAGE_PALE};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(8)

        # ── Naslov ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_text = self._proposal.get('title', 'Prijedlog')
        title_lbl = QLabel(f"📋 {title_text}")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(f"color: {COLOR_SAGE_DARK};")
        header_row.addWidget(title_lbl)

        # Confidence badge
        conf = self._proposal.get('confidence')
        if conf is not None:
            pct = int(conf * 100)
            if pct >= 90:
                badge_color, badge_bg = "#2f7d5b", "#e2f1e9"
            elif pct >= 70:
                badge_color, badge_bg = "#8a641f", "#f7efd9"
            else:
                badge_color, badge_bg = "#943535", "#f5e3e3"
            conf_lbl = QLabel(f"  {pct}%  ")
            conf_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {badge_color};
                    background-color: {badge_bg};
                    border-radius: 8px;
                    padding: 2px 6px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
            header_row.addWidget(conf_lbl)

        header_row.addStretch()

        # Scope info
        scope = self._proposal.get('scope', '')
        if scope:
            scope_lbl = QLabel(scope)
            scope_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
            header_row.addWidget(scope_lbl)

        outer.addLayout(header_row)

        # Subtitle
        subtitle = self._proposal.get('subtitle', '')
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
            sub_lbl.setWordWrap(True)
            outer.addWidget(sub_lbl)

        # ── Separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {COLOR_SAGE_PALE};")
        outer.addWidget(sep)

        # ── Polja u scroll area ───────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(160)
        scroll.setStyleSheet("background: transparent;")

        fields_widget = QWidget()
        fields_widget.setStyleSheet("background: transparent;")
        form = QFormLayout(fields_widget)
        form.setContentsMargins(0, 4, 0, 4)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        for fld in self._proposal.get('fields', []):
            label_text = fld.get('label', '')
            key = fld.get('key')
            value = str(fld.get('value', ''))
            editable = fld.get('editable', True)

            label_w = QLabel(label_text + ":")
            label_w.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")

            if not editable or key is None:
                # Read-only prikaz
                value_w = QLabel(value)
                value_w.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 12px; font-weight: bold;")
                value_w.setWordWrap(True)
            else:
                value_w = QLineEdit(value)
                value_w.setPlaceholderText(fld.get('placeholder', ''))
                value_w.setStyleSheet(f"""
                    QLineEdit {{
                        border: 1px solid {COLOR_SAGE_PALE};
                        border-radius: 4px;
                        padding: 3px 6px;
                        font-size: 12px;
                        background: white;
                        color: {COLOR_TEXT};
                        min-width: 160px;
                    }}
                    QLineEdit:focus {{
                        border-color: {COLOR_SAGE};
                    }}
                """)
                self._inputs[key] = value_w

            form.addRow(label_w, value_w)

        scroll.setWidget(fields_widget)
        outer.addWidget(scroll)

        # ── Dugmad ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        apply_label = self._proposal.get('apply_label', 'Potvrdi i primijeni')
        confirm_btn = QPushButton(f"✅  {apply_label}")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #286a4e; }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)

        reject_btn = QPushButton("✕  Odbaci")
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_TEXT_MUTED};
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLOR_DANGER};
                border-color: {COLOR_DANGER};
            }}
        """)
        reject_btn.clicked.connect(self._on_reject)

        btn_row.addWidget(reject_btn)
        btn_row.addWidget(confirm_btn)
        outer.addLayout(btn_row)

    def _on_confirm(self):
        """Skupi vrijednosti iz svih editabilnih polja i emituj signal."""
        values = {}
        for key, widget in self._inputs.items():
            values[key] = widget.text().strip()
        self.confirmed.emit(values)

    def _on_reject(self):
        self.rejected.emit()

    def get_values(self) -> Dict[str, str]:
        return {k: w.text().strip() for k, w in self._inputs.items()}
