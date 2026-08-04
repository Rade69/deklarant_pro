"""
Settings Panel - UI for settings management.

TASK 6: Styling improvements - GroupBox-ovi, bolji layout, styling
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QMessageBox, QGroupBox, QScrollArea,
    QSpinBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from typing import Dict, Any
import qtawesome as qta
from gui.tabs.admin.panels import styles as S
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class SettingsPanel(QWidget):
    """Settings panel UI sa poboljšanim styling-om."""

    # Signali
    save_requested = Signal(dict)
    reset_requested = Signal()
    test_sound_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za Settings panel."""
        self.setStyleSheet(S.PANEL_BASE_STYLE)
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(S.GROUPBOX_STYLE)

        # Input fields styling
        input_style = """
            QComboBox, QSpinBox, QLineEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px 10px;
                background-color: white;
                font-size: 13px;
                min-width: 200px;
            }
            QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
                border-color: #bbb;
            }
            QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
                border-color: #3477a5;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #52697b;
                margin-right: 10px;
            }
        """
        
        for widget in self.findChildren(QComboBox):
            widget.setStyleSheet(input_style)
        for widget in self.findChildren(QSpinBox):
            widget.setStyleSheet(input_style)
        for widget in self.findChildren(QLineEdit):
            widget.setStyleSheet(input_style)

        # Checkbox styling
        checkbox_style = """
            QCheckBox {
                spacing: 8px;
                font-size: 13px;
                font-weight: normal;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3477a5;
                border-color: #3477a5;
            }
            QCheckBox::indicator:hover {
                border-color: #bbb;
            }
        """
        
        for checkbox in self.findChildren(QCheckBox):
            checkbox.setStyleSheet(checkbox_style)

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
                background-color: #bfd0dc;
            }
            QPushButton#saveButton {
                background-color: #3477a5;
                color: white;
                border-color: #3477a5;
            }
            QPushButton#saveButton:hover {
                background-color: #2b648c;
            }
            QPushButton#resetButton {
                background-color: #ad3e3e;
                color: white;
                border-color: #ad3e3e;
            }
            QPushButton#resetButton:hover {
                background-color: #943535;
            }
        """
        
        self.btn_save.setStyleSheet(button_style)
        self.btn_reset.setStyleSheet(button_style)
        self.btn_test_sound.setStyleSheet(button_style)

    def setup_ui(self):
        """Setup UI-a sa grupisanim settings-ima."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.cog', color='#17324a', scale_factor=2).pixmap(32, 32))
        header_layout.addWidget(header_icon)
        
        header = QLabel("Settings")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #17324a; margin-left: 10px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        settings_widget = QWidget()
        main_layout = QVBoxLayout(settings_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)

        # ===== APPEARANCE GROUP =====
        appearance_group = QGroupBox("🎨 Izgled")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        appearance_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        appearance_layout.setVerticalSpacing(10)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['light', 'dark'])
        self.theme_combo.setToolTip("Odaberi temu (svijetla/tamna)")
        appearance_layout.addRow("Tema:", self.theme_combo)

        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItems(['sr', 'en'])
        self.language_combo.setToolTip("Odaberi jezik interfejsa")
        appearance_layout.addRow("Jezik:", self.language_combo)

        main_layout.addWidget(appearance_group)

        # ===== BACKUP GROUP =====
        backup_group = QGroupBox("💾 Backup")
        backup_layout = QFormLayout(backup_group)
        backup_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        backup_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        backup_layout.setVerticalSpacing(10)

        # Auto backup
        self.auto_backup_check = QCheckBox()
        self.auto_backup_check.setToolTip("Automatski kreiraj backup periodično")
        backup_layout.addRow("Auto Backup:", self.auto_backup_check)

        # Backup interval
        self.backup_interval_spin = QSpinBox()
        self.backup_interval_spin.setRange(1, 365)
        self.backup_interval_spin.setValue(7)
        self.backup_interval_spin.setSuffix(" dana")
        self.backup_interval_spin.setToolTip("Koliko često kreirati backup")
        backup_layout.addRow("Backup Interval:", self.backup_interval_spin)

        main_layout.addWidget(backup_group)

        # ===== LOGGING GROUP =====
        logging_group = QGroupBox("📋 Logovanje")
        logging_layout = QFormLayout(logging_group)
        logging_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        logging_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        logging_layout.setVerticalSpacing(10)

        # Log level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        self.log_level_combo.setToolTip("Nivo detaljnosti logova")
        logging_layout.addRow("Log Level:", self.log_level_combo)

        main_layout.addWidget(logging_group)

        sound_group = QGroupBox("🔊 Zvučna obavještenja")
        sound_layout = QFormLayout(sound_group)
        sound_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        sound_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sound_layout.setVerticalSpacing(10)

        self.completion_sound_check = QCheckBox()
        self.completion_sound_check.setToolTip(
            "Pusti zvuk kada se završi parsiranje, automatizacija ili izvoz"
        )
        sound_layout.addRow("Zvuk završetka:", self.completion_sound_check)

        self.btn_test_sound = QPushButton(
            qta.icon('fa5s.volume-up', color='#17324a'),
            " Testiraj zvuk"
        )
        self.btn_test_sound.setToolTip("Odmah pusti probni zvuk")
        self.btn_test_sound.clicked.connect(self.test_sound_requested.emit)
        sound_layout.addRow("Provjera:", self.btn_test_sound)

        main_layout.addWidget(sound_group)

        # ===== PLUGINS GROUP =====
        plugins_group = QGroupBox("🔌 Plugin-i")
        plugins_layout = QFormLayout(plugins_group)
        plugins_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        plugins_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        plugins_layout.setVerticalSpacing(10)

        # Plugins auto load
        self.plugins_auto_load_check = QCheckBox()
        self.plugins_auto_load_check.setToolTip("Automatski učitaj plugin-ove pri pokretanju")
        plugins_layout.addRow("Auto Load Plugins:", self.plugins_auto_load_check)

        main_layout.addWidget(plugins_group)

        main_layout.addStretch()

        scroll.setWidget(settings_widget)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_reset = QPushButton(
            qta.icon('fa5s.undo', color='white'),
            " Resetuj"
        )
        self.btn_reset.setFont(QFont("Arial", 13))
        self.btn_reset.setToolTip("Vrati na fabrička podešavanja")
        self.btn_reset.setObjectName("resetButton")
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        self.btn_reset.setMinimumHeight(38)
        btn_layout.addWidget(self.btn_reset)

        btn_layout.addStretch()

        self.btn_save = QPushButton(
            qta.icon('fa5s.save', color='white'),
            " Sačuvaj Settings"
        )
        self.btn_save.setFont(QFont("Arial", 13))
        self.btn_save.setToolTip("Sačuvaj trenutna podešavanja")
        self.btn_save.setObjectName("saveButton")
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_save.setMinimumHeight(38)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    # PUBLIC API

    def set_settings(self, settings: Dict[str, Any]):
        """
        Postavi settings.

        Args:
            settings: Dict sa settings-ima
        """
        self.theme_combo.setCurrentText(settings.get('theme', 'light'))
        self.language_combo.setCurrentText(settings.get('language', 'sr'))
        self.auto_backup_check.setChecked(settings.get('auto_backup', True))
        self.backup_interval_spin.setValue(settings.get('backup_interval_days', 7))
        self.log_level_combo.setCurrentText(settings.get('log_level', 'INFO'))
        self.plugins_auto_load_check.setChecked(settings.get('plugins_auto_load', True))
        self.completion_sound_check.setChecked(
            settings.get('completion_sound_enabled', True)
        )

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

    def _on_save_clicked(self):
        """Save button clicked."""
        settings = {
            'theme': self.theme_combo.currentText(),
            'language': self.language_combo.currentText(),
            'auto_backup': self.auto_backup_check.isChecked(),
            'backup_interval_days': self.backup_interval_spin.value(),
            'log_level': self.log_level_combo.currentText(),
            'plugins_auto_load': self.plugins_auto_load_check.isChecked(),
            'completion_sound_enabled': self.completion_sound_check.isChecked(),
        }

        self.save_requested.emit(settings)

    def _on_reset_clicked(self):
        """Reset button clicked."""
        reply = QMessageBox.question(
            self,
            "Potvrda",
            "Da li zaista želiš da resetuješ settings na fabrička podešavanja?\n\n"
            "Ova akcija će poništiti sve tvoje izmjene.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.reset_requested.emit()
