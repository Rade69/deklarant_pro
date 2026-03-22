"""
Database Panel - UI for database management.

TASK 9: Styling improvements - Database info, bolji layout, progress bar
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QGroupBox, QProgressBar,
    QFrame, QGridLayout
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from typing import List, Dict, Any
import qtawesome as qta


class DatabasePanel(QWidget):
    """Database management panel UI sa poboljšanim styling-om."""

    # Signali
    backup_requested = Signal(str)
    restore_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za Database panel."""
        # GroupBox styling
        groupbox_style = """
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 14px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #333;
            }
        """
        
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(groupbox_style)

        # Backup list styling
        self.backup_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        # Progress bar styling
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f5f5f5;
                height: 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
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
            QPushButton#backupButton {
                background-color: #28a745;
                color: white;
                border-color: #28a745;
            }
            QPushButton#backupButton:hover {
                background-color: #218838;
            }
            QPushButton#restoreButton {
                background-color: #0078d4;
                color: white;
                border-color: #0078d4;
            }
            QPushButton#restoreButton:hover {
                background-color: #106ebe;
            }
            QPushButton#refreshButton {
                background-color: #6c757d;
                color: white;
                border-color: #6c757d;
            }
            QPushButton#refreshButton:hover {
                background-color: #5a6268;
            }
        """
        
        self.btn_backup.setStyleSheet(button_style)
        self.btn_restore.setStyleSheet(button_style)
        self.btn_refresh.setStyleSheet(button_style)

        # Info labels styling
        for label in self.findChildren(QLabel):
            if label.objectName() == "info_label":
                label.setStyleSheet("color: #666; font-size: 13px;")

    def setup_ui(self):
        """Setup UI-a sa Database info sekcijom."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header sa ikonicom
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.database', color='#333333', scale_factor=2).pixmap(32, 32))
        header_layout.addWidget(header_icon)
        
        header = QLabel("Database Management")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; margin-left: 10px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # ===== DATABASE INFO GROUP =====
        db_info_group = QGroupBox("📊 Informacije o Bazi")
        db_info_layout = QGridLayout(db_info_group)
        db_info_layout.setVerticalSpacing(10)
        db_info_layout.setHorizontalSpacing(20)

        # Database path
        self.lbl_db_path = QLabel("Lokacija:")
        self.lbl_db_path.setObjectName("info_label")
        self.lbl_db_path.setFont(QFont("Arial", 13))
        db_info_layout.addWidget(self.lbl_db_path, 0, 0)

        self.val_db_path = QLabel("N/A")
        self.val_db_path.setFont(QFont("Courier New", 12))
        self.val_db_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        db_info_layout.addWidget(self.val_db_path, 0, 1)

        # Database size
        self.lbl_db_size = QLabel("Veličina:")
        self.lbl_db_size.setObjectName("info_label")
        self.lbl_db_size.setFont(QFont("Arial", 13))
        db_info_layout.addWidget(self.lbl_db_size, 1, 0)

        self.val_db_size = QLabel("N/A")
        self.val_db_size.setFont(QFont("Arial", 13, QFont.Bold))
        self.val_db_size.setStyleSheet("color: #0078d4;")
        db_info_layout.addWidget(self.val_db_size, 1, 1)

        # Last backup
        self.lbl_last_backup = QLabel("Zadnji Backup:")
        self.lbl_last_backup.setObjectName("info_label")
        self.lbl_last_backup.setFont(QFont("Arial", 13))
        db_info_layout.addWidget(self.lbl_last_backup, 2, 0)

        self.val_last_backup = QLabel("Nema backup-a")
        self.val_last_backup.setObjectName("info_label")
        self.val_last_backup.setFont(QFont("Arial", 13))
        db_info_layout.addWidget(self.val_last_backup, 2, 1)

        # Total backups
        self.lbl_total_backups = QLabel("Ukupno Backup-a:")
        self.lbl_total_backups.setObjectName("info_label")
        self.lbl_total_backups.setFont(QFont("Arial", 13))
        db_info_layout.addWidget(self.lbl_total_backups, 3, 0)

        self.val_total_backups = QLabel("0")
        self.val_total_backups.setFont(QFont("Arial", 13, QFont.Bold))
        self.val_total_backups.setStyleSheet("color: #28a745;")
        db_info_layout.addWidget(self.val_total_backups, 3, 1)

        layout.addWidget(db_info_group)

        # ===== BACKUP GROUP =====
        backup_group = QGroupBox("💾 Kreiraj Backup")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setSpacing(10)

        backup_info = QLabel("Kreiraj backup trenutne baze podataka. Preporučuje se prije većih operacija.")
        backup_info.setObjectName("info_label")
        backup_info.setWordWrap(True)
        backup_layout.addWidget(backup_info)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_backup = QPushButton(
            qta.icon('fa5s.download', color='white'),
            " Kreiraj Backup"
        )
        self.btn_backup.setFont(QFont("Arial", 13, QFont.Bold))
        self.btn_backup.setToolTip("Kreiraj backup trenutne baze podataka")
        self.btn_backup.clicked.connect(self._on_backup_clicked)
        self.btn_backup.setMinimumHeight(40)
        self.btn_backup.setObjectName("backupButton")
        btn_layout.addWidget(self.btn_backup)

        btn_layout.addStretch()
        backup_layout.addLayout(btn_layout)
        layout.addWidget(backup_group)

        # ===== RESTORE GROUP =====
        restore_group = QGroupBox("📩 Obnova iz Backup-a")
        restore_layout = QVBoxLayout(restore_group)
        restore_layout.setSpacing(10)

        restore_info = QLabel("Odaberi backup fajl iz liste i obnovi bazu podataka.")
        restore_info.setObjectName("info_label")
        restore_info.setWordWrap(True)
        restore_layout.addWidget(restore_info)

        # Backup list
        self.backup_list = QListWidget()
        self.backup_list.setFont(QFont("Arial", 13))
        self.backup_list.setMaximumHeight(250)
        self.backup_list.setMinimumHeight(150)
        self.backup_list.itemSelectionChanged.connect(self._on_backup_selection_changed)
        self.backup_list.itemDoubleClicked.connect(self._on_backup_double_clicked)
        restore_layout.addWidget(self.backup_list)

        # Restore buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_restore = QPushButton(
            qta.icon('fa5s.upload', color='white'),
            " Obnovi Izabranu"
        )
        self.btn_restore.setFont(QFont("Arial", 13, QFont.Bold))
        self.btn_restore.setToolTip("Obnovi bazu iz izabranog backup fajla")
        self.btn_restore.clicked.connect(self._on_restore_clicked)
        self.btn_restore.setEnabled(False)
        self.btn_restore.setMinimumHeight(40)
        self.btn_restore.setObjectName("restoreButton")
        btn_layout.addWidget(self.btn_restore)

        self.btn_refresh = QPushButton(
            qta.icon('fa5s.sync', color='white'),
            " Refresh Listu"
        )
        self.btn_refresh.setFont(QFont("Arial", 13))
        self.btn_refresh.setToolTip("Osveži listu dostupnih backup-ova")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.setObjectName("refreshButton")
        btn_layout.addWidget(self.btn_refresh)

        btn_layout.addStretch()
        restore_layout.addLayout(btn_layout)
        layout.addWidget(restore_group)

        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFormat("%p% - U toku...")
        layout.addWidget(self.progress)

        layout.addStretch()

    # PUBLIC API

    def set_backups(self, backups: List[Dict[str, Any]]):
        """
        Postavi listu backup-ova.

        Args:
            backups: Lista dict-ova sa backup info-m
        """
        self.backup_list.clear()

        if not backups:
            item = QListWidgetItem("📦 Nema dostupnih backup-ova")
            item.setFlags(Qt.NoItemFlags)
            self.backup_list.addItem(item)
            self.val_total_backups.setText("0")
            self.val_last_backup.setText("Nema backup-a")
            return

        for backup in backups:
            display = f"📦 {backup['filename']} ({self._format_size(backup['size'])})"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, backup)
            item.setFont(QFont("Arial", 13))
            self.backup_list.addItem(item)

        # Update info
        self.val_total_backups.setText(str(len(backups)))
        
        # Zadnji backup (prvi u listi jer su sortirani od najnovijeg)
        last_backup = backups[0]
        from datetime import datetime
        try:
            created = datetime.fromisoformat(last_backup['created'])
            self.val_last_backup.setText(created.strftime("%d.%m.%Y. %H:%M"))
        except:
            self.val_last_backup.setText(last_backup.get('filename', 'N/A'))

    def set_database_info(self, db_path: str, db_size: int):
        """
        Postavi informacije o bazi.

        Args:
            db_path: Putanja do database fajla
            db_size: Veličina u bajtovima
        """
        self.val_db_path.setText(db_path)
        self.val_db_size.setText(self._format_size(db_size))

    def show_progress(self, value: int, visible: bool = True):
        """
        Prikaži progress bar.

        Args:
            value: Vrijednost progress-a (0-100)
            visible: Da li prikazati progress bar
        """
        self.progress.setVisible(visible)
        if visible:
            self.progress.setValue(value)

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

    def _on_backup_clicked(self):
        """Backup button clicked."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj Backup",
            "",
            "Database fajlovi (*.db)"
        )

        if filepath:
            self.backup_requested.emit(filepath)

    def _on_restore_clicked(self):
        """Restore button clicked."""
        current = self.backup_list.currentItem()
        if not current:
            return

        data = current.data(Qt.UserRole)
        backup_path = data.get('filepath', '')

        reply = QMessageBox.warning(
            self,
            "Potvrda Restore-a",
            "⚠️ UPOZORENJE: Ova operacija će PREPISATI trenutnu bazu podataka!\n\n"
            f"Backup fajl: {backup_path}\n\n"
            "Da li ste sigurni da želite nastaviti?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.restore_requested.emit(backup_path)

    def _on_backup_double_clicked(self, item):
        """Backup item double clicked - auto restore."""
        if item.data(Qt.UserRole):
            self._on_restore_clicked()

    def _on_backup_selection_changed(self):
        """Backup selection changed - enable/disable restore button."""
        current = self.backup_list.currentItem()
        has_selection = current is not None and current.data(Qt.UserRole) is not None
        self.btn_restore.setEnabled(has_selection)

    def _on_refresh_clicked(self):
        """Refresh button clicked."""
        self.refresh_requested.emit()

    def _format_size(self, size: int) -> str:
        """Formatiraj veličinu u ljudima čitljiv format."""
        if size == 0:
            return "N/A"
        
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        size_float = float(size)

        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1

        return f"{size_float:.1f} {units[unit_index]}"
