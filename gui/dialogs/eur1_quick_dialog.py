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
        self.setWindowTitle("📋 EUR.1 Obrazac")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # HEADER - Objašnjenje
        header = QLabel("⚠️ PDF nema izjavu o preferencijalnom poreklu.")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #856404; "
                           "background: #fff3cd; padding: 10px; border-radius: 5px;")
        layout.addWidget(header)
        
        subheader = QLabel("Unesi EUR.1 broj za svaku zemlju koja ima obrazac.\nSve stavke iste zemlje idu pod isti EUR.1.")
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

        global_label = QLabel("📄 Broj fakture:")
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

        # INFO LABEL - Broj stavki
        self.info_label = QLabel("ℹ️ Unesi EUR.1 broj i klikni Primijeni")
        self.info_label.setStyleSheet("font-weight: bold; color: #0c5460; "
                                     "background: #d1ecf1; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.info_label)

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
        
        # EUR.1 input
        eur1_label = QLabel("EUR.1:")
        eur1_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(eur1_label)
        
        eur1_number = QLineEdit()
        eur1_number.setPlaceholderText("npr. 000456/2025")
        eur1_number.setMaximumWidth(150)
        eur1_number.textChanged.connect(lambda _text: self._update_info())
        layout.addWidget(eur1_number)
        
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
            'eur1_number': eur1_number,
            'preference': preference,
            'items': items,
        }
        
        return frame
    
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

        if ready_countries:
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
            self.info_label.setText("ℹ️ Unesi EUR.1 broj i klikni Primijeni")
            self.info_label.setStyleSheet(
                "font-weight: bold; color: #0c5460; "
                "background: #d1ecf1; padding: 10px; border-radius: 5px;"
            )
            self.ok_button.setEnabled(False)
    
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
            return 'EUP'
        elif country_upper in cefta_countries:
            return 'CEFTAP'
        elif country_upper == 'TR':
            return 'TRP'
        elif country_upper == 'IR':
            return 'IRP'
        elif country_upper in {'CH', 'NO', 'IS', 'LI'}:
            return 'EFTA1'
        else:
            return ''

    def get_data(self) -> Dict[str, Dict]:
        """
        Vrati podatke za sve označene zemlje.

        Returns:
            {
                'RS': {
                    'eur1_number': '000456/2025',
                    'invoice_number': '3940/2025',  # Broj fakture
                    'preference': 'CEFTAP',
                    'items': [list of all RS items],
                },
                ...
            }
        """
        result = {}
        invoice_number = self.global_invoice_number.text().strip()

        for country, data in self.country_inputs.items():
            if data['checkbox'].isChecked():
                eur1_number = data['eur1_number'].text().strip()

                if eur1_number:  # Samo ako je unesen broj
                    result[country] = {
                        'eur1_number': eur1_number,
                        'invoice_number': invoice_number,
                        'preference': data['preference'],
                        'items': data['items'],  # SVE stavke ove zemlje
                    }

        return result
    
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
