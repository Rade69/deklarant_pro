"""
Enhanced Tariff Suggestion Dialog

Poboljšani dijalog za sugestije tarifnih brojeva sa:
1. Multiple suggestions (top 3)
2. Historijski podaci o dobavljaču
3. Kontekstualne informacije
4. Objašnjenja za svaki prijedlog
5. Warnings za potencijalne greške
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QGroupBox, QRadioButton,
    QButtonGroup, QTextEdit, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPalette


@dataclass
class SuggestionItem:
    """Jedan prijedlog tarifnog broja."""
    tariff_code: str
    description: str
    confidence: float  # 0.0-1.0
    source: str  # 'basic', 'historical', 'contextual', 'ai'
    explanation: str
    needs_review: bool = False
    is_recommended: bool = False


@dataclass
class DialogContext:
    """Kontekst za dijalog."""
    supplier_name: str = ""
    product_name: str = ""
    product_category: str = ""
    invoice_lines: List[Dict] = None
    has_historical_data: bool = False
    historical_usage_count: int = 0
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.invoice_lines is None:
            self.invoice_lines = []
        if self.warnings is None:
            self.warnings = []


class EnhancedTariffSuggestionDialog(QDialog):
    """
    Poboljšani dijalog za sugestije tarifnih brojeva.
    
    Prikazuje:
    1. Osnovne prijedloge (postojeći sistem)
    2. Agent sugestije (historija + kontekst)
    3. Warnings i objašnjenja
    4. Mogućnost odabira
    """
    
    # Signal koji se emituje kada korisnik odabere tarifni broj
    tariff_selected = Signal(str)
    
    def __init__(
        self,
        basic_suggestions: List[Dict[str, Any]],
        agent_suggestions: List[Dict[str, Any]],
        context: DialogContext,
        parent=None
    ):
        super().__init__(parent)
        
        self.basic_suggestions = basic_suggestions
        self.agent_suggestions = agent_suggestions
        self.context = context
        self.selected_tariff = ""
        
        self._init_ui()
        self._setup_signals()
        
        # Postavi veličinu prozora
        self.setMinimumSize(800, 600)
        self.setWindowTitle("🤖 Inteligentne sugestije za tarifni broj")
    
    def _init_ui(self):
        """Inicijalizacija UI komponenti."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. HEADER - Informacije o proizvodu i dobavljaču
        header_widget = self._create_header_widget()
        main_layout.addWidget(header_widget)
        
        # 2. SUGGESTIONS AREA - Scrollable area sa prijedlozima
        suggestions_area = self._create_suggestions_area()
        main_layout.addWidget(suggestions_area, 1)  # Stretch factor 1
        
        # 3. WARNINGS AREA - Ako postoje upozorenja
        if self.context.warnings:
            warnings_widget = self._create_warnings_widget()
            main_layout.addWidget(warnings_widget)
        
        # 4. FOOTER - Dugmad za akcije
        footer_widget = self._create_footer_widget()
        main_layout.addWidget(footer_widget)
    
    def _create_header_widget(self) -> QWidget:
        """Kreiraj header widget sa informacijama."""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(8)
        
        # Naslov
        title_label = QLabel("🤖 INTELIGENTNE SUGESTIJE ZA TARIFNI BROJ")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        # Informacije o proizvodu
        product_info = QLabel(f"<b>Proizvod:</b> {self.context.product_name}")
        product_info.setStyleSheet("font-size: 13px; color: #34495e;")
        header_layout.addWidget(product_info)
        
        # Informacije o dobavljaču
        if self.context.supplier_name:
            supplier_info = QLabel(f"<b>Dobavljač:</b> {self.context.supplier_name}")
            supplier_info.setStyleSheet("font-size: 13px; color: #34495e;")
            header_layout.addWidget(supplier_info)
        
        # Historijski podaci
        if self.context.has_historical_data and self.context.historical_usage_count > 0:
            history_info = QLabel(
                f"📊 <b>Historija:</b> {self.context.supplier_name} je ranije koristio "
                f"tarifne brojeve {self.context.historical_usage_count} puta"
            )
            history_info.setStyleSheet("font-size: 12px; color: #7f8c8d; font-style: italic;")
            header_layout.addWidget(history_info)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #bdc3c7;")
        header_layout.addWidget(separator)
        
        return header
    
    def _create_suggestions_area(self) -> QScrollArea:
        """Kreiraj scrollable area sa prijedlozima."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget za prijedloge
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)
        container_layout.setContentsMargins(5, 5, 5, 5)
        
        # Grupisanje prijedloga po izvoru
        all_suggestions = self._group_and_rank_suggestions()
        
        # Prikaži prijedloge po grupama
        for group_name, suggestions in all_suggestions.items():
            if suggestions:
                group_widget = self._create_suggestion_group(group_name, suggestions)
                container_layout.addWidget(group_widget)
        
        # Ako nema prijedloga
        if not any(len(s) for s in all_suggestions.values()):
            no_suggestions = QLabel("⚠️ Nema dostupnih prijedloga za ovaj proizvod.")
            no_suggestions.setStyleSheet("font-size: 13px; color: #e74c3c; padding: 20px;")
            no_suggestions.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(no_suggestions)
        
        # Spacer na kraju
        container_layout.addStretch()
        
        scroll_area.setWidget(container)
        return scroll_area
    
    def _group_and_rank_suggestions(self) -> Dict[str, List[SuggestionItem]]:
        """Grupiraj i rangiraj prijedloge po izvoru."""
        groups = {
            "recommended": [],
            "basic": [],
            "historical": [],
            "contextual": []
        }
        
        # Konvertuj basic suggestions
        for i, suggestion in enumerate(self.basic_suggestions):
            item = SuggestionItem(
                tariff_code=suggestion.get('tariff_code', ''),
                description=suggestion.get('description', ''),
                confidence=suggestion.get('similarity', 0.5),
                source='basic',
                explanation=suggestion.get('explanation', 'AI prijedlog'),
                needs_review=suggestion.get('needs_review', False),
                is_recommended=(i == 0 and suggestion.get('similarity', 0) >= 0.85)
            )
            
            if item.is_recommended:
                groups["recommended"].append(item)
            else:
                groups["basic"].append(item)
        
        # Konvertuj agent suggestions
        for suggestion in self.agent_suggestions:
            item = SuggestionItem(
                tariff_code=suggestion.get('tariff_code', ''),
                description=suggestion.get('description', ''),
                confidence=suggestion.get('confidence', 0.5),
                source=suggestion.get('source', 'agent'),
                explanation=suggestion.get('explanation', ''),
                needs_review=suggestion.get('needs_review', False)
            )
            
            if item.source == 'historical':
                groups["historical"].append(item)
            else:
                groups["contextual"].append(item)
        
        # Sortiraj svaku grupu po confidence (opadajuće)
        for group in groups.values():
            group.sort(key=lambda x: x.confidence, reverse=True)
        
        return groups
    
    def _create_suggestion_group(
        self,
        group_name: str,
        suggestions: List[SuggestionItem]
    ) -> QGroupBox:
        """Kreiraj group box sa prijedlozima."""
        group_box = QGroupBox()
        
        # Stilovi za različite grupe
        group_styles = {
            "recommended": {
                "title": "🎯 PREPORUČENI PRIJEDLOG",
                "color": "#27ae60",
                "bg_color": "#e8f6f3"
            },
            "basic": {
                "title": "🤖 AI PRIJEDLOZI",
                "color": "#3498db",
                "bg_color": "#ebf5fb"
            },
            "historical": {
                "title": "📊 HISTORIJSKI PODACI",
                "color": "#8e44ad",
                "bg_color": "#f4ecf7"
            },
            "contextual": {
                "title": "🔍 KONTEKSTUALNE INFORMACIJE",
                "color": "#d35400",
                "bg_color": "#fdebd0"
            }
        }
        
        style = group_styles.get(group_name, group_styles["basic"])
        
        # Postavi naslov grupe
        group_box.setTitle(style["title"])
        group_box.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {style['color']};
                border: 2px solid {style['color']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: {style['bg_color']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }}
        """)
        
        # Layout za prijedloge
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(10)
        
        # Dodaj prijedloge
        for i, suggestion in enumerate(suggestions[:3]):  # Maksimum 3 po grupi
            suggestion_widget = self._create_suggestion_widget(suggestion, i)
            group_layout.addWidget(suggestion_widget)
        
        return group_box
    
    def _create_suggestion_widget(
        self,
        suggestion: SuggestionItem,
        index: int
    ) -> QWidget:
        """Kreiraj widget za jedan prijedlog."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Radio button za odabir
        radio = QRadioButton()
        radio.setObjectName(f"radio_{suggestion.tariff_code}")
        radio.setChecked(suggestion.is_recommended)
        radio.toggled.connect(
            lambda checked, code=suggestion.tariff_code: self._on_tariff_selected(code, checked)
        )
        layout.addWidget(radio)
        
        # Informacije o prijedlogu
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # Tarifni broj i confidence
        tariff_label = QLabel(
            f"<b>{suggestion.tariff_code}</b> "
            f"<span style='color: #7f8c8d; font-size: 12px;'>(confidence: {suggestion.confidence:.0%})</span>"
        )
        tariff_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(tariff_label)
        
        # Opis
        if suggestion.description:
            desc_label = QLabel(suggestion.description)
            desc_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
            desc_label.setWordWrap(True)
            info_layout.addWidget(desc_label)
        
        # Objašnjenje
        if suggestion.explanation:
            expl_label = QLabel(f"💡 {suggestion.explanation}")
            expl_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-style: italic;")
            expl_label.setWordWrap(True)
            info_layout.addWidget(expl_label)
        
        # Warning ako treba review
        if suggestion.needs_review:
            warning_label = QLabel("⚠️ Preporučuje se ručna provjera")
            warning_label.setStyleSheet("font-size: 11px; color: #e74c3c;")
            info_layout.addWidget(warning_label)
        
        layout.addLayout(info_layout, 1)  # Stretch factor 1
        
        # Stilovi za widget
        bg_color = "#ffffff"
        if suggestion.is_recommended:
            bg_color = "#d5f4e6"
        elif suggestion.needs_review:
            bg_color = "#fdedec"
        
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 6px;
                border: 1px solid #dfe6e9;
            }}
        """)
        
        return widget
    
    def _create_warnings_widget(self) -> QGroupBox:
        """Kreiraj widget sa upozorenjima."""
        warning_box = QGroupBox("⚠️ UPОZORENJA")
        warning_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #e74c3c;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: #fdedec;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }
        """)
        
        warning_layout = QVBoxLayout(warning_box)
        
        for warning in self.context.warnings:
            warning_label = QLabel(f"• {warning}")
            warning_label.setStyleSheet("font-size: 12px; color: #c0392b;")
            warning_label.setWordWrap(True)
            warning_layout.addWidget(warning_label)
        
        return warning_box
    
    def _create_footer_widget(self) -> QWidget:
        """Kreiraj footer sa dugmadima."""
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        
        # Spacer lijevo
        footer_layout.addStretch()
        
        # Dugme "Poništi"
        cancel_btn = QPushButton("❌ Poništi")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)
        
        # Dugme "Pregledaj sve" (opciono)
        if len(self.basic_suggestions) > 3 or len(self.agent_suggestions) > 3:
            review_btn = QPushButton("🔄 Pregledaj sve prijedloge")
            review_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f39c12;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #e67e22;
                }
            """)
            review_btn.clicked.connect(self._show_all_suggestions)
            footer_layout.addWidget(review_btn)
        
        # Dugme "Prihvati"
        accept_btn = QPushButton("✅ Prihvati odabrani")
        accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        accept_btn.clicked.connect(self.accept)
        accept_btn.setEnabled(False)  # Disabled dok se ne odabere tarifa
        self.accept_btn = accept_btn
        footer_layout.addWidget(accept_btn)
        
        return footer
    
    def _setup_signals(self):
        """Postavi signale."""
        pass
    
    def _on_tariff_selected(self, tariff_code: str, checked: bool):
        """Handler za odabir tarifnog broja."""
        if checked:
            self.selected_tariff = tariff_code
            self.accept_btn.setEnabled(True)
    
    def _show_all_suggestions(self):
        """Prikaži sve prijedloge u novom dijalogu."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        
        dialog = QDialog(self)
        dialog.setWindowTitle("📋 Svi prijedlozi")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Text area sa svim prijedlozima
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        # Formatiraj sve prijedloge
        all_text = self._format_all_suggestions()
        text_edit.setHtml(all_text)
        
        layout.addWidget(text_edit)
        
        # Dugme za zatvaranje
        close_btn = QPushButton("Zatvori")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _format_all_suggestions(self) -> str:
        """Formatiraj sve prijedloge za HTML prikaz."""
        html = "<h3>Svi prijedlozi za tarifni broj</h3>"
        
        # Basic suggestions
        if self.basic_suggestions:
            html += "<h4>🤖 AI Prijedlozi:</h4><ul>"
            for suggestion in self.basic_suggestions:
                html += f"<li><b>{suggestion.get('tariff_code', 'N/A')}</b> "
                html += f"(confidence: {suggestion.get('similarity', 0):.0%})<br>"
                html += f"{suggestion.get('description', '')}<br>"
                html += f"<i>{suggestion.get('explanation', '')}</i></li>"
            html += "</ul>"
        
        # Agent suggestions
        if self.agent_suggestions:
            html += "<h4>🔍 Agent Prijedlozi:</h4><ul>"
            for suggestion in self.agent_suggestions:
                html += f"<li><b>{suggestion.get('tariff_code', 'N/A')}</b> "
                html += f"(confidence: {suggestion.get('confidence', 0):.0%})<br>"
                html += f"{suggestion.get('description', '')}<br>"
                html += f"<i>{suggestion.get('explanation', '')}</i></li>"
            html += "</ul>"
        
        return html
    
    def get_selected_tariff(self) -> str:
        """Vrati odabrani tarifni broj."""
        return self.selected_tariff
    
    @staticmethod
    def show_enhanced_dialog(
        basic_suggestions: List[Dict[str, Any]],
        agent_suggestions: List[Dict[str, Any]],
        context: DialogContext,
        parent=None
    ) -> Optional[str]:
        """
        Statička metoda za prikaz dijaloga i dobijanje rezultata.
        
        Args:
            basic_suggestions: Osnovni prijedlozi
            agent_suggestions: Agent prijedlozi
            context: Kontekst dijaloga
            parent: Parent widget
        
        Returns:
            Odabrani tarifni broj ili None ako je dijalog otkazan
        """
        dialog = EnhancedTariffSuggestionDialog(
            basic_suggestions,
            agent_suggestions,
            context,
            parent
        )
        
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_selected_tariff()
        
        return None


# Helper funkcije za kreiranje konteksta
def create_context_from_invoice(
    product_name: str,
    supplier_name: str = "",
    invoice_lines: List[Dict] = None
) -> DialogContext:
    """Kreiraj kontekst na osnovu fakture."""
    from services.agent.historical_learning_service_safe import HistoricalLearningServiceSafe
    from services.agent.supplier_profiling_service import SupplierProfilingService
    
    context = DialogContext(
        supplier_name=supplier_name,
        product_name=product_name,
        invoice_lines=invoice_lines or []
    )
    
    # Detektuj kategoriju proizvoda
    context.product_category = _detect_product_category(product_name)
    
    # Provjeri historijske podatke
    if supplier_name:
        historical_service = HistoricalLearningServiceSafe()
        profiling_service = SupplierProfilingService()
        
        # Provjeri da li supplier ima historijske podatke
        profile = profiling_service.get_complete_profile(supplier_name)
        if profile:
            context.has_historical_data = True
            context.historical_usage_count = profile.total_declarations
        
        # Dodaj warnings ako postoje
        _add_warnings_from_context(context, supplier_name, product_name)
    
    return context


def _detect_product_category(product_name: str) -> str:
    """Detektuj kategoriju proizvoda na osnovu naziva."""
    product_lower = product_name.lower()
    
    if any(word in product_lower for word in ['alat', 'šraf', 'čekić', 'ključ']):
        return "ručni alati"
    elif any(word in product_lower for word in ['elektron', 'baterij', 'kabl', 'priključ']):
        return "elektronika"
    elif any(word in product_lower for word in ['keram', 'ploč', 'cigl', 'cigla']):
        return "keramički proizvodi"
    elif any(word in product_lower for word in ['tekstil', 'pamuk', 'pamuk', 'tkanin']):
        return "tekstil"
    elif any(word in product_lower for word in ['hrana', 'piće', 'vino', 'brašno']):
        return "hrana i pića"
    elif any(word in product_lower for word in ['kemij', 'boj', 'lak', 'sredstvo']):
        return "hemikalije"
    
    return "ostalo"


def _add_warnings_from_context(
    context: DialogContext,
    supplier_name: str,
    product_name: str
):
    """Dodaj warnings na osnovu konteksta."""
    warnings = []
    
    # Provjeri da li je proizvod nov za ovog dobavljača
    from services.agent.supplier_profiling_service import SupplierProfilingService
    
    profiling_service = SupplierProfilingService()
    profile = profiling_service.get_complete_profile(supplier_name)
    
    if profile and profile.product_profiles:
        # Provjeri da li je sličan proizvod ranije uvožen
        product_keywords = set(_extract_keywords(product_name.lower()))
        has_similar = False
        
        for existing_product in profile.product_profiles.values():
            existing_keywords = set(_extract_keywords(existing_product.product_name.lower()))
            common_keywords = product_keywords & existing_keywords
            
            if len(common_keywords) >= 2:  # Ako ima barem 2 zajednička keyword-a
                has_similar = True
                break
        
        if not has_similar:
            warnings.append(f"Nov proizvod za {supplier_name}. Provjeri tarifni broj.")
    
    # Provjeri kategoriju
    if context.product_category == "elektronika" and "alat" in supplier_name.lower():
        warnings.append(f"Elektronika kod dobavljača alata. Provjeri da li je stvarno za alat.")
    
    context.warnings = warnings


def _extract_keywords(text: str) -> List[str]:
    """Ekstraktuj ključne riječi iz teksta."""
    import re
    
    if not text:
        return []
    
    # Ukloni specijalne karaktere
    cleaned = re.sub(r'[^a-zA-ZčćžšđČĆŽŠĐ\s]', ' ', text)
    
    # Podijeli na riječi
    words = cleaned.lower().split()
    
    # Ukloni stop riječi
    stop_words = {'i', 'ili', 'sa', 'bez', 'za', 'od', 'do', 'na', 'u', 'po', 'iz', 'kao'}
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return keywords


# Test funkcija
def test_enhanced_dialog():
    """Testiraj enhanced dijalog."""
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Test podaci
    basic_suggestions = [
        {
            'tariff_code': '82052000',
            'description': 'Šrafcigeri, ručni alati',
            'similarity': 0.92,
            'explanation': 'Fuzzy match sa postojećim mapiranjem',
            'needs_review': False
        },
        {
            'tariff_code': '82053000',
            'description': 'Ručni alati',
            'similarity': 0.78,
            'explanation': 'Sličan proizvod u historiji',
            'needs_review': True
        }
    ]
    
    agent_suggestions = [
        {
            'tariff_code': '82052000',
            'description': 'Šrafcigeri',
            'confidence': 0.95,
            'source': 'historical',
            'explanation': 'MASTER TOOLS ranije koristio ovaj tarifni broj 5 puta',
            'needs_review': False
        },
        {
            'tariff_code': '82054000',
            'description': 'Ključevi',
            'confidence': 0.65,
            'source': 'contextual',
            'explanation': 'Slično drugim alatima u fakturi',
            'needs_review': True
        }
    ]
    
    context = DialogContext(
        supplier_name='MASTER TOOLS',
        product_name='Šrafciger profesionalni',
        product_category='ručni alati',
        has_historical_data=True,
        historical_usage_count=15,
        warnings=['Nov proizvod za ovog dobavljača. Provjeri tarifni broj.']
    )
    
    result = EnhancedTariffSuggestionDialog.show_enhanced_dialog(
        basic_suggestions,
        agent_suggestions,
        context
    )
    
    if result:
        print(f"✅ Odabran tarifni broj: {result}")
    else:
        print("❌ Dijalog otkazan")
    
    sys.exit()


if __name__ == "__main__":
    test_enhanced_dialog()
