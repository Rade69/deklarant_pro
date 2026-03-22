"""
Komponenta za prikaz sumarnih metrika u Naimenovanja tabu.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel


class SummaryPanel(QWidget):
    """Komponenta za prikaz sumarnih metrika."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Postavlja UI elemente."""
        self.setObjectName("summaryPanel")
        self.setFixedHeight(40)
        self.setStyleSheet("""
            #summaryPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 6, 15, 6)
        layout.setSpacing(20)
        
        # Metrike
        self.lbl_tarifa = QLabel("Tarifni broj (33): —")
        self.lbl_tarifa.setProperty("class", "summary-metric")
        layout.addWidget(self.lbl_tarifa)
        
        self.lbl_masa = QLabel("Bruto / Netto: — / — kg")
        self.lbl_masa.setProperty("class", "summary-metric")
        layout.addWidget(self.lbl_masa)
        
        self.lbl_vrijednost = QLabel("Vrijednost: — EUR")
        self.lbl_vrijednost.setProperty("class", "summary-metric")
        layout.addWidget(self.lbl_vrijednost)
        
        self.lbl_zemlja = QLabel("Zemlja: —")
        self.lbl_zemlja.setProperty("class", "summary-metric")
        layout.addWidget(self.lbl_zemlja)
        
        layout.addStretch()
        
        self.lbl_status = QLabel("✅ VALIDNO")
        self.lbl_status.setProperty("class", "summary-status-badge")
        layout.addWidget(self.lbl_status)
    
    def update_metrics(self, tariff: str, gross: float, net: float, value: float, currency: str, country: str):
        """
        Ažurira sve metrike.
        
        Args:
            tariff: Tarifni broj
            gross: Bruto masa
            net: Neto masa  
            value: Vrijednost
            currency: Valuta
            country: Zemlja porekla
        """
        self.lbl_tarifa.setText(f"Tarifni broj (33): {tariff or '—'}")
        
        bruto = f"{gross:.2f}" if gross else "0.00"
        netto = f"{net:.2f}" if net else "0.00"
        self.lbl_masa.setText(f"Bruto / Netto: {bruto} / {netto} kg")
        
        formatted_value = f"{value:,.0f}" if value else "0"
        self.lbl_vrijednost.setText(f"Vrijednost: {formatted_value} {currency or 'EUR'}")
        
        self.lbl_zemlja.setText(f"Zemlja: {country or '—'}")