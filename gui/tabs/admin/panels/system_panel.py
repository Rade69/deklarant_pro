"""
System Panel - UI for system info.

TASK 13: Styling improvements - viÅ¡e sekcija, bolji layout, export opcije
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QGroupBox,
    QGridLayout, QScrollArea, QComboBox, QFileDialog,
    QInputDialog, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from typing import Dict, Any
import qtawesome as qta
import json
import socket
from gui.tabs.admin.panels import styles as S
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class SystemPanel(QWidget):
    """System Info panel UI sa poboljÅ¡anim styling-om."""

    refresh_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za System Info panel."""
        self.setStyleSheet(S.PANEL_BASE_STYLE)
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(S.GROUPBOX_STYLE)

        # Info text styling
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 12px;
                line-height: 1.6;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)

        # Label styling
        for label in self.findChildren(QLabel):
            if label.objectName() == "info_label":
                label.setStyleSheet("color: #666; font-size: 13px;")
            elif label.objectName() == "info_value":
                label.setStyleSheet("color: #333; font-size: 13px; font-weight: 500;")
            elif label.objectName() == "section_header":
                label.setStyleSheet("color: #0078d4; font-size: 14px; font-weight: bold;")

        # Button styling
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
                font-weight: 500;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QPushButton#copyButton {
                background-color: #0078d4;
                color: white;
                border-color: #0078d4;
            }
            QPushButton#copyButton:hover {
                background-color: #106ebe;
            }
            QPushButton#exportButton {
                background-color: #28a745;
                color: white;
                border-color: #28a745;
            }
            QPushButton#exportButton:hover {
                background-color: #218838;
            }
            QPushButton#refreshButton {
                background-color: #6c757d;
                color: white;
                border-color: #6c757d;
            }
            QPushButton#refreshButton:hover {
                background-color: #5a6268;
            }
            QPushButton#aboutButton {
                background-color: #17a2b8;
                color: white;
                border-color: #17a2b8;
            }
            QPushButton#aboutButton:hover {
                background-color: #138496;
            }
            QPushButton#aiHealthButton {
                background-color: #6f42c1;
                color: white;
                border-color: #6f42c1;
            }
            QPushButton#aiHealthButton:hover {
                background-color: #5a32a3;
            }
        """
        
        self.btn_copy.setStyleSheet(button_style)
        self.btn_export.setStyleSheet(button_style)
        self.btn_refresh.setStyleSheet(button_style)
        self.btn_about.setStyleSheet(button_style)
        self.btn_ai_health.setStyleSheet(button_style)

    def setup_ui(self):
        """Setup UI-a sa viÅ¡e sekcija."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header sa ikonicom
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.info-circle', color='#333333', scale_factor=2).pixmap(32, 32))
        header_layout.addWidget(header_icon)
        
        header = QLabel("Sistemske Informacije")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; margin-left: 10px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # Scroll area za content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(15)

        # ===== APPLICATION INFO GROUP =====
        app_group = QGroupBox("ðŸ“¦ Informacije o Aplikaciji")
        app_layout = QGridLayout(app_group)
        app_layout.setVerticalSpacing(8)
        app_layout.setHorizontalSpacing(15)

        # App name
        self.lbl_app_name = QLabel("Aplikacija:")
        self.lbl_app_name.setObjectName("info_label")
        self.lbl_app_name.setFont(QFont("Arial", 13))
        app_layout.addWidget(self.lbl_app_name, 0, 0)

        self.val_app_name = QLabel("Deklarant Pro")
        self.val_app_name.setObjectName("info_value")
        self.val_app_name.setFont(QFont("Arial", 13, QFont.Bold))
        app_layout.addWidget(self.val_app_name, 0, 1)

        # Version
        self.lbl_version = QLabel("Verzija:")
        self.lbl_version.setObjectName("info_label")
        app_layout.addWidget(self.lbl_version, 1, 0)

        self.val_version = QLabel("2.0.0")
        self.val_version.setObjectName("info_value")
        app_layout.addWidget(self.val_version, 1, 1)

        # Build date
        self.lbl_build = QLabel("Datum Build-a:")
        self.lbl_build.setObjectName("info_label")
        app_layout.addWidget(self.lbl_build, 2, 0)

        self.val_build = QLabel("N/A")
        self.val_build.setObjectName("info_value")
        app_layout.addWidget(self.val_build, 2, 1)

        scroll_layout.addWidget(app_group)

        # ===== SYSTEM INFO GROUP =====
        system_group = QGroupBox("ðŸ’» Sistemske Informacije")
        system_layout = QGridLayout(system_group)
        system_layout.setVerticalSpacing(8)
        system_layout.setHorizontalSpacing(15)

        # OS
        self.lbl_os = QLabel("Operativni Sistem:")
        self.lbl_os.setObjectName("info_label")
        self.lbl_os.setFont(QFont("Arial", 13))
        system_layout.addWidget(self.lbl_os, 0, 0)

        self.val_os = QLabel("N/A")
        self.val_os.setObjectName("info_value")
        system_layout.addWidget(self.val_os, 0, 1)

        # Python version
        self.lbl_python = QLabel("Python:")
        self.lbl_python.setObjectName("info_label")
        system_layout.addWidget(self.lbl_python, 1, 0)

        self.val_python = QLabel("N/A")
        self.val_python.setObjectName("info_value")
        system_layout.addWidget(self.val_python, 1, 1)

        # Qt version
        self.lbl_qt = QLabel("Qt Verzija:")
        self.lbl_qt.setObjectName("info_label")
        system_layout.addWidget(self.lbl_qt, 2, 0)

        self.val_qt = QLabel("N/A")
        self.val_qt.setObjectName("info_value")
        system_layout.addWidget(self.val_qt, 2, 1)

        # Architecture
        self.lbl_arch = QLabel("Arhitektura:")
        self.lbl_arch.setObjectName("info_label")
        system_layout.addWidget(self.lbl_arch, 3, 0)

        self.val_arch = QLabel("N/A")
        self.val_arch.setObjectName("info_value")
        system_layout.addWidget(self.val_arch, 3, 1)

        scroll_layout.addWidget(system_group)


        # ===== DETAILED INFO TEXT =====
        detailed_group = QGroupBox("ðŸ“‹ Detaljne Informacije")
        detailed_layout = QVBoxLayout(detailed_group)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Courier New", 11))
        self.info_text.setMinimumHeight(250)
        detailed_layout.addWidget(self.info_text)

        scroll_layout.addWidget(detailed_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # ===== ACTION BUTTONS =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Copy button with format selector
        self.btn_copy = QPushButton(
            qta.icon('fa5s.copy', color='white'),
            " Kopiraj"
        )
        self.btn_copy.setFont(QFont("Arial", 13))
        self.btn_copy.setToolTip("Kopiraj system info u clipboard")
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_copy.setMinimumHeight(40)
        self.btn_copy.setObjectName("copyButton")
        btn_layout.addWidget(self.btn_copy)

        # Export button
        self.btn_export = QPushButton(
            qta.icon('fa5s.file-export', color='white'),
            " Export"
        )
        self.btn_export.setFont(QFont("Arial", 13))
        self.btn_export.setToolTip("Eksportuj system info u fajl")
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setObjectName("exportButton")
        btn_layout.addWidget(self.btn_export)

        # About button
        self.btn_about = QPushButton(
            qta.icon('fa5s.info-circle', color='white'),
            " About"
        )
        self.btn_about.setFont(QFont("Arial", 13))
        self.btn_about.setToolTip("Informacije o aplikaciji")
        self.btn_about.clicked.connect(self._on_about_clicked)
        self.btn_about.setMinimumHeight(40)
        self.btn_about.setObjectName("aboutButton")
        btn_layout.addWidget(self.btn_about)

        self.btn_ai_health = QPushButton(
            qta.icon('fa5s.heartbeat', color='white'),
            " OsvjeÅ¾i AI"
        )
        self.btn_ai_health.setFont(QFont("Arial", 13))
        self.btn_ai_health.setToolTip("Provjeri AI providere i mreÅ¾u")
        self.btn_ai_health.clicked.connect(self._on_ai_health_clicked)
        self.btn_ai_health.setMinimumHeight(40)
        self.btn_ai_health.setObjectName("aiHealthButton")
        btn_layout.addWidget(self.btn_ai_health)

        btn_layout.addStretch()

        # Refresh button
        self.btn_refresh = QPushButton(
            qta.icon('fa5s.sync', color='white'),
            " Refresh"
        )
        self.btn_refresh.setFont(QFont("Arial", 13))
        self.btn_refresh.setToolTip("OsveÅ¾i system informacije")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.setObjectName("refreshButton")
        btn_layout.addWidget(self.btn_refresh)

        layout.addLayout(btn_layout)

    # PUBLIC API

    def set_system_info(self, info: Dict[str, Any]):
        """
        Postavi system info za prikaz.

        Args:
            info: Dict sa system info-m
        """
        self._current_info = info

        # Application info
        self.val_app_name.setText(info.get('app_name', 'N/A'))
        self.val_version.setText(info.get('app_version', 'N/A'))
        self.val_build.setText(info.get('build_date', 'N/A'))

        # System info
        self.val_os.setText(info.get('platform', 'N/A'))
        self.val_python.setText(info.get('python_version', 'N/A'))
        self.val_qt.setText(info.get('qt_version', 'N/A'))
        self.val_arch.setText(info.get('architecture', 'N/A'))

        # Detailed info
        self._update_detailed_info(info)

    def show_success(self, message: str):
        """PrikaÅ¾i success poruku."""
        QMessageBox.information(self, "Uspjeh", message)

    def show_error(self, message: str):
        """PrikaÅ¾i error poruku."""
        QMessageBox.critical(self, "GreÅ¡ka", message)

    # PRIVATE HANDLERS

    def _update_detailed_info(self, info: Dict[str, Any]):
        """AÅ¾uriraj detaljne informacije u text editor-u."""
        detailed = f"""
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
DEKLARANT PRO - SYSTEM INFORMATION
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

APLIKACIJA
----------
  Naziv:       {info.get('app_name', 'N/A')}
  Verzija:     {info.get('app_version', 'N/A')}
  Datum build: {info.get('build_date', 'N/A')}

SISTEM
------
  OS:          {info.get('platform', 'N/A')}
  Python:      {info.get('python_version', 'N/A')}
  Qt:          {info.get('qt_version', 'N/A')}
  Arhitektura: {info.get('architecture', 'N/A')}

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
Generisano: {info.get('generated_at', 'N/A')}
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
"""
        self.info_text.setText(detailed)

    def _get_copy_text(self, format: str = 'text') -> str:
        """
        Vrati tekst za kopiranje u odabranom formatu.

        Args:
            format: 'text', 'markdown', ili 'json'

        Returns:
            Formatirani tekst
        """
        if not hasattr(self, '_current_info'):
            return ""

        excluded_keys = {'database_size', 'plugins_count'}
        info = {
            key: value
            for key, value in self._current_info.items()
            if key not in excluded_keys
        }

        if format == 'json':
            return json.dumps(info, indent=2, ensure_ascii=False)
        elif format == 'markdown':
            return f"""# Deklarant Pro â€” System Info

## Aplikacija
- **Naziv:** {info.get('app_name', 'N/A')}
- **Verzija:** {info.get('app_version', 'N/A')}
- **Datum build:** {info.get('build_date', 'N/A')}

## Sistem
- **OS:** {info.get('platform', 'N/A')}
- **Python:** {info.get('python_version', 'N/A')}
- **Qt:** {info.get('qt_version', 'N/A')}
- **Arhitektura:** {info.get('architecture', 'N/A')}

Generisano: {info.get('generated_at', 'N/A')}
"""
        else:  # plain text
            return f"""Deklarant Pro â€” System Info
===========================
Aplikacija: {info.get('app_name', 'N/A')} v{info.get('app_version', 'N/A')}
Datum build: {info.get('build_date', 'N/A')}

Sistem:
  OS:          {info.get('platform', 'N/A')}
  Python:      {info.get('python_version', 'N/A')}
  Qt:          {info.get('qt_version', 'N/A')}
  Arhitektura: {info.get('architecture', 'N/A')}

Generisano: {info.get('generated_at', 'N/A')}
"""

    def _on_copy_clicked(self):
        """Copy button clicked - show format selector."""
        format_choice, ok = QInputDialog.getItem(
            self,
            "Odaberi Format",
            "U kom formatu Å¾eliÅ¡ da kopiraÅ¡?",
            ["Plain Text", "Markdown", "JSON"],
            0,
            False
        )
        
        if ok:
            format_map = {
                'Plain Text': 'text',
                'Markdown': 'markdown',
                'JSON': 'json'
            }
            
            text = self._get_copy_text(format_map.get(format_choice, 'text'))
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            
            self.show_success(f"System info kopiran u clipboard!\nFormat: {format_choice}")

    def _on_export_clicked(self):
        """Export button clicked."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Eksportuj System Info",
            "",
            "Text fajlovi (*.txt);;Markdown (*.md);;JSON (*.json);;Svi fajlovi (*)"
        )

        if filepath:
            # Odredi format po ekstenziji
            if filepath.endswith('.md'):
                format = 'markdown'
            elif filepath.endswith('.json'):
                format = 'json'
            else:
                format = 'text'

            text = self._get_copy_text(format)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.show_success(f"System info eksportovan!\n\nFajl: {filepath}\nFormat: {format.upper()}")
            except Exception as e:
                self.show_error(f"GreÅ¡ka pri eksportu:\n{str(e)}")

    def _on_refresh_clicked(self):
        """Refresh button clicked."""
        self.refresh_requested.emit()

    def _on_about_clicked(self):
        """About button clicked."""
        QMessageBox.about(
            self,
            "O Deklarant Pro",
            """
            <h2>Deklarant Pro</h2>
            <p><b>Verzija:</b> 2.0.0</p>
            <p><b>Opis:</b> Aplikacija za carinske deklaracije</p>
            <p><b>Tehnologija:</b> Python + PySide6 (Qt6)</p>
            <br>
            <p><b>Admin Tab:</b> Centralni panel za administraciju</p>
            <ul>
                <li>Upravljanje parserima</li>
                <li>Baza podataka</li>
                <li>Analitika</li>
                <li>Logovi</li>
                <li>Sistemske informacije</li>
                <li>Licenca</li>
                <li>UÄenje iz XML-ova</li>
            </ul>
            <br>
            <p>Â© 2026 Radovan StojanoviÄ‡</p>
            """
        )

    def _on_ai_health_clicked(self):
        """AI health check: kljuÄevi, DNS i testni odgovor providera."""
        from gui.tabs.agent.widgets.llm_provider import LLMProvider

        provider = LLMProvider()
        lines = [
            "AI HEALTH CHECK",
            "===============",
            "",
            f"DeepSeek kljuÄ: {'OK' if provider.has_deepseek() else 'NEDOSTAJE'}",
            f"Groq kljuÄ:     {'OK' if provider.has_groq() else 'NEDOSTAJE'}",
            f"Gemini kljuÄ:   {'OK' if provider.has_gemini() else 'NEDOSTAJE'}",
            f"OpenRouter kljuÄ: {'OK' if provider.has_openrouter() else 'NEDOSTAJE'}",
            f"Aktivni redoslijed (primarni): {provider.active_provider()}",
            "",
            "DNS provjera:",
        ]

        host_map = {
            "DeepSeek": "api.deepseek.com",
            "Groq": "api.groq.com",
            "Gemini": "generativelanguage.googleapis.com",
            "OpenRouter": "openrouter.ai",
        }
        for name, host in host_map.items():
            try:
                ip = socket.gethostbyname(host)
                lines.append(f"- {name}: OK ({host} -> {ip})")
            except Exception as e:
                lines.append(f"- {name}: GREÅ KA ({host}) - {e}")

        lines.extend([
            "",
            "Test upit (kratki ping):",
        ])

        tests = [
            ("Groq", provider.has_groq(), "groq"),
            ("Gemini", provider.has_gemini(), "gemini"),
            ("OpenRouter", provider.has_openrouter(), "openrouter"),
            ("DeepSeek", provider.has_deepseek(), "deepseek"),
        ]
        messages = [
            {"role": "system", "content": "Odgovori samo sa TEST_OK."},
            {"role": "user", "content": "TEST_OK"},
        ]

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for name, has_key, forced in tests:
                if not has_key:
                    lines.append(f"- {name}: preskoÄeno (nema kljuÄ)")
                    continue
                prev_deepseek = provider.deepseek_key
                prev_groq = provider.groq_key
                prev_gemini = provider.gemini_key
                prev_openrouter = provider.openrouter_key
                try:
                    if forced == "deepseek":
                        provider.groq_key = ""
                        provider.gemini_key = ""
                        provider.openrouter_key = ""
                    elif forced == "groq":
                        provider.deepseek_key = ""
                        provider.gemini_key = ""
                        provider.openrouter_key = ""
                    elif forced == "gemini":
                        provider.deepseek_key = ""
                        provider.groq_key = ""
                        provider.openrouter_key = ""
                    else:
                        provider.deepseek_key = ""
                        provider.groq_key = ""
                        provider.gemini_key = ""

                    out = (provider.complete(messages, max_tokens=16) or "").strip()
                    preview = out[:80] if out else "<prazan odgovor>"
                    lines.append(f"- {name}: OK ({preview})")
                except Exception as e:
                    lines.append(f"- {name}: GREÅ KA ({e})")
                finally:
                    provider.deepseek_key = prev_deepseek
                    provider.groq_key = prev_groq
                    provider.gemini_key = prev_gemini
                    provider.openrouter_key = prev_openrouter
        finally:
            QApplication.restoreOverrideCursor()

        QMessageBox.information(self, "AI status", "\n".join(lines))

