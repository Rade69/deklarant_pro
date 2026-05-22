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
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QLineEdit, QPushButton, QScrollArea,
    QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.draft.draft import InvoiceLine
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


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
        self._prefill_invoice_number = invoice_number
        self.setup_ui()

    def setup_ui(self):
        """Postavi UI elemente dialoga."""
        self.setWindowTitle("EUR.1 obrazac po fakturi")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # HEADER - Objašnjenje
        header = QLabel("PDF nema izjavu o preferencijalnom porijeklu.")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #856404; "
                           "background: #fff3cd; padding: 10px; border-radius: 5px;")
        layout.addWidget(header)

        subheader = QLabel(
            "Označi samo fakture i zemlje za koje stvarno postoji EUR.1 obrazac.\n"
            "Stavke koje ne označiš ostaju bez povlastice."
        )
        subheader.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(subheader)

        # BROJ FAKTURE / IZJAVE
        global_group = QFrame()
        global_group.setStyleSheet("""
            QFrame {
                background: #e7f3ff;
                border: 1px solid #b8daff;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        global_layout = QHBoxLayout(global_group)

        global_label = QLabel("Broj fakture:")
        global_label.setStyleSheet("font-weight: bold;")
        global_layout.addWidget(global_label)

        self.global_invoice_number = QLineEdit()
        self.global_invoice_number.setPlaceholderText("npr. 3940/2025")
        self.global_invoice_number.setMaximumWidth(200)
        global_layout.addWidget(self.global_invoice_number)

        # Prefill ako je broj fakture pročitan iz PDF-a
        if self._prefill_invoice_number:
            self.global_invoice_number.blockSignals(True)
            self.global_invoice_number.setText(self._prefill_invoice_number)
            self.global_invoice_number.blockSignals(False)
            auto_label = QLabel("automatski pročitan")
            auto_label.setStyleSheet("color: #28a745; font-size: 11px; font-style: italic;")
            global_layout.addWidget(auto_label)

        global_layout.addStretch()
        layout.addWidget(global_group)

        # SCROLL AREA - Zemlje
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.NoFrame)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(5)

        # Grupiši stavke po zemlji
        countries = self._group_by_country()

        if countries:
            for key, items in sorted(countries.items()):
                group = self._create_country_group(key, items)
                self.scroll_layout.addWidget(group)
        else:
            # Nema zemlja_porijekla na stavkama - prikaži ručni unos (kao kod Blagić-Loren)
            self._manual_country_row = self._create_manual_country_input()
            self.scroll_layout.addWidget(self._manual_country_row)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # INFO LABEL - Broj stavki
        self.info_label = QLabel("Unesi EUR.1 broj za svaku označenu grupu")
        self.info_label.setStyleSheet("font-weight: bold; color: #0c5460; "
                                     "background: #d1ecf1; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.info_label)

        # BUTTONS
        self.ok_button = QPushButton("Primijeni označene")
        self.ok_button.clicked.connect(self._on_accept)
        self.ok_button.setEnabled(False)  # Disabled until valid input
        self.ok_button.setMinimumHeight(40)

        cancel_button = QPushButton("Nema EUR.1 / preskoči")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setMinimumHeight(40)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)


    def _group_by_country(self) -> Dict[str, List[InvoiceLine]]:
        """Grupiši stavke po fakturi + zemlji porijekla.
        
        Kada ima više faktura, svaka faktura treba da ima svoju grupu
        pa korisnik može da za svaku fakturu odabere zemlju i EUR.1 broj.
        
        Returns:
            Dict sa ključevima oblika 'INVOICE_NUM - COUNTRY' (npr. 'IF0520/26-01 - RS')
        """
        groups = {}
        for item in self.invoice_lines:
            if item.zemlja_porijekla:
                country = item.zemlja_porijekla.upper()
                invoice_num = item.invoice_number or 'BEZ_BROJA'
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

    def _create_country_group(self, key: str, items: List[InvoiceLine]) -> QFrame:
        """Kreiraj grupu (red) za jednu kombinaciju faktura + zemlja."""
        # Parse ključ da dobije invoice_number i country_code
        invoice_number = self._get_invoice_number(key)
        country_code = key.split(' - ')[-1].strip() if ' - ' in key else key
        country_name = self._get_country_name(key)
        
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 5px;
            }
            QFrame:hover {
                background: #e9ecef;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # Header sa invoice_number i zemljom
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        invoice_label = QLabel(f"Faktura: {invoice_number}")
        invoice_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        header_layout.addWidget(invoice_label)
        
        header_layout.addSpacing(10)
        
        country_label = QLabel(f"Zemlja: {country_code} - {country_name}")
        country_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #28a745;")
        header_layout.addWidget(country_label)
        
        layout.addLayout(header_layout)
        
        # ComboBox za izbor zemlje (ako korisnik želi da promeni zemlju)
        country_select_layout = QHBoxLayout()
        country_label = QLabel("Zemlja:")
        country_label.setStyleSheet("font-size: 11px; color: #555;")
        country_select_layout.addWidget(country_label)
        
        self._country_combo = self._create_country_combo(country_code)
        country_select_layout.addWidget(self._country_combo)
        country_select_layout.addStretch()
        layout.addLayout(country_select_layout)
        
        # Checkbox
        checkbox = QCheckBox("Ova faktura/zemlja ima EUR.1 obrazac")
        checkbox.setStyleSheet("font-size: 12px; margin-top: 5px;")
        checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(checkbox)
        
        # Broj stavki
        count_label = QLabel(f"({len(items)} stavki)")
        count_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(count_label)

        layout.addSpacing(10)
        
        # EUR.1 input
        eur1_label = QLabel("EUR.1 broj:")
        eur1_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(eur1_label)

        eur1_number = QLineEdit()
        eur1_number.setPlaceholderText("npr. 000456/2025")
        eur1_number.setMaximumWidth(200)
        eur1_number.textChanged.connect(lambda _text: self._update_info())
        layout.addWidget(eur1_number)

        layout.addSpacing(10)
        
        # Povlastica (read-only)
        preference = self._suggest_preference(country_code)
        pref_label = QLabel(f"→ Povlastica: {preference if preference else '(automatski)'}")
        pref_label.setStyleSheet("color: #155724; font-weight: bold; font-size: 12px;")
        layout.addWidget(pref_label)
        
        layout.addStretch()
        
        # Sačuvaj reference
        self.country_inputs[key] = {
            'checkbox': checkbox,
            'eur1_number': eur1_number,
            'preference': preference,
            'items': items,
            'invoice_number': invoice_number,
            'combo': self._country_combo,  # Ref na combobox za izbor zemlje
        }
        
        return frame

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
    
    def _on_checkbox_changed(self):
        """Ažuriraj dugme kada se checkbox promeni."""
        self._update_info()

    def _on_accept(self):
        """Handle accept button click."""
        import sys
        logger.info(f"✅ [_on_accept] Dugme Primijeni kliknuto!")
        eur1_data = self.get_data()
        logger.info(f"✅ [_on_accept] eur1_data={eur1_data}")
        self.accept()

    def _update_info(self):
        """Ažuriraj info label sa brojem stavki za ažuriranje."""
        ready_countries = []

        for country, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                eur1_number = data['eur1_number'].text().strip()
                if eur1_number:
                    ready_countries.append(country)
        
        # Proveri i manualni unos (kada nema zemlja_na_stavkama)
        manual_ok = False
        if not self.country_inputs and hasattr(self, '_manual_country_edit'):
            code = self._manual_country_edit.text().strip().upper()
            if len(code) == 2 and code.isalpha():
                manual_ok = True
                ready_countries = [code]  # Pretvori manualni unos u ready_countries

        if ready_countries:
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
        combo.setMaximumWidth(150)
        
        # Učitaj zemlje iz baze
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT sifra, naziv FROM catalogs.drzave WHERE sifra IS NOT NULL ORDER BY naziv")
                countries = cur.fetchall()
                
                # Dodaj sve zemlje
                for row in countries:
                    code = row['sifra']
                    name = row['naziv']
                    combo.addItem(f"{code} - {name}", code)
                
                # Podesi current country
                idx = combo.findData(current_country)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                
                # Event handler za promenu zemlje
                combo.currentIndexChanged.connect(self._on_country_changed)
                
        except Exception as e:
            print(f"Greška pri učitavanju zemalja: {e}")
            combo.addItem(f"{current_country} - {current_country}", current_country)
        
        return combo
    
    def _on_country_changed(self, index: int):
        """Ažuriraj preference kada se promeni zemlja u comboboxu."""
        combo = self.sender()
        if combo and hasattr(combo, 'currentData'):
            country_code = combo.currentData()
            if country_code:
                pref = self._suggest_preference(country_code)
                # Pronađi ovu kombinaciju u country_inputs i ažuriraj preference
                # Ovo je komplikovano jer treba da se zna koji combo pripada kojoj grupi
                # Za sada samo osveži UI
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
                    'invoice_number': self.global_invoice_number.text().strip(),
                    'preference': self._suggest_preference(code),
                    'items': self.invoice_lines,
                }

        return result
    
    def _get_selected_country(self, key: str) -> str:
        """Dobavi trenutno izabranu zemlju iz comboboxa za dati ključ."""
        data = self.country_inputs.get(key)
        if data and hasattr(self, '_country_combo') and data.get('combo'):
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
                if invoice_number:
                    # Sačuvaj broj fakture za referencu (novo i staro polje)
                    item.invoice_number = invoice_number
                    if hasattr(item, 'raw'):
                        item.raw['invoice_number'] = invoice_number
                updated_count += 1

        return updated_count
