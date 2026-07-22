"""
gui/dialogs/inspection_dialog.py

Dijalog za prikaz naimenovanja koja zahtijevaju inspekciju.

Prikazuje:
- Pošiljalac, primalac, ukupni bruto i neto (na vrhu, jednom)
- Stavke grupisane po tipu inspekcije (sanitarna, veterinarska, fitosanitarna,
  kontrola kvaliteta, agencija za lijekove)
- Po stavki: naziv robe, JM, količina, neto kg, zemlja porijekla, tarifni broj

Napomena: Dijalog samo prikazuje podatke. Inspekcijski listovi se unose
ručno u odgovarajuće web aplikacije.
"""

from __future__ import annotations

import logging
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from services.inspection_service import (
    INSPECTION_ICONS,
    INSPECTION_LABELS,
    INSPECTION_ORDER,
    InspectionMatch,
    get_inspection_service,
)

logger = logging.getLogger("deklarant_pro.inspection_dialog")


class InspectionDialog(QDialog):
    """
    Dijalog za prikaz inspekcijskih zahtjeva za naimenovanja u deklaraciji.

    Korištenje:
        dlg = InspectionDialog(draft, parent=self)
        dlg.exec()
    """

    def __init__(self, draft: DeclarationDraft, parent=None):
        super().__init__(parent)
        self.draft = draft
        self._service = get_inspection_service()
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Inspekcijski pregled naimenovanja")
        self.setMinimumWidth(820)
        self.setMinimumHeight(600)
        self.resize(900, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        # --- Header blok (pošiljalac, primalac, ukupne mase) ---
        root.addWidget(self._build_header_block())

        # --- Scroll area sa stavkama po tipu inspekcije ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self._build_inspection_sections(content_layout)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        root.addWidget(scroll, stretch=1)

        # --- Dugme Zatvori ---
        btn_close = QPushButton("Zatvori")
        btn_close.setFixedWidth(120)
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _build_header_block(self) -> QFrame:
        """Blok sa pošiljaocm, primaocem i ukupnim masama."""
        frame = QFrame()
        frame.setObjectName("inspHeaderFrame")
        frame.setStyleSheet(
            "QFrame#inspHeaderFrame {"
            "  background: #f0f4f8;"
            "  border: 1px solid #d0d7de;"
            "  border-radius: 6px;"
            "  padding: 4px;"
            "}"
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        bold = QFont()
        bold.setBold(True)

        # Naslov
        title = QLabel("Podaci za inspekcijski list")
        title.setFont(bold)
        title.setStyleSheet("font-size: 13px; color: #2c3e50;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #d0d7de;")
        layout.addWidget(sep)

        # Pošiljalac
        posaljalac = self.draft.izvoznik_naziv or "—"
        row1 = QHBoxLayout()
        lbl_p = QLabel("Pošiljalac:")
        lbl_p.setFont(bold)
        lbl_p.setFixedWidth(100)
        row1.addWidget(lbl_p)
        row1.addWidget(QLabel(posaljalac))
        row1.addStretch()
        layout.addLayout(row1)

        # Primalac
        primalac = self.draft.primalac_naziv or "—"
        row2 = QHBoxLayout()
        lbl_r = QLabel("Primalac:")
        lbl_r.setFont(bold)
        lbl_r.setFixedWidth(100)
        row2.addWidget(lbl_r)
        row2.addWidget(QLabel(primalac))
        row2.addStretch()
        layout.addLayout(row2)

        # Ukupne mase iz naimenovanja
        total_bruto = sum(n.gross_mass_kg for n in self.draft.items)
        total_neto = sum(n.net_mass_kg for n in self.draft.items)

        row3 = QHBoxLayout()
        lbl_b = QLabel("Ukupno bruto:")
        lbl_b.setFont(bold)
        lbl_b.setFixedWidth(100)
        row3.addWidget(lbl_b)
        row3.addWidget(QLabel(f"{total_bruto:,.3f} kg"))
        row3.addSpacing(40)
        lbl_n = QLabel("Ukupno neto:")
        lbl_n.setFont(bold)
        row3.addWidget(lbl_n)
        row3.addWidget(QLabel(f"{total_neto:,.3f} kg"))
        row3.addStretch()
        layout.addLayout(row3)

        return frame

    def _build_inspection_sections(self, parent_layout: QVBoxLayout) -> None:
        """
        Grupiše naimenovanja po tipu inspekcije i kreira sekcije.
        Redoslijed: INSPECTION_ORDER.
        """
        items = self.draft.items
        if not items:
            lbl = QLabel("Nema naimenovanja u deklaraciji.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
            parent_layout.addWidget(lbl)
            return

        # Prikupi koji naimenovanja idu pod koji tip inspekcije
        # type_to_items: {inspection_type: [(naim, InspectionMatch)]}
        type_to_items: dict[str, list[tuple[NaimenovanjeDraft, InspectionMatch]]] = {
            t: [] for t in INSPECTION_ORDER
        }
        no_inspection: list[NaimenovanjeDraft] = []

        # Tipovi inspekcije koji pokrivaju hranu — ako naim ima bilo koji od ovih,
        # isključuje se iz quality_control (zdravstvena inspekcija nije za prehrambene)
        FOOD_TYPES = {"sanitary", "veterinary", "phytosanitary"}

        for naim in items:
            if not naim.tariff_code:
                no_inspection.append(naim)
                continue

            result = self._service.check(naim.tariff_code)
            if not result.requires_any_inspection:
                no_inspection.append(naim)
                continue

            has_food_inspection = any(m.inspection_type in FOOD_TYPES for m in result.matches)

            for match in result.matches:
                itype = match.inspection_type
                if itype not in type_to_items:
                    continue
                # Prehrambeni proizvodi ne idu u Zdravstvenu inspekciju
                if itype == "quality_control" and has_food_inspection:
                    continue
                type_to_items[itype].append((naim, match))

        # Kreiraj sekciju za svaki tip koji ima stavki
        has_any = False
        for itype in INSPECTION_ORDER:
            entries = type_to_items.get(itype, [])
            if not entries:
                continue
            has_any = True
            section = self._build_section(itype, entries)
            parent_layout.addWidget(section)

        if not has_any:
            lbl = QLabel("Nijedna stavka ne zahtijeva inspekciju na osnovu tarifnog broja.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
            parent_layout.addWidget(lbl)

        # Stavke bez tarifnog broja ili bez inspekcije
        if no_inspection:
            parent_layout.addWidget(self._build_no_inspection_note(no_inspection))

    def _build_section(
        self,
        itype: str,
        entries: list[tuple[NaimenovanjeDraft, InspectionMatch]],
    ) -> QFrame:
        """Jedna sekcija za jedan tip inspekcije sa tabelom stavki."""
        frame = QFrame()
        frame.setObjectName("inspSectionFrame")
        frame.setStyleSheet(
            "QFrame#inspSectionFrame {"
            "  border: 1px solid #d0d7de;"
            "  border-radius: 6px;"
            "}"
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Naslov sekcije ---
        icon = INSPECTION_ICONS.get(itype, "🔍")
        label = INSPECTION_LABELS.get(itype, itype)

        # Provjeri da li ima uslovnih
        has_conditional = any(m.is_conditional for _, m in entries)
        conditional_suffix = "  (uslovna pravila — provjeri uslov)" if has_conditional else ""

        title_widget = QWidget()
        title_widget.setObjectName("inspSectionTitle")
        title_color = self._section_color(itype)
        title_widget.setStyleSheet(
            f"QWidget#inspSectionTitle {{"
            f"  background: {title_color};"
            f"  border-radius: 5px 5px 0 0;"
            f"}}"
        )
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(12, 8, 12, 8)

        title_lbl = QLabel(f"{icon}  {label}{conditional_suffix}")
        title_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a1a2e;")
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()

        count_lbl = QLabel(f"{len(entries)} stavki")
        count_lbl.setStyleSheet("color: #555; font-size: 11px;")
        title_layout.addWidget(count_lbl)

        layout.addWidget(title_widget)

        # --- Tabela stavki ---
        table = self._build_table(entries, itype)
        layout.addWidget(table)

        # --- Uslovni tekst ako postoji ---
        for naim, match in entries:
            if match.condition_text:
                cond_lbl = QLabel(f"  ⚠️  Uslov: {match.condition_text}")
                cond_lbl.setStyleSheet(
                    "color: #856404; background: #fff3cd; padding: 4px 12px;"
                    "font-size: 11px;"
                )
                cond_lbl.setWordWrap(True)
                layout.addWidget(cond_lbl)
                break  # Prikaži jednom ako isti uslov dijele stavke iste sekcije

        # --- Istorijska napomena (informativno, ne zamjenjuje pravno pravilo) ---
        hist_note = self._build_historical_note(itype, entries)
        if hist_note:
            layout.addWidget(hist_note)

        return frame

    def _build_historical_note(
        self,
        itype: str,
        entries: list[tuple[NaimenovanjeDraft, InspectionMatch]],
    ) -> QLabel | None:
        """
        Istorijska (INFORMATIVNA) napomena — za tarifne brojeve u ovoj sekciji,
        koliko puta je baš ova vrsta inspekcije zabilježena u stvarnim prošlim
        ASYCUDA deklaracijama (catalogs.inspection_document_history). NIKAD ne
        mijenja niti suprimira pravno pravilo iznad (tabela/uslov) — samo
        dodatni kontekst. Vraća None ako nema podatka (bez fallback nagađanja).

        Vidi project_rooms/2026-07-22_istorijska-napomena-inspekcije.md.
        """
        seen_tariffs: dict[str, int] = {}
        for naim, _ in entries:
            tarif = naim.tariff_code or ""
            if not tarif or tarif in seen_tariffs:
                continue
            for hint in self._service.historical_hint(tarif):
                if hint.inspection_type == itype:
                    seen_tariffs[tarif] = hint.usage_count
                    break

        if not seen_tariffs:
            return None

        parts = ", ".join(f"{t} ({c}x)" for t, c in seen_tariffs.items())
        lbl = QLabel(
            f"📊 Istorijski podatak (informativno, ne zamjenjuje pravno pravilo): "
            f"tarifni broj(evi) {parts} — ranije zabilježeno u stvarnim deklaracijama."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color: #555; font-size: 11px; background: #eef2f7; "
            "padding: 4px 12px; border-top: 1px solid #d0d7de;"
        )
        return lbl

    def _build_table(
        self,
        entries: list[tuple[NaimenovanjeDraft, InspectionMatch]],
        itype: str,
    ) -> QTableWidget:
        """Tabela sa kolonama: Rb. | Naziv robe | JM | Količina | Neto kg | Zemlja | Tarifa | Vrsta robe."""
        from PySide6.QtGui import QColor

        cols = ["Rb.", "Naziv robe", "JM", "Količina", "Neto kg", "Zemlja", "Tarifni br.", "Vrsta robe"]
        table = QTableWidget(len(entries), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            "QTableWidget { background: #ffffff; alternate-background-color: #f0f4f8; color: #1e3820; }"
            "QTableWidget::item { color: #1e3820; }"
            "QTableWidget::item:selected { background-color: #d4e8d4; color: #1e3820; }"
        )
        table.verticalHeader().setVisible(False)

        # Širine kolona — posljednja kolona dobija više prostora
        col_widths = [35, 230, 50, 75, 80, 55, 90, 180]
        for i, w in enumerate(col_widths):
            table.setColumnWidth(i, w)

        vrsta_col = len(cols) - 1
        highlight_bg = QColor("#FFF9C4")   # blago žuta — ističe kolonu za web formu

        # Popuni redove
        for row_idx, (naim, match) in enumerate(entries):
            rb = str(naim.ordinal_no) if naim.ordinal_no else str(row_idx + 1)
            naziv = naim.goods_description or naim.goods_trade_name or "—"
            jm = naim.supplementary_unit_code or ""
            kolicina = (
                f"{naim.supplementary_unit_qty:,.3f}" if naim.supplementary_unit_qty else ""
            )
            neto = f"{naim.net_mass_kg:,.3f}" if naim.net_mass_kg else "—"
            zemlja = naim.origin_country_code or "—"
            tarifa = naim.tariff_code or "—"

            # Predloži vrstu robe za inspekcijski formular
            vrsta = self._service.suggest_vrsta_robe(naim.tariff_code or "", itype) or "—"

            values = [rb, naziv, jm, kolicina, neto, zemlja, tarifa, vrsta]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col_idx == 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                elif col_idx in (3, 4):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                # Istakni kolonu "Vrsta robe"
                if col_idx == vrsta_col:
                    item.setBackground(highlight_bg)
                table.setItem(row_idx, col_idx, item)

        table.resizeRowsToContents()

        # Visina tabele — max 300px
        row_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
        header_h = table.horizontalHeader().height()
        total_h = row_h + header_h + 4
        table.setFixedHeight(min(total_h, 300))
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        return table

    def _build_no_inspection_note(
        self, items: list[NaimenovanjeDraft]
    ) -> QLabel:
        """Napomena o stavkama koje ne zahtijevaju inspekciju."""
        rb_list = ", ".join(
            str(n.ordinal_no) if n.ordinal_no else "?" for n in items
        )
        lbl = QLabel(
            f"Stavke bez inspekcijskog zahtjeva (rb. {rb_list}): "
            f"Nisu pronađena odgovarajuća inspekcijska pravila."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color: #555; font-size: 11px; font-style: italic; "
            "background: #f8f9fa; border: 1px solid #e9ecef; "
            "border-radius: 4px; padding: 8px 12px;"
        )
        return lbl

    @staticmethod
    def _section_color(itype: str) -> str:
        """Boja zaglavlja sekcije po tipu inspekcije."""
        colors = {
            "sanitary":          "#d4edda",   # zelena
            "veterinary":        "#cce5ff",   # plava
            "phytosanitary":     "#c8f0c8",   # zelena (blija nijansa)
            "quality_control":   "#fff3cd",   # žuta
            "market_inspection": "#ffe0b2",   # narandzasta (naftni derivati)
            "medicines_agency":  "#f8d7da",   # crvena/roze
        }
        return colors.get(itype, "#e9ecef")
