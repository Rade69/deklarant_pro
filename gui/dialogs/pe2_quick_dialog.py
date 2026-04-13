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


class PE2QuickDialog(QDialog):
    """
    Dijalog za unos PE2 podataka (izjava o poreklu na fakturi).
    
    Pravila:
    - Jedna šifra dokumenta po zemlji (PE2)
    - Broj izjave (npr. broj fakture) može biti isti za sve zemlje
    - Automatska povlastica na osnovu zemlje
    """
    
    def __init__(self, invoice_lines: List[InvoiceLine], parent=None, invoice_number: str = ""):
        super().__init__(parent)
        self.invoice_lines = invoice_lines
        self.country_inputs = {}
        self._prefill_invoice_number = invoice_number
        self.setup_ui()
        
    def setup_ui(self):
        """Postavi UI elemente dialoga."""
        self.setWindowTitle("📋 PE2 Obrazac (Izjava o poreklu)")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # HEADER - Objašnjenje
        header = QLabel("✅ Faktura SADRŽI izjavu o preferencijalnom poreklu.")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #155724; "
                           "background: #d4edda; padding: 10px; border-radius: 5px;")
        layout.addWidget(header)
        
        subheader = QLabel("Čekiraj zemlje koje imaju izjavu o porijeklu (PE2).\nBroj fakture je opcionalan — upiši ga ako ga imaš.")
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
        
        for country_code, items in sorted(countries.items()):
            country_name = self._get_country_name(country_code)
            group = self._create_country_group(country_code, country_name, items)
            self.scroll_layout.addWidget(group)
        
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
    
    def _group_by_country(self) -> Dict[str, List[InvoiceLine]]:
        """Grupiši stavke po zemlji porijekla."""
        countries = {}
        for item in self.invoice_lines:
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
        
        # Šifra (PE2 - read-only)
        code_label = QLabel("Šifra:")
        code_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(code_label)
        
        code_combo = QComboBox()
        code_combo.addItem("PE2", "PE2")
        code_combo.setMaximumWidth(80)
        code_combo.setEnabled(False)  # PE2 je fiksno za izjave
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

        if total > 0:
            # Dugme aktivno čim je bar jedna zemlja čekirana — broj fakture je opcionalan
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
                    'code': 'PE2',
                    'preference': data['preference'],  # EUP/CEFTAP/TRP (na osnovu zemlje)
                    'invoice_number': invoice_number,  # Broj fakture
                    'items': data['items'],  # SVE stavke ove zemlje
                }

        return result
    
    def _suggest_preference(self, country_code: str) -> str:
        """
        Predloži povlasticu (Rub.36) na osnovu zemlje.
        
        Poboljšana verzija koja koristi historijsko učenje ako je dostupno.
        
        Pravila:
        1. Prvo probaj historijsko učenje (ako znamo exportera)
        2. Fallback na hardcoded pravila
        """
        country_upper = country_code.upper()
        
        # Pokušaj da koristiš historijsko učenje ako znamo exportera
        try:
            # Proveri da li imamo exporter name (možda je pročitan iz fakture)
            exporter_name = ""
            if hasattr(self, 'exporter_name') and self.exporter_name:
                exporter_name = self.exporter_name
            elif self.invoice_lines and hasattr(self.invoice_lines[0], 'exporter'):
                # Pokušaj da ekstraktuješ exportera iz stavki
                exporter_name = self.invoice_lines[0].exporter
            
            if exporter_name:
                # Koristi sigurnu verziju historijskog učenja
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
            return 'EUP'
        elif country_upper in cefta_countries:
            return 'CEFTAP'
        elif country_upper == 'TR':
            return 'TRP'
        elif country_upper == 'IR':
            return 'IRP'
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
            for item in data['items']:
                # Povlastica (Rub.36) - na osnovu zemlje
                item.povlastica = data['preference']  # EUP/CEFTAP/TRP
                # Broj fakture (Rub.44) - čuvamo u eur1_number
                item.eur1_number = data['invoice_number']  # npr. 3940/2025
                item.has_origin_statement = True  # IMA izjavu
                updated_count += 1
        
        return updated_count
