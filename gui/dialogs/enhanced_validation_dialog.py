"""
Enhanced Validation Dialog

Poboljšani dijalog za prikaz rezultata agent validacije.
Prikazuje kompletnu analizu deklaracije sa:
1. Zaglavlje validacija
2. Naimenovanja analiza
3. Historijski kontekst
4. Pravne provjere
5. Kontekstualne informacije
6. Preporuke za popravke
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QScrollArea, QFrame, QGroupBox,
    QTextEdit, QSizePolicy, QSpacerItem, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QIcon, QBrush

from services.agent.agent_validation_service import (
    ValidationReport,
    ValidationItem,
    ValidationSeverity,
    ValidationCategory
)


@dataclass
class DialogConfig:
    """Konfiguracija dijaloga."""
    show_details: bool = True
    show_recommendations: bool = True
    allow_auto_fix: bool = True
    show_export_button: bool = False


class EnhancedValidationDialog(QDialog):
    """
    Enhanced dijalog za prikaz rezultata agent validacije.
    
    Prikazuje kompletnu analizu deklaracije sa tabovima za različite kategorije.
    """
    
    # Signali
    auto_fix_requested = Signal(list)  # Lista ValidationItem za popravku
    export_requested = Signal()  # Zahtjev za export
    
    def __init__(
        self,
        report: ValidationReport,
        config: DialogConfig = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.report = report
        self.config = config or DialogConfig()
        
        self._init_ui()
        self._setup_signals()
        
        # Postavi veličinu prozora
        self.setMinimumSize(900, 700)
        self.setWindowTitle("🤖 Agent Validacija - Kompletna Analiza")
        
        # Centriraj prozor
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
    
    def _init_ui(self):
        """Inicijalizacija UI komponenti."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. HEADER - Sažetak validacije
        header_widget = self._create_header_widget()
        main_layout.addWidget(header_widget)
        
        # 2. TAB WIDGET - Detaljna analiza po kategorijama
        if self.config.show_details:
            tab_widget = self._create_tab_widget()
            main_layout.addWidget(tab_widget, 1)  # Stretch factor 1
        
        # 3. RECOMMENDATIONS - Preporuke za popravke
        if self.config.show_recommendations and self.report.recommendations:
            recommendations_widget = self._create_recommendations_widget()
            main_layout.addWidget(recommendations_widget)
        
        # 4. FOOTER - Dugmad za akcije
        footer_widget = self._create_footer_widget()
        main_layout.addWidget(footer_widget)
    
    def _create_header_widget(self) -> QWidget:
        """Kreiraj header widget sa sažetkom validacije."""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(8)
        
        # Naslov
        title_label = QLabel("🤖 AGENT VALIDACIJA - KOMPLETNA ANALIZA")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        # Status validacije
        status_text = "✅ VALIDNO - MOŽETE NASTAVITI SA EXPORTOM" if self.report.valid \
                     else "❌ NEVALIDNO - POPRAVITE GREŠKE PRIJE EXPORTA"
        
        status_label = QLabel(status_text)
        status_font = QFont()
        status_font.setPointSize(13)
        status_font.setBold(True)
        status_label.setFont(status_font)
        status_label.setStyleSheet(
            f"color: {'#27ae60' if self.report.valid else '#e74c3c'};"
        )
        status_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(status_label)
        
        # Statistika
        stats_text = (
            f"📊 <b>Statistika:</b> "
            f"<span style='color: #e74c3c;'>{self.report.error_count} grešaka</span> • "
            f"<span style='color: #f39c12;'>{self.report.warning_count} upozorenja</span> • "
            f"<span style='color: #3498db;'>{self.report.info_count} informacija</span> • "
            f"<span style='color: #9b59b6;'>{self.report.suggestion_count} preporuka</span>"
        )
        
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("font-size: 13px; color: #34495e;")
        stats_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(stats_label)
        
        # Sažetak
        if self.report.summary:
            summary_label = QLabel(f"📝 <b>Sažetak:</b> {self.report.summary}")
            summary_label.setStyleSheet("font-size: 12px; color: #7f8c8d; font-style: italic;")
            summary_label.setWordWrap(True)
            header_layout.addWidget(summary_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #bdc3c7; margin: 10px 0;")
        header_layout.addWidget(separator)
        
        return header
    
    def _create_tab_widget(self) -> QTabWidget:
        """Kreiraj tab widget sa kategorijama validacije."""
        tab_widget = QTabWidget()
        tab_widget.setTabPosition(QTabWidget.West)
        
        # Stilovi za tabove
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #3498db;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #d6dbdf;
            }
        """)
        
        # Tab 1: Zaglavlje
        if self.report.zaglavlje_items:
            zaglavlje_tab = self._create_validation_tab(
                self.report.zaglavlje_items,
                "📋 Zaglavlje",
                "#3498db"
            )
            tab_widget.addTab(zaglavlje_tab, "📋 Zaglavlje")
        
        # Tab 2: Naimenovanja
        if self.report.naimenovanja_items:
            naimenovanja_tab = self._create_validation_tab(
                self.report.naimenovanja_items,
                "📦 Naimenovanja",
                "#2ecc71"
            )
            tab_widget.addTab(naimenovanja_tab, "📦 Naimenovanja")
        
        # Tab 3: Historijska analiza
        if self.report.historical_items:
            historical_tab = self._create_validation_tab(
                self.report.historical_items,
                "📊 Historijska Analiza",
                "#9b59b6"
            )
            tab_widget.addTab(historical_tab, "📊 Historija")
        
        # Tab 4: Pravne provjere
        if self.report.legal_items:
            legal_tab = self._create_validation_tab(
                self.report.legal_items,
                "⚖️ Pravne Provjere",
                "#e74c3c"
            )
            tab_widget.addTab(legal_tab, "⚖️ Pravno")
        
        # Tab 5: Kontekstualne provjere
        if self.report.contextual_items:
            contextual_tab = self._create_validation_tab(
                self.report.contextual_items,
                "🔍 Kontekstualne Provjere",
                "#f39c12"
            )
            tab_widget.addTab(contextual_tab, "🔍 Kontekst")
        
        return tab_widget
    
    def _create_validation_tab(
        self,
        items: List[ValidationItem],
        title: str,
        color: str
    ) -> QWidget:
        """Kreiraj tab sa listom validacijskih stavki."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Naslov taba
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {color};")
        layout.addWidget(title_label)
        
        # Scroll area za stavke
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(8)
        
        # Grupiši stavke po severity
        severity_groups = {
            ValidationSeverity.ERROR: [],
            ValidationSeverity.WARNING: [],
            ValidationSeverity.INFO: [],
            ValidationSeverity.SUGGESTION: []
        }
        
        for item in items:
            severity_groups[item.severity].append(item)
        
        # Prikaži po grupama
        for severity, group_items in severity_groups.items():
            if group_items:
                group_widget = self._create_severity_group(severity, group_items, color)
                container_layout.addWidget(group_widget)
        
        # Spacer na kraju
        container_layout.addStretch()
        
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)
        
        return tab
    
    def _create_severity_group(
        self,
        severity: ValidationSeverity,
        items: List[ValidationItem],
        color: str
    ) -> QGroupBox:
        """Kreiraj group box za grupu stavki istog severity."""
        # Mapiranje severity na ikone i boje
        severity_config = {
            ValidationSeverity.ERROR: {
                "icon": "❌",
                "title": "GREŠKE",
                "bg_color": "#fdedec",
                "border_color": "#e74c3c"
            },
            ValidationSeverity.WARNING: {
                "icon": "⚠️",
                "title": "UPOZORENJA",
                "bg_color": "#fef9e7",
                "border_color": "#f39c12"
            },
            ValidationSeverity.INFO: {
                "icon": "ℹ️",
                "title": "INFORMACIJE",
                "bg_color": "#ebf5fb",
                "border_color": "#3498db"
            },
            ValidationSeverity.SUGGESTION: {
                "icon": "💡",
                "title": "PREPORUKE",
                "bg_color": "#f4ecf7",
                "border_color": "#9b59b6"
            }
        }
        
        config = severity_config[severity]
        
        group_box = QGroupBox(f"{config['icon']} {config['title']} ({len(items)})")
        group_box.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {config['border_color']};
                border: 2px solid {config['border_color']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: {config['bg_color']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }}
        """)
        
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(8)
        
        # Dodaj stavke
        for item in items[:10]:  # Maksimum 10 stavki po grupi
            item_widget = self._create_validation_item_widget(item)
            group_layout.addWidget(item_widget)
        
        # Ako ima više od 10 stavki, dodaj label
        if len(items) > 10:
            more_label = QLabel(f"... i još {len(items) - 10} stavki")
            more_label.setStyleSheet("font-size: 11px; color: #7f8c8d; font-style: italic;")
            more_label.setAlignment(Qt.AlignCenter)
            group_layout.addWidget(more_label)
        
        return group_box
    
    def _create_validation_item_widget(self, item: ValidationItem) -> QWidget:
        """Kreiraj widget za jednu validacijsku stavku."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Ikona severity
        icon_label = QLabel(self._get_severity_icon(item.severity))
        icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(icon_label)
        
        # Informacije o stavki
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Rule i field
        rule_field = QLabel(f"<b>{item.rule}</b> - {item.field}")
        rule_field.setStyleSheet("font-size: 12px; color: #2c3e50;")
        info_layout.addWidget(rule_field)
        
        # Message
        message_label = QLabel(item.message)
        message_label.setStyleSheet("font-size: 11px; color: #34495e;")
        message_label.setWordWrap(True)
        info_layout.addWidget(message_label)
        
        # Explanation (ako postoji)
        if item.explanation:
            expl_label = QLabel(f"💡 {item.explanation}")
            expl_label.setStyleSheet("font-size: 10px; color: #7f8c8d; font-style: italic;")
            expl_label.setWordWrap(True)
            info_layout.addWidget(expl_label)
        
        layout.addLayout(info_layout, 1)  # Stretch factor 1
        
        # Checkbox za auto-fix (ako je fixable)
        if item.fixable and self.config.allow_auto_fix:
            checkbox = QCheckBox("Popravi")
            checkbox.setProperty("validation_item", item)
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    color: #27ae60;
                    font-weight: bold;
                }
            """)
            layout.addWidget(checkbox)
        
        # Stilovi za widget
        bg_color = "#ffffff"
        if item.severity == ValidationSeverity.ERROR:
            bg_color = "#fdedec"
        elif item.severity == ValidationSeverity.WARNING:
            bg_color = "#fef9e7"
        
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 6px;
                border: 1px solid #dfe6e9;
            }}
        """)
        
        return widget
    
    def _create_recommendations_widget(self) -> QGroupBox:
        """Kreiraj widget sa preporukama za popravke."""
        recommendations_box = QGroupBox("🎯 PREPORUKE ZA POPRAVKE")
        recommendations_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #27ae60;
                border: 2px solid #27ae60;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: #e8f6f3;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }
        """)
        
        recommendations_layout = QVBoxLayout(recommendations_box)
        recommendations_layout.setSpacing(8)
        
        # Dodaj preporuke
        for i, recommendation in enumerate(self.report.recommendations, 1):
            rec_label = QLabel(f"{i}. {recommendation}")
            rec_label.setStyleSheet("""
                font-size: 12px;
                color: #2c3e50;
                padding: 5px;
                border-left: 3px solid #27ae60;
                background-color: #ffffff;
                border-radius: 4px;
            """)
            rec_label.setWordWrap(True)
            recommendations_layout.addWidget(rec_label)
        
        return recommendations_box
    
    def _create_footer_widget(self) -> QWidget:
        """Kreiraj footer sa dugmadima za akcije."""
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        
        # Lijevo: Checkbox za prikaz detalja
        if self.config.show_details:
            self.details_checkbox = QCheckBox("Prikaži detaljnu analizu")
            self.details_checkbox.setChecked(True)
            self.details_checkbox.stateChanged.connect(self._on_details_toggled)
            footer_layout.addWidget(self.details_checkbox)
        
        # Spacer
        footer_layout.addStretch()
        
        # Desno: Dugmad za akcije
        
        # Dugme "Zatvori"
        close_btn = QPushButton("❌ Zatvori")
        close_btn.setStyleSheet("""
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
        close_btn.clicked.connect(self.reject)
        footer_layout.addWidget(close_btn)
        
        # Dugme "Popravi automatski" (ako ima fixable items)
        fixable_items = [
            item for item in self._get_all_items() 
            if item.fixable and self.config.allow_auto_fix
        ]
        
        if fixable_items:
            auto_fix_btn = QPushButton(f"🔧 Popravi ({len(fixable_items)})")
            auto_fix_btn.setStyleSheet("""
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
            auto_fix_btn.clicked.connect(lambda: self._on_auto_fix(fixable_items))
            footer_layout.addWidget(auto_fix_btn)
        
        # Dugme "Export" (ako je validno i config dozvoljava)
        if self.report.valid and self.config.show_export_button:
            export_btn = QPushButton("✅ Export XML")
            export_btn.setStyleSheet("""
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
            """)
            export_btn.clicked.connect(self._on_export)
            footer_layout.addWidget(export_btn)
        
        # Dugme "Sačuvaj izvještaj"
        save_report_btn = QPushButton("💾 Sačuvaj izvještaj")
        save_report_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        save_report_btn.clicked.connect(self._on_save_report)
        footer_layout.addWidget(save_report_btn)
        
        return footer
    
    def _setup_signals(self):
        """Postavi signale."""
        pass
    
    def _get_all_items(self) -> List[ValidationItem]:
        """Dobavi sve validacijske stavke."""
        all_items = []
        all_items.extend(self.report.zaglavlje_items)
        all_items.extend(self.report.naimenovanja_items)
        all_items.extend(self.report.historical_items)
        all_items.extend(self.report.legal_items)
        all_items.extend(self.report.contextual_items)
        return all_items
    
    def _get_severity_icon(self, severity: ValidationSeverity) -> str:
        """Dobavi ikonu za severity."""
        icons = {
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.INFO: "ℹ️",
            ValidationSeverity.SUGGESTION: "💡"
        }
        return icons.get(severity, "")
    
    def _on_details_toggled(self, state: int):
        """Handler za toggle detalja."""
        # Ovo bi trebalo sakriti/prikazati tab widget
        # Za sada ne radimo ništa
        pass
    
    def _on_auto_fix(self, items: List[ValidationItem]):
        """Handler za automatsko popravljanje."""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Automatsko popravljanje",
            f"Da li želite automatski popraviti {len(items)} stavki?\n\n"
            f"Ovo će ažurirati odgovarajuća polja u aplikaciji.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.auto_fix_requested.emit(items)
            self.accept()  # Zatvori dijalog nakon popravke
    
    def _on_export(self):
        """Handler za export."""
        self.export_requested.emit()
        self.accept()
    
    def _on_save_report(self):
        """Sačuvaj izvještaj u fajl."""
        from PySide6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj izvještaj validacije",
            "",
            "Text Files (*.txt);;HTML Files (*.html);;All Files (*)"
        )
        
        if filename:
            self._save_report_to_file(filename)
    
    def _save_report_to_file(self, filename: str):
        """Sačuvaj izvještaj u fajl."""
        try:
            content = self._generate_report_text()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "Izvještaj sačuvan",
                f"Izvještaj je sačuvan u: {filename}"
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Greška",
                f"Greška pri čuvanju izvještaja: {e}"
            )
    
    def _generate_report_text(self) -> str:
        """Generiši tekstualni izvještaj."""
        lines = []
        lines.append("=" * 60)
        lines.append("AGENT VALIDACIJA - IZVJEŠTAJ")
        lines.append(f"Datum: {self._get_current_datetime()}")
        lines.append("=" * 60)
        lines.append("")
        
        # Sažetak
        lines.append("📊 SAŽETAK:")
        lines.append(f"  Status: {'VALIDNO' if self.report.valid else 'NEVALIDNO'}")
        lines.append(f"  Greške: {self.report.error_count}")
        lines.append(f"  Upozorenja: {self.report.warning_count}")
        lines.append(f"  Informacije: {self.report.info_count}")
        lines.append(f"  Preporuke: {self.report.suggestion_count}")
        lines.append(f"  Sažetak: {self.report.summary}")
        lines.append("")
        
        # Preporuke
        if self.report.recommendations:
            lines.append("🎯 PREPORUKE:")
            for i, rec in enumerate(self.report.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        # Detalji po kategorijama
        all_items = self._get_all_items()
        if all_items:
            lines.append("📋 DETALJNA ANALIZA:")
            
            for item in all_items:
                severity_icon = self._get_severity_icon(item.severity)
                lines.append(f"")
                lines.append(f"{severity_icon} [{item.rule}] {item.field}")
                lines.append(f"   Poruka: {item.message}")
                if item.explanation:
                    lines.append(f"   Objašnjenje: {item.explanation}")
                if item.fixable:
                    lines.append(f"   [AUTO-FIX DOSTUPNO]")
        
        return "\n".join(lines)
    
    def _get_current_datetime(self) -> str:
        """Dobavi trenutni datum i vrijeme."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Helper funkcija za prikaz dijaloga
def show_enhanced_validation_dialog(
    report: ValidationReport,
    parent=None,
    config: DialogConfig = None
) -> bool:
    """
    Prikaži enhanced validation dijalog.
    
    Args:
        report: ValidationReport
        parent: Parent widget
        config: DialogConfig
    
    Returns:
        True ako je dijalog prihvaćen (OK), False ako je odbijen (Cancel)
    """
    dialog = EnhancedValidationDialog(report, config, parent)
    return dialog.exec() == QDialog.Accepted


# Test funkcija
def test_enhanced_dialog():
    """Testiraj enhanced validation dijalog."""
    from PySide6.QtWidgets import QApplication
    import sys
    from services.agent.agent_validation_service import (
        ValidationReport,
        ValidationItem,
        ValidationSeverity,
        ValidationCategory
    )
    
    app = QApplication(sys.argv)
    
    # Kreiraj test report
    report = ValidationReport(
        valid=False,
        error_count=2,
        warning_count=3,
        info_count=1,
        suggestion_count=1,
        zaglavlje_items=[
            ValidationItem(
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.REQUIRED_FIELD,
                rule="Rb.22",
                field="Iznos fakture",
                message="Rb.22 — Iznos fakture NIJE ažuriran: 15.000,00 ≠ 18.500,00",
                explanation="Iznos iz fakture se razlikuje od unesenog iznosa.",
                fixable=True,
                fix_action="auto_update_iznos"
            )
        ],
        naimenovanja_items=[
            ValidationItem(
                severity=ValidationSeverity.WARNING,
                category=ValidationCategory.CONSISTENCY,
                rule="Na2",
                field="Tarifni broj",
                message="Stavka 2: Tarifni broj '85061000' sadrži ne-digit karaktere",
                explanation="Tarifni brojevi bi trebali sadržavati samo cifre."
            )
        ],
        historical_items=[
            ValidationItem(
                severity=ValidationSeverity.INFO,
                category=ValidationCategory.HISTORICAL,
                rule="Historija",
                field="Supplier",
                message="MASTER TOOLS: 15 historijskih deklaracija",
                explanation="Supplier je ranije koristio sistem 15 puta."
            )
        ],
        legal_items=[
            ValidationItem(
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.LEGAL,
                rule="Na1",
                field="Povlastica",
                message="Stavka 1: EUP nije validna za Srbiju",
                explanation="Srbija nije članica EU. EUP povlastica nije validna."
            )
        ],
        contextual_items=[
            ValidationItem(
                severity=ValidationSeverity.SUGGESTION,
                category=ValidationCategory.CONTEXTUAL,
                rule="Grupisanje",
                field="Naimenovanja",
                message="Stavke 1, 3 mogu se grupisati",
                explanation="Sve stavke imaju isti tarifni broj, zemlju, povlasticu."
            )
        ],
        summary="❌ 2 grešaka (blokiraju export). ⚠️ 3 upozorenja. ℹ️ 1 informacija. 💡 1 preporuka",
        recommendations=[
            "Popravi: Rb.22 — Iznos fakture NIJE ažuriran: 15.000,00 ≠ 18.500,00",
            "Provjeri: Stavka 1: EUP nije validna za Srbiju",
            "Razmotri: Stavke 1, 3 mogu se grupisati"
        ]
    )
    
    # Prikaži dijalog
    config = DialogConfig(
        show_details=True,
        show_recommendations=True,
        allow_auto_fix=True,
        show_export_button=False
    )
    
    result = show_enhanced_validation_dialog(report, config=config)
    
    if result:
        print("✅ Dijalog prihvaćen")
    else:
        print("❌ Dijalog odbijen")
    
    sys.exit()


if __name__ == "__main__":
    test_enhanced_dialog()