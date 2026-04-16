"""
Zaglavlje Template Dialog

Prikazuje korisniku:
- Koji XML template je nađen (pošiljalac, score, filename)
- Koja polja su auto-popunjena
- Koja polja još trebaju ručni unos

Korisnik može prihvatiti ili odbaciti template.
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)

# Polja koja uvijek trebaju ručni unos
MANUAL_FIELDS = {
    "ref_br":           "Rb.7 — Referentni broj",
    "transport_id":     "Rb.18 — Tablica vozila",
    "aktivno_transport": "Rb.21 — Aktivno transportno sredstvo",
    "rb40_broj":        "Rb.40 — Broj prethodnog dokumenta",
    "trosak_1":         "Troškovi — Vanjski prevoz",
    "trosak_2":         "Troškovi — Osiguranje",
    "trosak_3":         "Troškovi — Ostali troškovi",
    "trosak_4":         "Troškovi — Unutrašnji prevoz",
    "trosak_5":         "Troškovi — Odbitci",
}

# Čitljivi nazivi za auto-popunjena polja
FIELD_LABELS = {
    "deklaracija_tip":        "Rb.1 — Tip deklaracije",
    "deklaracija_oznaka":     "Rb.1 — Oznaka",
    "deklaracija_a":          "Rb.1 — Tip A/Z/B",
    "ured_odredista":         "Rb.1 — Ured odredišta",
    "izvoznik_id":            "Rb.2 — Izvoznik ID",
    "izvoznik_naziv":         "Rb.2 — Izvoznik naziv",
    "izvoznik_grad":          "Rb.2 — Izvoznik grad",
    "izvoznik_drzava":        "Rb.2 — Izvoznik država",
    "primalac_id":            "Rb.8 — Primalac ID",
    "primalac_naziv":         "Rb.8 — Primalac naziv",
    "primalac_adresa":        "Rb.8 — Primalac adresa",
    "primalac_grad":          "Rb.8 — Primalac grad",
    "deklarant_id":           "Rb.14 — Deklarant ID",
    "deklarant_naziv":        "Rb.14 — Deklarant naziv",
    "deklarant_grad":         "Rb.14 — Deklarant grad",
    "deklarant_predstavnik":  "Rb.14 — Predstavnik",
    "kontejner":              "Rb.19 — Kontejner",
    "vid_unutra":             "Rb.25 — Vid unutrašnji",
    "vid_granica":            "Rb.26 — Vid granica",
    "mjesto_otvaraca":        "Rb.27 — Mjesto otvarača",
    "izlazna_carinarnica":    "Rb.29 — Izlazna carinarnica",
    "lokacija_robe":          "Rb.30 — Lokacija robe",
    "drzava_izvoza_sifra":    "Rb.15 — Država izvoza",
    "drzava_odredista_sifra": "Rb.17 — Država odredišta",
    "uslovi_kod":             "Rb.20 — Uslovi isporuke",
    "uslovi_mjesto":          "Rb.20 — Mjesto isporuke",
    "valuta":                 "Rb.22 — Valuta",
    "vrsta_trans_1":          "Rb.24 — Vrsta transakcije",
    "rb40_tip":               "Rb.40 — Tip dokumenta",
    "rb40_skracenica":        "Rb.40 — Šifra dokumenta",
    "odgodjeno_placanje":     "Rb.48 — Odgođeno plaćanje",
    "identifikacija_skladista": "Rb.49 — Skladište",
}


class ZaglavljeTemplateDialog(QDialog):
    """
    Dijalog koji prikazuje rezultat XML template pretrage.

    Prihvata ili odbacuje primjenu template polja na draft.
    """

    def __init__(self, template_match, applied_fields: list, parent=None):
        """
        Args:
            template_match: TemplateMatch objekat sa info o nađenom XML-u
            applied_fields: Lista naziva polja koja su popunjena
            parent: Parent widget
        """
        super().__init__(parent)
        self.template_match = template_match
        self.applied_fields = applied_fields

        self.setWindowTitle("📋 Zaglavlje popunjeno iz istorije")
        self.setMinimumSize(600, 500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Header info ──────────────────────────────────────────
        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background: #e8f4fd; border: 1px solid #b8d4e8; border-radius: 6px; padding: 8px; }"
        )
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(4)

        score_pct = int(self.template_match.match_score * 100)
        score_color = "#155724" if score_pct >= 80 else "#856404" if score_pct >= 60 else "#721c24"

        info_layout.addWidget(QLabel(
            f"<b>Nađen template:</b> {self.template_match.filename}"
        ))
        info_layout.addWidget(QLabel(
            f"<b>Pošiljalac:</b> {self.template_match.exporter_name}"
        ))
        info_layout.addWidget(QLabel(
            f"<b>Poklapanje:</b> <span style='color:{score_color}'>{score_pct}%</span>"
        ))
        layout.addWidget(info_frame)

        # ── Auto-popunjena polja ──────────────────────────────────
        layout.addWidget(QLabel("<b>✅ Auto-popunjena polja:</b>"))

        auto_table = QTableWidget()
        auto_table.setColumnCount(2)
        auto_table.setHorizontalHeaderLabels(["Rubrika", "Vrijednost"])
        auto_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        auto_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        auto_table.setEditTriggers(QTableWidget.NoEditTriggers)
        auto_table.setMaximumHeight(180)

        green = QColor("#d4edda")
        for field_name in self.applied_fields:
            label = FIELD_LABELS.get(field_name, field_name)
            value = self.template_match.fields.get(field_name, "")
            row = auto_table.rowCount()
            auto_table.insertRow(row)
            item_label = QTableWidgetItem(label)
            item_value = QTableWidgetItem(str(value))
            item_label.setBackground(green)
            item_value.setBackground(green)
            auto_table.setItem(row, 0, item_label)
            auto_table.setItem(row, 1, item_value)

        layout.addWidget(auto_table)

        # ── Polja za ručni unos ───────────────────────────────────
        layout.addWidget(QLabel("<b>⚠️ Polja koja trebaju ručni unos (u Zaglavlje tabu):</b>"))

        manual_table = QTableWidget()
        manual_table.setColumnCount(1)
        manual_table.setHorizontalHeaderLabels(["Rubrika"])
        manual_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        manual_table.setEditTriggers(QTableWidget.NoEditTriggers)
        manual_table.setMaximumHeight(160)

        yellow = QColor("#fff3cd")
        for field_name, label in MANUAL_FIELDS.items():
            row = manual_table.rowCount()
            manual_table.insertRow(row)
            item = QTableWidgetItem(label)
            item.setBackground(yellow)
            manual_table.setItem(row, 0, item)

        layout.addWidget(manual_table)

        # ── Dugmad ───────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_odbaci = QPushButton("❌ Odbaci template")
        btn_odbaci.setStyleSheet(
            "QPushButton { background: #dc3545; color: white; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background: #c82333; }"
        )
        btn_odbaci.clicked.connect(self.reject)

        btn_prihvati = QPushButton("✅ Prihvati i nastavi")
        btn_prihvati.setStyleSheet(
            "QPushButton { background: #28a745; color: white; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background: #218838; }"
        )
        btn_prihvati.setDefault(True)
        btn_prihvati.clicked.connect(self.accept)

        btn_layout.addWidget(btn_odbaci)
        btn_layout.addWidget(btn_prihvati)
        layout.addLayout(btn_layout)
