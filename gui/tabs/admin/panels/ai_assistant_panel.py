"""
AI Assistant Panel - UI za testiranje AI tarifnih prijedloga.

Omogućava:
- Testiranje HybridTariffAgent sa proizvoljnim nazivom robe
- Prikaz rezultata sa confidence skorom
- Historija testiranja
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QGroupBox,
    QGridLayout, QScrollArea, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from gui.tabs.admin.panels import styles as S


class AIAssistantPanel(QWidget):
    """AI Assistant Panel UI za testiranje tarifnih prijedloga."""

    # Signali
    test_requested = Signal(str)  # naziv_robe
    clear_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling."""
        self.setStyleSheet(S.PANEL_BASE_STYLE)
        
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(S.GROUPBOX_STYLE)

    def setup_ui(self):
        """Setup UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Splitter za input i rezultate
        splitter = QSplitter(Qt.Vertical)

        # Input sekcija
        input_widget = self._create_input_section()
        splitter.addWidget(input_widget)

        # Results sekcija
        results_widget = self._create_results_section()
        splitter.addWidget(results_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

    def _create_header(self) -> QWidget:
        """Kreiraj header sa naslovom."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Ikona i naslov
        icon_label = QLabel()
        try:
            icon = qta.icon('fa5s.robot', color='#0078d4', scale_factor=2.0)
            icon_label.setPixmap(icon.pixmap(32, 32))
        except:
            icon_label.setText("🤖")

        title_label = QLabel("AI ASSISTANT - Testiranje Tarifnih Prijedloga")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("color: #333; padding: 5px;")

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch()

        return widget

    def _create_input_section(self) -> QWidget:
        """Kreiraj input sekciju za testiranje."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Group: Unos naziva robe
        group = QGroupBox("📝 Unos Naziva Robe")
        group_layout = QVBoxLayout(group)

        # Input polje
        self.input_naziv = QLineEdit()
        self.input_naziv.setPlaceholderText("Unesite naziv robe za testiranje (npr. 'čokolada punjena kremom')")
        self.input_naziv.setMinimumHeight(40)
        self.input_naziv.setFont(QFont("Segoe UI", 12))
        group_layout.addWidget(self.input_naziv)

        # Buttoni
        btn_layout = QHBoxLayout()

        self.btn_test = QPushButton("🤖 Testiraj AI Prijedlog")
        self.btn_test.setMinimumHeight(40)
        self.btn_test.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.btn_test.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004494;
            }
        """)
        self.btn_test.clicked.connect(self._on_test_clicked)

        self.btn_clear = QPushButton("🗑️ Očisti")
        self.btn_clear.setMinimumHeight(40)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #666;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        self.btn_clear.clicked.connect(self._on_clear_clicked)

        btn_layout.addWidget(self.btn_test)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()

        group_layout.addLayout(btn_layout)
        layout.addWidget(group)

        # Info box
        info_group = QGroupBox("ℹ️ Kako Radi")
        info_layout = QVBoxLayout(info_group)
        info_label = QLabel(
            "1. Unesite naziv robe u polje iznad\n"
            "2. Kliknite 'Testiraj AI Prijedlog'\n"
            "3. AI će pretražiti:\n"
            "   • Historiju deklaracija (RAG)\n"
            "   • Zvanične tarife (PostgreSQL)\n"
            "   • AI model (Ollama qwen2.5:1.5b)\n"
            "4. Rezultati se prikazuju ispod sa confidence skorom"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; line-height: 1.6; padding: 5px;")
        info_layout.addWidget(info_label)

        layout.addWidget(info_group)

        return widget

    def _create_results_section(self) -> QWidget:
        """Kreiraj sekciju za prikaz rezultata."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Group: Rezultati
        self.group_results = QGroupBox("📊 Rezultati Testiranja")
        results_layout = QVBoxLayout(self.group_results)

        # Output area
        self.output_results = QTextEdit()
        self.output_results.setReadOnly(True)
        self.output_results.setFont(QFont("Consolas", 11))
        self.output_results.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        self.output_results.setPlaceholderText("Rezultati će se pojaviti ovdje nakon testiranja...")
        results_layout.addWidget(self.output_results)

        # Stats
        stats_layout = QGridLayout()

        self.lbl_confidence = QLabel("Confidence: -")
        self.lbl_confidence.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_confidence.setStyleSheet("color: #666;")

        self.lbl_method = QLabel("Metoda: -")
        self.lbl_method.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_method.setStyleSheet("color: #666;")

        self.lbl_review = QLabel("Review: -")
        self.lbl_review.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_review.setStyleSheet("color: #666;")

        stats_layout.addWidget(self.lbl_confidence, 0, 0)
        stats_layout.addWidget(self.lbl_method, 0, 1)
        stats_layout.addWidget(self.lbl_review, 0, 2)
        stats_layout.setColumnStretch(3, 1)

        results_layout.addLayout(stats_layout)

        layout.addWidget(self.group_results)

        return widget

    def _on_test_clicked(self):
        """Handle test button click."""
        naziv = self.input_naziv.text().strip()
        if naziv:
            self.test_requested.emit(naziv)

    def _on_clear_clicked(self):
        """Handle clear button click."""
        self.input_naziv.clear()
        self.output_results.clear()
        self.lbl_confidence.setText("Confidence: -")
        self.lbl_method.setText("Metoda: -")
        self.lbl_review.setText("Review: -")
        self.clear_requested.emit()

    # ============================================================
    # PUBLIC API
    # ============================================================

    def set_input(self, naziv_robe: str):
        """Postavi naziv robe u input polje."""
        self.input_naziv.setText(naziv_robe)

    def display_results(self, result: dict):
        """
        Prikaži rezultate testiranja.

        Args:
            result: Dict sa tarifni_broj, confidence, method, explanation, needs_review
        """
        # Formatiraj output
        output = []
        output.append("=" * 60)
        output.append("🤖 AI PRIJEDLOG")
        output.append("=" * 60)
        output.append("")

        tarifni = result.get('tarifni_broj', 'N/A')
        output.append(f"📌 TARIFNI BROJ: {tarifni}")
        output.append("")

        confidence = result.get('confidence', 0)
        confidence_pct = f"{confidence:.0%}"
        output.append(f"📊 CONFIDENCE: {confidence_pct}")

        # Confidence color coding
        if confidence >= 0.85:
            output.append("   Status: ✅ VISOK - Auto-popuni")
        elif confidence >= 0.60:
            output.append("   Status: ⚠️ SREDNJI - Pregledaj")
        else:
            output.append("   Status: ❌ NIZAK - Obavezno pregledaj")

        output.append("")
        output.append(f"🔧 METODA: {result.get('method', 'N/A')}")
        output.append("")

        needs_review = result.get('needs_review', False)
        output.append(f"⚠️ REVIEW POTREBAN: {'DA' if needs_review else 'NE'}")
        output.append("")

        output.append("=" * 60)
        output.append("📝 OBJAŠNJENJE:")
        output.append("=" * 60)
        output.append(result.get('explanation', 'N/A'))
        output.append("")

        # Candidates
        candidates = result.get('candidates', [])
        if candidates:
            output.append("=" * 60)
            output.append("📋 ALTERNATIVNI PRIJEDLOZI:")
            output.append("=" * 60)
            for i, cand in enumerate(candidates[:5], 1):
                output.append(f"{i}. {cand.get('tarifni_broj', 'N/A')} - {cand.get('naziv_robe', 'N/A')[:50]}")
                output.append(f"   Confidence: {cand.get('confidence', 0):.0%}, Source: {cand.get('source', 'N/A')}")
            output.append("")

        # Display
        self.output_results.setText("\n".join(output))

        # Update stats labels
        self.lbl_confidence.setText(f"Confidence: {confidence_pct}")
        if confidence >= 0.85:
            self.lbl_confidence.setStyleSheet("color: #28a745; font-weight: bold;")
        elif confidence >= 0.60:
            self.lbl_confidence.setStyleSheet("color: #ffc107; font-weight: bold;")
        else:
            self.lbl_confidence.setStyleSheet("color: #dc3545; font-weight: bold;")

        self.lbl_method.setText(f"Metoda: {result.get('method', 'N/A')}")
        self.lbl_review.setText(f"Review: {'DA ⚠️' if needs_review else 'NE ✅'}")
        if needs_review:
            self.lbl_review.setStyleSheet("color: #dc3545; font-weight: bold;")
        else:
            self.lbl_review.setStyleSheet("color: #28a745; font-weight: bold;")

    def display_error(self, error: str):
        """
        Prikaži grešku.

        Args:
            error: Poruka greške
        """
        self.output_results.setText(f"❌ GREŠKA:\n\n{error}")
        self.lbl_confidence.setText("Confidence: -")
        self.lbl_method.setText("Metoda: -")
        self.lbl_review.setText("Review: -")
