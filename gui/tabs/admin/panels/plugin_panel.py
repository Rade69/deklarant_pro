"""
Upravljanje dodatcima Panel - UI for plugin management.

TASK 1: Styling improvements - boje, spacing, borders, ikone
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox,
    QFrame, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from typing import List, Dict, Any
import qtawesome as qta


class PluginPanel(QWidget):
    """Upravljanje dodatcima panel UI sa poboljšanim styling-om."""

    # Signali
    install_requested = Signal(str)  # filepath
    reload_requested = Signal()
    remove_requested = Signal(str)   # plugin_name

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za Upravljanje dodatcima panel."""
        # Lista parsera styling
        self.parsers_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 3px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        # Info panel styling
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 8px;
                font-size: 13px;
                font-family: 'Arial', sans-serif;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)

        # GroupBox styling
        self.findChild(QGroupBox).setStyleSheet("""
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #333;
            }
        """)

        # Button styling
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #999;
                border-color: #e0e0e0;
            }
        """
        
        self.btn_install.setStyleSheet(button_style)
        self.btn_reload.setStyleSheet(button_style)
        self.btn_remove.setStyleSheet(button_style)

        # Header styling
        header = self.findChild(QLabel, "header_label")
        if header:
            header.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 15px;
                }
            """)

    def setup_ui(self):
        """Setup UI-a sa poboljšanim layout-om."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 10px margins oko cijelog panel-a
        layout.setSpacing(15)  # 15px spacing između elemenata

        # Header sa objectName za styling
        header = QLabel("<h2>📦 Upravljanje dodatcima</h2>")
        header.setObjectName("header_label")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; margin-bottom: 15px;")
        layout.addWidget(header)

        # Main content (horizontal layout sa separator-om)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)  # 15px spacing između liste i info panel-a

        # Lista parsera (lijevo) - 60% width
        list_group = QGroupBox("Instalirani Parseri")
        list_group.setFont(QFont("Arial", 13, QFont.Bold))
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(5, 5, 5, 5)
        
        self.parsers_list = QListWidget()
        self.parsers_list.setFont(QFont("Arial", 13))
        self.parsers_list.currentItemChanged.connect(
            self._on_parser_selected
        )
        self.parsers_list.setMinimumWidth(250)
        list_layout.addWidget(self.parsers_list)
        
        content_layout.addWidget(list_group, stretch=3)

        # Separator line (vertikalna linija između liste i info panel-a)
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #ddd; background-color: #ddd;")
        separator.setFixedWidth(2)
        content_layout.addWidget(separator)

        # Info panel (desno) - 40% width
        info_group = QGroupBox("Informacije o Parseru")
        info_group.setFont(QFont("Arial", 13, QFont.Bold))
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(10, 10, 10, 10)

        # Scroll area za info text
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Arial", 13))
        self.info_text.setMinimumHeight(250)
        self.info_text.setHtml(self._get_empty_info_html())
        
        scroll.setWidget(self.info_text)
        info_layout.addWidget(scroll)

        content_layout.addWidget(info_group, stretch=2)

        layout.addLayout(content_layout)

        # Buttons sa ikonama
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_install = QPushButton(
            qta.icon('fa5s.download', color='#333333'),
            " Instaliraj Novi Parser"
        )
        self.btn_install.setFont(QFont("Arial", 13))
        self.btn_install.setToolTip("Odaberi .py fajl parsera i instaliraj ga")
        self.btn_install.clicked.connect(self._on_install_clicked)
        self.btn_install.setMinimumHeight(35)
        btn_layout.addWidget(self.btn_install)

        self.btn_reload = QPushButton(
            qta.icon('fa5s.sync', color='#333333'),
            " Ponovo učitaj parsere"
        )
        self.btn_reload.setFont(QFont("Arial", 13))
        self.btn_reload.setToolTip("Ponovo učitaj sve instalirane parsere")
        self.btn_reload.clicked.connect(self._on_reload_clicked)
        self.btn_reload.setMinimumHeight(35)
        btn_layout.addWidget(self.btn_reload)

        self.btn_remove = QPushButton(
            qta.icon('fa5s.trash-alt', color='#333333'),
            " Ukloni"
        )
        self.btn_remove.setFont(QFont("Arial", 13))
        self.btn_remove.setToolTip("Ukloni odabrani parser")
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_remove.setEnabled(False)
        self.btn_remove.setMinimumHeight(35)
        btn_layout.addWidget(self.btn_remove)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _get_empty_info_html(self):
        """Vraća HTML za prazan info panel."""
        return """
        <div style="text-align: center; color: #999; padding: 40px;">
            <div style="font-size: 48px; margin-bottom: 10px;">📦</div>
            <div style="font-size: 14px;">Nijedan parser nije odabran</div>
            <div style="font-size: 12px; margin-top: 5px;">Odaberite parser iz liste da vidite informacije</div>
        </div>
        """

    def _get_empty_state_html(self):
        """Vraća HTML za empty state kada nema parsera."""
        return """
        <div style="text-align: center; color: #999; padding: 40px;">
            <div style="font-size: 48px; margin-bottom: 10px;">📦</div>
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 5px;">Nema instaliranih parsera</div>
            <div style="font-size: 13px;">Klikni 'Instaliraj Novi Parser' da dodaš parser</div>
        </div>
        """

    # PUBLIC API (Controller poziva)

    def set_plugins(self, plugins: List[Dict[str, Any]]):
        """
        Postavi listu plugin-a.

        Args:
            plugins: Lista dict-ova sa plugin info-m
        """
        self.parsers_list.clear()

        if not plugins:
            # Empty state sa boljom porukom
            item = QListWidgetItem()
            item.setFlags(Qt.NoItemFlags)  # Ne može se selektovati
            self.parsers_list.addItem(item)
            
            # Kreiraj widget za empty state
            empty_widget = QWidget()
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setAlignment(Qt.AlignCenter)
            
            empty_label = QLabel("📦 Nema instaliranih parsera\n\nKlikni 'Instaliraj Novi Parser' da dodaš parser")
            empty_label.setStyleSheet("color: #999; font-size: 14px; text-align: center;")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(empty_label)
            
            self.parsers_list.setItemWidget(item, empty_widget)
            return

        for plugin in plugins:
            display_name = f"✅ {plugin.get('name', 'Unknown')}"

            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, plugin)
            item.setFont(QFont("Arial", 13))

            self.parsers_list.addItem(item)

    def show_success(self, message: str):
        """Prikaži success poruku."""
        QMessageBox.information(self, "Uspjeh", message)

    def show_error(self, message: str):
        """Prikaži error poruku."""
        QMessageBox.critical(self, "Greška", message)

    def show_warning(self, message: str):
        """Prikaži warning poruku."""
        QMessageBox.warning(self, "Upozorenje", message)

    # PRIVATE HANDLERS

    def _on_parser_selected(self, current, previous):
        """Parser selected - prikaži info."""
        if not current:
            self.info_text.setHtml(self._get_empty_info_html())
            self.btn_remove.setEnabled(False)
            return

        self.btn_remove.setEnabled(True)

        data = current.data(Qt.UserRole)

        # Format info sa boljim styling-om
        info = f"""
        <div style="font-size: 13px; line-height: 1.6;">
            <table style="width: 100%;">
                <tr>
                    <td style="font-weight: bold; width: 100px;">Ime:</td>
                    <td>{data.get('name', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Prioritet:</td>
                    <td>{data.get('priority', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Klijent:</td>
                    <td>{data.get('client', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Firma:</td>
                    <td>{data.get('firma', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Verzija:</td>
                    <td>{data.get('version', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Autor:</td>
                    <td>{data.get('author', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="font-weight: bold;">Fajl:</td>
                    <td style="font-family: 'Courier New', monospace; font-size: 12px;">{data.get('filename', 'N/A')}</td>
                </tr>
            </table>
        </div>
        """

        self.info_text.setHtml(info)

    def _on_install_clicked(self):
        """Install button clicked."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Parser Fajl",
            "",
            "Python fajlovi (*.py)"
        )

        if filepath:
            self.install_requested.emit(filepath)

    def _on_reload_clicked(self):
        """Reload button clicked."""
        self.reload_requested.emit()

    def _on_remove_clicked(self):
        """Remove button clicked."""
        current = self.parsers_list.currentItem()
        if not current:
            return

        data = current.data(Qt.UserRole)
        plugin_name = data.get('name', '')

        reply = QMessageBox.question(
            self,
            "Potvrda",
            f"Da li zaista želiš da obrišeš parser '{plugin_name}'?\n\n"
            f"Ova akcija je nepovratna!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.remove_requested.emit(plugin_name)
