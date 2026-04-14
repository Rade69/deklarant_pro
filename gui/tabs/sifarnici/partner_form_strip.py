# gui/tabs/sifarnici/partner_form_strip.py

"""
Info-strip forma za partnere (Pošiljaoci / Uvoznici).

Kompaktni 2-panel layout sa JIB/Naziv header-om,
lijevom panelom (Adresa, Grad, Zemlja) i desnim
panelom (Telefon, Email, JIB, Matični, Kontakt).
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QFrame,
)
from PySide6.QtCore import Qt


# ============================================================
# SECTION: partner-form-strip
# PURPOSE: Reusable info-strip widget for partner data entry
# DOC: docs/sections/partner-form-strip.md
# ============================================================

_FIELD_STYLE = (
    "QLineEdit { background: white; border: 1px solid #c8cdd4; "
    "border-radius: 3px; padding: 4px 7px; font-size: 12px; }"
    "QLineEdit:focus { border: 1px solid #2196F3; }"
    "QLineEdit:read-only { background: #f5f5f5; color: #555; }"
)
_LABEL_STYLE = "color: #4a5568; font-size: 12px; font-weight: bold;"


class PartnerFormStrip(QWidget):
    """Info-strip za partnere — Pošiljaoci i Uvoznici.

    Layout:
      ┌ JIB / Naziv header ─────────────────────────────────┐
      ├────────────────────────┬────────────────────────────┤
      │ Adresa                 │ Telefon                    │
      │ Grad + PTT             │ Email                      │
      │ Zemlja                 │ JIB (13 cifara)            │
      │                        │ Matični                    │
      │                        │ Kontakt                    │
      └────────────────────────┴────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("partner_strip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#partner_strip { border: 1px solid #c8cdd4; "
            "border-radius: 4px; background: white; }"
        )

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(1, 1, 1, 1)

        # ── Header: JIB + Naziv ────────────────────────────
        header = self._create_header()
        outer.addWidget(header)

        # ── Body: Adresa | Kontakt ─────────────────────────
        body = self._create_body()
        outer.addWidget(body)

    # ── Public API ─────────────────────────────────────────

    @property
    def jib_field(self) -> QLineEdit:
        return self._jib_field

    @property
    def naziv_field(self) -> QLineEdit:
        return self._naziv_field

    @property
    def adresa_field(self) -> QLineEdit:
        return self._adresa_field

    @property
    def grad_field(self) -> QLineEdit:
        return self._grad_field

    @property
    def postanski_broj_field(self) -> QLineEdit:
        return self._postanski_broj_field

    @property
    def zemlja_field(self) -> QLineEdit:
        return self._zemlja_field

    @property
    def telefon_field(self) -> QLineEdit:
        return self._telefon_field

    @property
    def email_field(self) -> QLineEdit:
        return self._email_field

    @property
    def pdv_field(self) -> QLineEdit:
        """JIB (13 cifara) = '4' + PDV (12 cifara)."""
        return self._pdv_field

    @property
    def maticni_field(self) -> QLineEdit:
        return self._maticni_field

    @property
    def kontakt_field(self) -> QLineEdit:
        return self._kontakt_field

    # ── Private ────────────────────────────────────────────

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("strip_header")
        header.setStyleSheet(
            "QWidget#strip_header { background: #eef2f7; "
            "border-bottom: 1px solid #d0d5db; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 9, 14, 9)
        h_layout.setSpacing(6)

        lbl_jib = QLabel("PDV:")
        lbl_jib.setStyleSheet(_LABEL_STYLE)
        lbl_jib.setFixedWidth(32)
        self._jib_field = QLineEdit()
        self._jib_field.setFixedWidth(175)
        self._jib_field.setStyleSheet(_FIELD_STYLE)
        self._jib_field.setPlaceholderText("JIB broj")

        lbl_naziv = QLabel("Naziv:")
        lbl_naziv.setStyleSheet(_LABEL_STYLE)
        lbl_naziv.setFixedWidth(44)
        self._naziv_field = QLineEdit()
        self._naziv_field.setStyleSheet(_FIELD_STYLE)
        self._naziv_field.setPlaceholderText("Naziv firme")

        h_layout.addWidget(lbl_jib)
        h_layout.addWidget(self._jib_field)
        h_layout.addSpacing(18)
        h_layout.addWidget(lbl_naziv)
        h_layout.addWidget(self._naziv_field, 1)
        return header

    def _create_body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet("background: white;")
        b_layout = QHBoxLayout(body)
        b_layout.setSpacing(0)
        b_layout.setContentsMargins(0, 0, 0, 0)

        left = self._create_left_panel()
        right = self._create_right_panel()

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #d0d5db;")

        b_layout.addWidget(left, 6)
        b_layout.addWidget(sep)
        b_layout.addWidget(right, 4)
        return body

    def _create_left_panel(self) -> QWidget:
        left = QWidget()
        left.setStyleSheet("QLabel { color: #4a5568; font-size: 12px; }")
        lf = QFormLayout(left)
        lf.setContentsMargins(14, 10, 14, 10)
        lf.setSpacing(9)
        lf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._adresa_field = QLineEdit()
        self._adresa_field.setStyleSheet(_FIELD_STYLE)

        grad_row = QWidget()
        gr_lay = QHBoxLayout(grad_row)
        gr_lay.setContentsMargins(0, 0, 0, 0)
        gr_lay.setSpacing(6)
        self._grad_field = QLineEdit()
        self._grad_field.setStyleSheet(_FIELD_STYLE)
        ptt_lbl = QLabel("PTT:")
        ptt_lbl.setFixedWidth(30)
        ptt_lbl.setStyleSheet("color: #666; font-size: 11px;")
        self._postanski_broj_field = QLineEdit()
        self._postanski_broj_field.setFixedWidth(68)
        self._postanski_broj_field.setStyleSheet(_FIELD_STYLE)
        gr_lay.addWidget(self._grad_field, 2)
        gr_lay.addWidget(ptt_lbl)
        gr_lay.addWidget(self._postanski_broj_field)

        self._zemlja_field = QLineEdit()
        self._zemlja_field.setStyleSheet(_FIELD_STYLE)

        lf.addRow("Adresa:", self._adresa_field)
        lf.addRow("Grad:", grad_row)
        lf.addRow("Zemlja:", self._zemlja_field)
        return left

    def _create_right_panel(self) -> QWidget:
        right = QWidget()
        right.setStyleSheet("QLabel { color: #4a5568; font-size: 12px; }")
        rf = QFormLayout(right)
        rf.setContentsMargins(14, 10, 14, 10)
        rf.setSpacing(9)
        rf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._telefon_field = QLineEdit()
        self._telefon_field.setStyleSheet(_FIELD_STYLE)
        self._email_field = QLineEdit()
        self._email_field.setStyleSheet(_FIELD_STYLE)
        self._pdv_field = QLineEdit()
        self._pdv_field.setStyleSheet(_FIELD_STYLE)
        self._maticni_field = QLineEdit()
        self._maticni_field.setStyleSheet(_FIELD_STYLE)
        self._kontakt_field = QLineEdit()
        self._kontakt_field.setStyleSheet(_FIELD_STYLE)

        rf.addRow("Telefon:", self._telefon_field)
        rf.addRow("Email:", self._email_field)
        rf.addRow("JIB:", self._pdv_field)
        rf.addRow("Matični:", self._maticni_field)
        rf.addRow("Kontakt:", self._kontakt_field)
        return right
