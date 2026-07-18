import logging
logger = logging.getLogger(__name__)
# gui/dialogs/eur1_quick_dialog.py

"""
EUR.1 Quick Dialog

Dijalog za brz unos EUR.1 brojeva odmah nakon učitavanja fakture.

Pravilo: 1 zemlja = 1 EUR.1 broj
Sve stavke iste zemlje idu pod isti EUR.1 obrazac.
"""

from typing import Dict, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QLineEdit, QPushButton, QScrollArea,
    QWidget, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from core.draft.draft import InvoiceLine


class Eur1QuickDialog(QDialog):
    """
    Dijalog za unos EUR.1 brojeva po zemljama.

    Pravila:
    - Jedan EUR.1 broj po zemlji
    - Automatska povlastica na osnovu zemlje
    - Validacija: povlastica zahteva EUR.1 ili izjavu
    """

    def __init__(self, invoice_lines: List[InvoiceLine], parent=None, invoice_number: str = ""):
        super().__init__(parent)
        self.invoice_lines = invoice_lines
        self.invoice_number = invoice_number
        self.country_inputs = {}
        self._row_by_key = {}
        self._prefill_invoice_number = invoice_number
        # Per-item tracking: da li neke stavke imaju izjavu o porijeklu (npr. Medicopharm)
        self._any_has_statement = any(
            getattr(item, 'has_origin_statement', False)
            for item in invoice_lines
        )
        self.setup_ui()

    def setup_ui(self):
        """Postavi UI elemente dialoga."""
        self.setWindowTitle("EUR.1 obrazac po fakturi")
        self.setMinimumWidth(820)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # HEADER — razlikuj slučaj: bez izjave vs. izjava postoji ali vrijednost > 6.000 EUR
        if self._any_has_statement:
            header_txt = "Faktura sadrži izjavu o porijeklu, ali vrijednost prelazi 6.000 EUR."
            header_style = ("font-size: 15px; font-weight: bold; color: #0c3547; "
                            "background: #cce5f0; padding: 10px; border-radius: 5px;")
            sub_txt = ("Za primjenu povlastice potreban je EUR.1 obrazac.\n"
                       "Označi samo fakture i zemlje za koje stvarno postoji EUR.1 obrazac.\n"
                       "Stavke koje ne označiš ostaju bez povlastice.")
        else:
            header_txt = "PDF nema izjavu o preferencijalnom porijeklu."
            header_style = ("font-size: 15px; font-weight: bold; color: #856404; "
                            "background: #fff3cd; padding: 10px; border-radius: 5px;")
            sub_txt = ("Označi samo fakture i zemlje za koje stvarno postoji EUR.1 obrazac.\n"
                       "Stavke koje ne označiš ostaju bez povlastice.")

        header = QLabel(header_txt)
        header.setStyleSheet(header_style)
        layout.addWidget(header)

        subheader = QLabel(sub_txt)
        subheader.setStyleSheet("color: #666; font-size: 12px; padding: 2px;")
        layout.addWidget(subheader)

        # Info o parcijalnoj izjavi — kad neke stavke imaju izjavu, neke ne
        if self._any_has_statement:
            total = len(self.invoice_lines)
            covered_count = sum(
                1 for item in self.invoice_lines
                if getattr(item, 'has_origin_statement', False)
            )
            uncovered = sorted(
                item.line_no for item in self.invoice_lines
                if not getattr(item, 'has_origin_statement', False)
            )
            if uncovered:
                uncov_str = ", ".join(str(n) for n in uncovered)
                partial_label = QLabel(
                    f"ℹ️  Izjava na fakturi pokriva {covered_count}/{total} stavki. "
                    f"Stavke rb. {uncov_str} nisu pokrivene izjavom i neće dobiti povlasticu."
                )
                partial_label.setStyleSheet(
                    "font-size: 12px; color: #5a3e00; background: #fff8dc; "
                    "padding: 8px; border-radius: 5px; border: 1px solid #e8c84a;"
                )
                partial_label.setWordWrap(True)
                layout.addWidget(partial_label)

        countries = self._group_by_country()

        if countries:
            self.groups_table = self._create_groups_table(countries)
            layout.addWidget(self.groups_table)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameStyle(QFrame.NoFrame)
            scroll_content = QWidget()
            self.scroll_layout = QVBoxLayout(scroll_content)
            self.scroll_layout.setAlignment(Qt.AlignTop)
            self._manual_country_row = self._create_manual_country_input()
            self.scroll_layout.addWidget(self._manual_country_row)
            self.scroll_layout.addStretch()
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)

        # INFO LABEL - Broj stavki
        self.info_label = QLabel("Unesi EUR.1 broj za svaku označenu grupu")
        self.info_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #0c5460; "
                                     "background: #d1ecf1; padding: 9px; border-radius: 5px;")
        layout.addWidget(self.info_label)

        # BUTTONS
        self.ok_button = QPushButton("Primijeni označene")
        self.ok_button.clicked.connect(self._on_accept)
        self.ok_button.setEnabled(False)  # Disabled until valid input
        self.ok_button.setMinimumHeight(42)
        self.ok_button.setMinimumWidth(150)

        cancel_button = QPushButton("Nema EUR.1 / preskoči")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setMinimumHeight(42)
        cancel_button.setMinimumWidth(160)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self._update_info()
        self._auto_resize()


    def _auto_resize(self):
        """Automatski provjeri visinu na osnovu broja redova, ograniči na ekran."""
        from PySide6.QtGui import QGuiApplication
        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen:
            available_h = screen.availableGeometry().height() - 80
            if self.height() > available_h:
                self.resize(self.width(), available_h)

    def _group_by_country(self) -> Dict[str, List[InvoiceLine]]:
        """Grupiši stavke po fakturi + zemlji porijekla.

        Kada ima više faktura, svaka faktura treba da ima svoju grupu
        pa korisnik može da za svaku fakturu odabere zemlju i EUR.1 broj.

        Kad importer radi per-item has_origin_statement tracking (npr. Medicopharm —
        izjava pokriva samo određene rbr-ove), stavke koje NISU u izjavi se
        preskačaju, jer ne mogu dobiti EUR.1 povlasticu.

        Returns:
            Dict sa ključevima oblika 'INVOICE_NUM - COUNTRY' (npr. 'IF0520/26-01 - RS')
        """
        groups = {}
        for item in self.invoice_lines:
            if self._any_has_statement and not getattr(item, 'has_origin_statement', False):
                continue  # Per-item filter: stavka nije pokrivena izjavom — bez povlastice
            country = (item.zemlja_porijekla or '').strip().upper()
            if not country:
                continue
            invoice_num = (item.invoice_number or 'BEZ_BROJA').strip()
            key = f"{invoice_num} - {country}"
            if key not in groups:
                groups[key] = []
            groups[key].append(item)
        return groups

    def _get_country_name(self, key: str) -> str:
        """Dobavi naziv zemlje iz kljuca oblika 'INVOICE_NUM - COUNTRY'."""
        # Parse 'IF0520/26-01 - RS' -> 'RS'
        if ' - ' in key:
            country_code = key.split(' - ')[-1].strip()
        else:
            country_code = key
        
        # Try to load from database
        try:
            from database.db import get_db_connection

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT naziv FROM catalogs.drzave WHERE sifra = %s", (country_code,))
                    row = cur.fetchone()
                    if row:
                        return row['naziv']
        except Exception:
            pass

        # Fallback - return code as name
        return country_code
    
    def _get_invoice_number(self, key: str) -> str:
        """Dobavi broj fakture iz kljuca oblika 'INVOICE_NUM - COUNTRY'."""
        # Parse 'IF0520/26-01 - RS' -> 'IF0520/26-01'
        if ' - ' in key:
            return key.split(' - ')[0].strip()
        return key

    def _create_groups_table(self, countries: Dict[str, List[InvoiceLine]]) -> QTableWidget:
        headers = [
            "Broj fakture", "Zemlja porijekla", "Povlastica",
            "Ima EUR1", "EUR1 obrazac"
        ]
        table = QTableWidget(len(countries), len(headers), self)
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f0f4f8;
                gridline-color: #d7dee8;
                border: 1px solid #b8c7d8;
                border-radius: 4px;
                font-size: 14px;
                color: #27384a;
            }
            QTableWidget::item { color: #27384a; }
            QHeaderView::section {
                background: #eef3f8;
                color: #27384a;
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
                border: 0;
                border-right: 1px solid #d7dee8;
            }
            QComboBox, QLineEdit {
                min-height: 34px;
                font-size: 14px;
                padding-left: 8px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }
        """)

        for row, (key, items) in enumerate(sorted(countries.items())):
            self._populate_group_row(table, row, key, items)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        table.setColumnWidth(1, 230)
        table.setColumnWidth(4, 240)
        table.verticalHeader().setDefaultSectionSize(48)
        row_height = 48
        header_height = 46
        total_h = header_height + len(countries) * row_height

        # Ograniči visinu tabele na osnovu ekrana, da dugmići OK/Cancel
        # ostanu vidljivi i kad ima puno grupa (faktura x zemlja) — vidi
        # agent_reports/2026-06-13_eur1-dialog-velicina-i-zaglavlje.md
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        available_h = (screen.availableGeometry().height() - 80) if screen else 700
        max_table_h = max(header_height + row_height * 3, available_h - 300)
        table_h = min(total_h, max_table_h)
        table.setMinimumHeight(table_h)
        table.setMaximumHeight(table_h)
        return table

    def _populate_group_row(self, table: QTableWidget, row: int, key: str, items: List[InvoiceLine]) -> None:
        invoice_number = self._get_invoice_number(key)
        country_code = key.split(' - ')[-1].strip() if ' - ' in key else key
        country_name = self._get_country_name(key)
        preference = self._suggest_preference(country_code)

        table.setItem(row, 0, QTableWidgetItem(invoice_number))

        country_combo = self._create_country_combo(country_code)
        country_combo.setMinimumWidth(190)
        table.setCellWidget(row, 1, country_combo)

        pref_label = QLabel(preference if preference else "(bez povlastice)")
        pref_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #155724;")
        table.setCellWidget(row, 2, pref_label)

        checkbox = QCheckBox()
        checkbox.setToolTip("Označi samo ako za ovu fakturu i zemlju postoji EUR1 obrazac.")
        checkbox.stateChanged.connect(lambda _state, group_key=key: self._on_checkbox_changed(group_key))
        checkbox_holder = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_holder)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.addWidget(checkbox)
        table.setCellWidget(row, 3, checkbox_holder)

        eur1_number = QLineEdit()
        eur1_number.setPlaceholderText("npr. 000456/2025")
        eur1_number.setMinimumWidth(260)
        eur1_number.setEnabled(False)
        eur1_number.textChanged.connect(lambda _text: self._update_info())
        table.setCellWidget(row, 4, eur1_number)

        country_combo.currentIndexChanged.connect(
            lambda _idx, group_key=key: self._on_country_changed_for_group(group_key)
        )

        self.country_inputs[key] = {
            'checkbox': checkbox,
            'eur1_number': eur1_number,
            'preference': preference,
            'preference_label': pref_label,
            'items': items,
            'invoice_number': invoice_number,
            'combo': country_combo,
        }
        self._row_by_key[key] = row
        if any(getattr(item, "raw", {}).get("eur1_suggested") for item in items):
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            eur1_number.setEnabled(True)

    def _create_manual_country_input(self) -> QFrame:
        """Fallback kad stavke nemaju zemlja_porijekla - ručni unos šifre zemlje."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(frame)

        warn = QLabel("⚠️  Stavke nemaju upisanu zemlju porijekla.\nUnesi šifru zemlje ručno (npr. TR, DE, CN):")
        warn.setStyleSheet("color: #856404; font-weight: bold;")
        layout.addWidget(warn)

        row = QHBoxLayout()

        self._manual_country_edit = QLineEdit()
        self._manual_country_edit.setPlaceholderText("Šifra zemlje (2 slova, npr. RS)")
        self._manual_country_edit.setMaximumWidth(120)
        self._manual_country_edit.textChanged.connect(self._on_manual_country_changed)
        row.addWidget(self._manual_country_edit)

        pref_hint = QLabel("→ povlastica: ")
        pref_hint.setStyleSheet("color: #555;")
        row.addWidget(pref_hint)

        self._manual_pref_label = QLabel("")
        self._manual_pref_label.setStyleSheet("color: #155724; font-weight: bold;")
        row.addWidget(self._manual_pref_label)

        row.addStretch()
        layout.addLayout(row)

        return frame
    
    def _on_manual_country_changed(self, text: str):
        """Ažuriraj prikaz povlastice i OK dugme."""
        code = text.strip().upper()
        if hasattr(self, '_manual_pref_label'):
            pref = self._suggest_preference(code) if code else ""
            self._manual_pref_label.setText(pref or ("(nepoznata zemlja)" if code else ""))
        self._update_info()
    
    def _on_checkbox_changed(self, key: str = ""):
        """Ažuriraj dugme kada se checkbox promeni."""
        if key and key in self.country_inputs:
            data = self.country_inputs[key]
            checked = data['checkbox'].isChecked()
            data['eur1_number'].setEnabled(checked)
            if not checked:
                data['eur1_number'].clear()
        self._update_info()

    def _on_accept(self):
        """Handle accept button click."""
        logger.info(f"✅ [_on_accept] Dugme Primijeni kliknuto!")
        eur1_data = self.get_data()
        logger.info(f"✅ [_on_accept] eur1_data={eur1_data}")
        self.accept()

    def _update_info(self):
        """Ažuriraj info label sa brojem stavki za ažuriranje."""
        ready_countries = []

        checked_missing = 0
        for country, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                eur1_number = data['eur1_number'].text().strip()
                if eur1_number:
                    ready_countries.append(country)
                else:
                    checked_missing += 1
        
        # Proveri i manualni unos (kada nema zemlja_na_stavkama)
        manual_ok = False
        if not self.country_inputs and hasattr(self, '_manual_country_edit'):
            code = self._manual_country_edit.text().strip().upper()
            if len(code) == 2 and code.isalpha():
                manual_ok = True
                ready_countries = [code]  # Pretvori manualni unos u ready_countries

        if ready_countries and not checked_missing:
            if manual_ok:
                total_items = len(self.invoice_lines)
                self.info_label.setText(
                    f"✅ {total_items} stavki iz ručno unešene zemlje će biti ažurirano"
                )
            else:
                total_items = sum(
                    len(self.country_inputs[c]['items']) for c in ready_countries
                )
                self.info_label.setText(
                    f"✅ {total_items} stavki iz {len(ready_countries)} zemlje će biti ažurirano"
                )
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #155724; "
                "background: #d4edda; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(True)
        elif checked_missing:
            self.info_label.setText(f"{checked_missing} označena grupa nema unesen EUR.1 broj")
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #856404; "
                "background: #fff3cd; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(False)
        else:
            self.info_label.setText("Unesi EUR.1 broj za svaku označenu grupu")
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #0c5460; "
                "background: #d1ecf1; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(False)
    
    def _create_country_combo(self, current_country: str):
        """Kreiraj ComboBox za izbor zemlje sa opcijama iz baze."""
        from PySide6.QtWidgets import QComboBox
        
        combo = QComboBox()
        combo.setMaximumWidth(220)
        
        # Učitaj zemlje iz cache-a (ne blokira GUI pri nedostupnom DB)
        from services.countries_cache import get_countries
        countries = get_countries()
        for code, name in countries:
            combo.addItem(f"{code} - {name}", code)

        idx = combo.findData(current_country)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif current_country:
            combo.insertItem(0, f"{current_country} - (nepoznata)", current_country)
            combo.setCurrentIndex(0)

        return combo
    
    def _on_country_changed_for_group(self, key: str):
        data = self.country_inputs.get(key)
        if not data:
            return
        country_code = self._get_selected_country(key)
        pref = self._suggest_preference(country_code)
        data['preference'] = pref
        label = data.get('preference_label')
        if label:
            label.setText(pref if pref else "(automatski)")
        self._update_info()

    def _suggest_preference(self, country_code: str) -> str:
        """
        Predloži povlasticu (Rub.36) na osnovu zemlje.

        Poboljšana verzija koja koristi istorijsko učenje ako je dostupno.

        Pravila:
        1. Prvo probaj istorijsko učenje (ako znamo exportera)
        2. Fallback na hardcoded pravila
        """
        country_upper = country_code.upper()

        # Pokušaj da koristiš istorijsko učenje ako znamo exportera
        try:
            # Proveri da li imamo exporter name (možda je pročitan iz fakture)
            exporter_name = ""
            if hasattr(self, 'exporter_name') and self.exporter_name:
                exporter_name = self.exporter_name
            elif self.invoice_lines and hasattr(self.invoice_lines[0], 'exporter'):
                # Pokušaj da ekstraktuješ exportera iz stavki
                exporter_name = self.invoice_lines[0].exporter

            if exporter_name:
                # Koristi sigurnu verziju istorijskog učenja
                from services.agent.historical_learning_service_safe import enhance_preference_logic
                historical_pref = enhance_preference_logic(country_upper, exporter_name)

                if historical_pref:
                    return historical_pref
        except Exception:
            # Silent fallback - nastavi sa hardcoded pravilima
            pass

        # FALLBACK: Hardcoded pravila (originalna logika)
        # EU zemlje
        eu_countries = {
            'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
            'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
        }

        # CEFTA zemlje
        cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}

        if country_upper in eu_countries:
            return 'EUPR'
        elif country_upper in cefta_countries:
            return 'CEFTAR'
        elif country_upper == 'TR':
            return 'TRPR'
        elif country_upper == 'IR':
            return 'IRP'
        elif country_upper in {'CH', 'LI'}:
            return 'EFTA1R'
        elif country_upper == 'IS':
            return 'EFTA2R'
        elif country_upper == 'NO':
            return 'EFTA3R'
        else:
            return ''

    def get_data(self) -> Dict[str, Dict]:
        """
        Vrati podatke za sve označene zemlje.

        Returns:
            {
                'IF0520/26-01 - RS': {
                    'eur1_number': '000456/2025',
                    'invoice_number': 'IF0520/26-01',
                    'preference': 'CEFTAR',
                    'items': [list of items],
                },
                'IF0520/26-02 - RS': {
                    ...
                },
                ...
            }
        """
        result = {}

        for key, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                eur1_number = data['eur1_number'].text().strip()

                if eur1_number:  # Samo ako je unesen broj
                    # Koristi invoice_number iz country_inputs
                    inv_num = data.get('invoice_number', '')
                    # Dobavi trenutno izabranu zemlju iz comboboxa
                    selected_country = self._get_selected_country(key)
                    # Odredi preference za izabranu zemlju
                    pref = self._suggest_preference(selected_country)
                    result[key] = {
                        'eur1_number': eur1_number,
                        'invoice_number': inv_num,
                        'preference': pref,
                        'country': selected_country,  # Dodato za reference
                        'items': data['items'],  # SVE stavke ove zemlje
                    }

        # Fallback: manualni unos (kada stavke nemaju zemlja_porijekla)
        if not result and hasattr(self, '_manual_country_edit'):
            code = self._manual_country_edit.text().strip().upper()
            if len(code) == 2 and code.isalpha():
                # Setuj zemlju na svim stavkama
                for ln in self.invoice_lines:
                    ln.zemlja_porijekla = code
                result[code] = {
                    'eur1_number': '',  # Prazan EUR.1 broj - korisnik može da unese kasnije
                    'invoice_number': self.invoice_number,
                    'preference': self._suggest_preference(code),
                    'items': self.invoice_lines,
                }

        return result
    
    def _get_selected_country(self, key: str) -> str:
        """Dobavi trenutno izabranu zemlju iz comboboxa za dati ključ."""
        data = self.country_inputs.get(key)
        if data and data.get('combo'):
            combo = data['combo']
            if hasattr(combo, 'currentData'):
                return combo.currentData() or key.split(' - ')[-1].strip()
        # Fallback na originalnu zemlju iz ključa
        return key.split(' - ')[-1].strip() if ' - ' in key else key

    @staticmethod
    def apply_eur1_data(invoice_lines: List[InvoiceLine], eur1_data: Dict[str, Dict]) -> int:
        """
        Primeni EUR.1 podatke na stavke.

        PRAVILO: Kad se unese EUR.1 broj → automatski se postavlja:
        - Rub.36 (povlastica): EUP/CEFTAP/TRP (na osnovu zemlje)
        - Rub.44 (dokument): PE1 {EUR.1_broj}

        Args:
            invoice_lines: Lista svih stavki
            eur1_data: Podaci iz dialoga

        Returns:
            Broj ažuriranih stavki
        """
        updated_count = 0

        for country, data in eur1_data.items():
            invoice_number = data.get('invoice_number', '')
            for item in data['items']:
                item.eur1_number = data['eur1_number']
                item.povlastica = data['preference']  # EUP/CEFTAP/TRP (na osnovu zemlje)
                item.has_origin_statement = False  # Nema izjavu, ima EUR.1

                # VAŽNO: ažuriraj indikatore pouzdanosti porijekla — bez ovoga
                # stavka zadržava staru vrijednost iz uvoza (npr. "PDF_OZNAKA",
                # postavljenu PRIJE potvrde EUR.1), pa korisnik vidi nedosljedne
                # oznake za suštinski iste slučajeve (potvrđeno preko zvaničnog
                # EUR.1 sertifikata = treba ista visoka pouzdanost kao kad je
                # izjava prepoznata direktno iz PDF-a). Izvor namjerno NIJE
                # "PDF_IZJAVA" jer ovdje nema izjave na fakturi, već zaseban
                # zvanični dokument (EUR.1).
                item.country_source = "EUR1_POTVRDA"
                item.country_confidence = "HIGH"
                item.country_conflict_details = ""

                if invoice_number:
                    # Sačuvaj broj fakture za referencu (novo i staro polje)
                    item.invoice_number = invoice_number
                    if hasattr(item, 'raw'):
                        item.raw['invoice_number'] = invoice_number
                updated_count += 1

        return updated_count
