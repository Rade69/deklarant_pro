import logging
logger = logging.getLogger(__name__)
# gui/dialogs/pe2_quick_dialog.py

"""
PE2 Quick Dialog

Dijalog za unos PE2 podataka (izjava o poreklu na fakturi).

Koristi se kad faktura SADRŽI izjavu o poreklu.
Korisnik štiklira koje zemlje imaju PE2 povlasticu.
"""

from typing import Dict, List
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QCheckBox, QLineEdit, QPushButton, QScrollArea,
    QWidget, QFrame, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.draft.draft import InvoiceLine
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class PE2QuickDialog(QDialog):
    """
    Dijalog za unos PE2 ili PE3 podataka (izjava o poreklu na fakturi).

    doc_code='PE2' — standardna izjava na fakturi (vrijednost ≤ 6.000 EUR)
    doc_code='PE3' — izjava ovlaštenog izvoznika (bez ograničenja vrijednosti)
    """

    def __init__(self, invoice_lines: List[InvoiceLine], parent=None,
                 invoice_number: str = "", doc_code: str = "PE2"):
        super().__init__(parent)
        self.invoice_lines = invoice_lines
        self.country_inputs = {}
        self._prefill_invoice_number = invoice_number
        self._doc_code = doc_code  # 'PE2' ili 'PE3'
        self.setup_ui()

    def setup_ui(self):
        """Postavi UI elemente dialoga."""
        is_pe3 = self._doc_code == 'PE3'
        self.setWindowTitle(
            "📋 PE3 Obrazac (Izjava ovlaštenog izvoznika)"
            if is_pe3 else
            "📋 PE2 Obrazac (Izjava o poreklu)"
        )
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # HEADER
        if is_pe3:
            header_txt = "✅ Faktura SADRŽI izjavu OVLAŠTENOG IZVOZNIKA (PE3)."
            sub_txt = ("Čekiraj zemlje koje imaju izjavu ovlaštenog izvoznika (PE3).\n"
                       "Broj ovlaštenja / fakture je opcionalan.")
        else:
            header_txt = "✅ Faktura SADRŽI izjavu o preferencijalnom poreklu."
            sub_txt = ("Čekiraj zemlje koje imaju izjavu o porijeklu (PE2).\n"
                       "Broj fakture je opcionalan — upiši ga ako ga imaš.")

        header = QLabel(header_txt)
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #155724; "
                             "background: #d4edda; padding: 10px; border-radius: 5px;")
        layout.addWidget(header)

        subheader = QLabel(sub_txt)
        subheader.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(subheader)
        
        # GLOBALNI BROJ FAKTURE/IZJAVE
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
        
        global_label = QLabel("📄 Broj fakture/izjave:")
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
            auto_label = QLabel("✅ automatski pročitan")
            auto_label.setStyleSheet("color: #28a745; font-size: 11px; font-style: italic;")
            global_layout.addWidget(auto_label)

        global_layout.addStretch()
        layout.addWidget(global_group)

        # INFO LABEL (mora PRIJE scroll area da bi signal ne pucao)
        self.info_label = QLabel("ℹ️ Čekiraj zemlju koja ima izjavu o porijeklu")
        self.info_label.setStyleSheet("font-weight: bold; color: #0c5460; "
                                     "background: #d1ecf1; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.info_label)

        # Poveži signal NAKON što je info_label kreiran
        self.global_invoice_number.textChanged.connect(self._on_global_invoice_changed)
        
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
            for country_code, items in sorted(countries.items()):
                country_name = self._get_country_name(country_code)
                group = self._create_country_group(country_code, country_name, items)
                self.scroll_layout.addWidget(group)
        else:
            # Nema zemlja_porijekla na stavkama — prikaži ručni unos
            self._manual_country_row = self._create_manual_country_input()
            self.scroll_layout.addWidget(self._manual_country_row)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # BUTTONS
        self.ok_button = QPushButton("✅ Primijeni")
        self.ok_button.clicked.connect(self._on_accept)
        self.ok_button.setEnabled(False)  # Disabled until valid input
        self.ok_button.setMinimumHeight(40)
        
        cancel_button = QPushButton("❌ Preskoči")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setMinimumHeight(40)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def _create_manual_country_input(self) -> QFrame:
        """Fallback kad stavke nemaju zemlja_porijekla — ručni unos šifre zemlje."""
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
        self._manual_country_edit.setPlaceholderText("Šifra zemlje (2 slova, npr. TR)")
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

    def _group_by_country(self) -> Dict[str, List[InvoiceLine]]:
        """Grupiši stavke po zemlji porijekla (isključuje stavke sa no_preference=True)."""
        countries = {}
        for item in self.invoice_lines:
            if getattr(item, 'no_preference', False):
                continue  # "bez pref. porekla" — preskoci, nema povlastice
            if item.zemlja_porijekla:
                country = item.zemlja_porijekla.upper()
                if country not in countries:
                    countries[country] = []
                countries[country].append(item)
        return countries
    
    def _get_country_name(self, country_code: str) -> str:
        """Dobavi naziv zemlje iz šifre."""
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
    
    def _create_country_group(self, country_code: str, country_name: str, 
                             items: List[InvoiceLine]) -> QFrame:
        """Kreiraj grupu (red) za jednu zemlju."""
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
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Checkbox
        checkbox = QCheckBox(f"{country_code} - {country_name}")
        checkbox.setStyleSheet("font-weight: bold; font-size: 13px;")
        checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(checkbox)
        
        # Broj stavki
        count_label = QLabel(f"({len(items)} stavki)")
        count_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(count_label)
        
        layout.addSpacing(20)
        
        # Šifra (PE2 ili PE3 - read-only)
        code_label = QLabel("Šifra:")
        code_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(code_label)

        code_combo = QComboBox()
        code_combo.addItem(self._doc_code, self._doc_code)
        code_combo.setMaximumWidth(80)
        code_combo.setEnabled(False)
        layout.addWidget(code_combo)
        
        layout.addSpacing(20)
        
        # Povlastica (read-only)
        preference = self._suggest_preference(country_code)
        pref_label = QLabel(f"→ {preference}")
        pref_label.setStyleSheet("color: #155724; font-weight: bold;")
        layout.addWidget(pref_label)
        
        layout.addStretch()
        
        # Sačuvaj reference
        self.country_inputs[country_code] = {
            'checkbox': checkbox,
            'code_combo': code_combo,
            'preference': preference,
            'items': items,
        }
        
        return frame
    
    def _on_checkbox_changed(self):
        """Ažuriraj UI kad se checkbox promeni."""
        # Ažuriraj info label i OK button
        self._update_info()
    
    def _on_global_invoice_changed(self, text: str):
        """Ažuriraj UI kad se promeni broj fakture."""
        self._update_info()


    def _on_accept(self):
        """Handle accept button click."""
        logger.info(f"✅ [_on_accept PE2] Dugme Primijeni kliknuto!")
        pe2_data = self.get_data()
        logger.info(f"✅ [_on_accept PE2] pe2_data={pe2_data}")
        self.accept()

    def _update_info(self):
        """Ažuriraj info label sa brojem stavki za ažuriranje."""
        total = 0
        countries_count = 0

        invoice_number = self.global_invoice_number.text().strip()

        for country, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                total += len(data['items'])
                countries_count += 1

        # Manualni unos (fallback kad nema zemlja_porijekla na stavkama)
        manual_ok = False
        if not self.country_inputs and hasattr(self, '_manual_country_edit'):
            code = self._manual_country_edit.text().strip().upper()
            if len(code) == 2 and code.isalpha():
                manual_ok = True
                total = len(self.invoice_lines)
                countries_count = 1

        if total > 0:
            inv_info = f" (Faktura: {invoice_number})" if invoice_number else ""
            self.info_label.setText(
                f"✅ {total} stavki iz {countries_count} zemlje će dobiti PE2{inv_info}"
            )
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #155724; "
                "background: #d4edda; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(True)
        else:
            self.info_label.setText("ℹ️ Čekiraj zemlju koja ima izjavu o porijeklu")
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #0c5460; "
                "background: #d1ecf1; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(False)
    
    def get_data(self) -> Dict[str, Dict]:
        """
        Vrati podatke za sve označene zemlje.

        Returns:
            {
                'DE': {
                    'code': 'PE2',
                    'preference': 'EUP',  # Stvarna šifra povlastice na osnovu zemlje
                    'invoice_number': '3940/2025',
                    'items': [list of all DE items],
                },
                ...
            }
        """
        result = {}
        invoice_number = self.global_invoice_number.text().strip()

        for country, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                result[country] = {
                    'code': self._doc_code,
                    'preference': data['preference'],
                    'invoice_number': invoice_number,
                    'items': data['items'],
                }

        # Fallback: manualni unos (kada stavke nemaju zemlja_porijekla)
        if not result and hasattr(self, '_manual_country_edit'):
            code = self._manual_country_edit.text().strip().upper()
            if len(code) == 2 and code.isalpha():
                for ln in self.invoice_lines:
                    ln.zemlja_porijekla = code
                result[code] = {
                    'code': self._doc_code,
                    'preference': self._suggest_preference(code),
                    'invoice_number': invoice_number,
                    'items': self.invoice_lines,
                }

        return result
    
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

    @staticmethod
    def apply_pe2_data(invoice_lines: List[InvoiceLine], pe2_data: Dict[str, Dict]) -> int:
        """
        Primeni PE2 podatke na stavke.
        
        PRAVILO: Kad se označi zemlja → automatski se postavlja:
        - Rub.36 (povlastica): EUP/CEFTAP/TRP (na osnovu zemlje)
        - Rub.44 (dokument): PE2 {broj_fakture}
        
        Args:
            invoice_lines: Lista svih stavki
            pe2_data: Podaci iz dialoga
            
        Returns:
            Broj ažuriranih stavki
        """
        updated_count = 0
        
        for country, data in pe2_data.items():
            doc_code = data.get('code', 'PE2')
            for item in data['items']:
                item.povlastica = data['preference']  # EUP/CEFTAP/TRP
                item.eur1_number = data['invoice_number']
                item.has_origin_statement = True
                item.is_authorized_exporter = (doc_code == 'PE3')

                # VAŽNO: ažuriraj i indikatore pouzdanosti (zelena ✅ oznaka u
                # tabeli) — bez ovoga stavka zadržava staru vrijednost iz
                # uvoza (npr. "PDF_OZNAKA", postavljenu PRIJE potvrde PE2),
                # pa korisnik vidi nedosljedne oznake za suštinski iste
                # slučajeve (potvrđena izjava o porijeklu = ista pouzdanost
                # kao kad je izjava prepoznata direktno iz PDF-a).
                item.country_source = "PDF_IZJAVA"
                item.country_confidence = "HIGH"
                item.country_conflict_details = ""

                updated_count += 1
        
        return updated_count
