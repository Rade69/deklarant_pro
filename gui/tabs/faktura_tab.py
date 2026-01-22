"""
ASYCUDA Pro - Faktura Tab
Tačna replika originalnog dizajna
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel
)
from PySide6.QtCore import Qt
from gui.classic_style import ClassicColors, ClassicFonts


class FakturaTab(QWidget):
    """Tab za prikaz i uređivanje fakture"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {ClassicColors.BACKGROUND_WHITE};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Kontrole
        controls = self._create_controls()
        layout.addWidget(controls)
        
        # Tabela
        self.table = self._create_table()
        layout.addWidget(self.table)
        
        # Navigacija
        navigation = self._create_navigation()
        layout.addWidget(navigation)
    
    def _create_controls(self):
        """Kreira kontrole iznad tabele"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Prva linija
        line1 = QHBoxLayout()
        line1.setSpacing(4)
        
        btn_novi = QPushButton("Novi")
        btn_novi.setFixedWidth(68)
        line1.addWidget(btn_novi)
        
        btn_dodaj = QPushButton("Dodaj")
        btn_dodaj.setFixedWidth(68)
        line1.addWidget(btn_dodaj)
        
        cb_dupli = QCheckBox("dupli")
        cb_dupli.setFixedWidth(60)
        line1.addWidget(cb_dupli)
        
        line1.addStretch()
        layout.addLayout(line1)
        
        # Druga linija
        line2 = QHBoxLayout()
        line2.setSpacing(4)
        
        cb_sve_redove = QCheckBox("sve redove")
        cb_sve_redove.setFixedWidth(90)
        line2.addWidget(cb_sve_redove)
        
        cb_lokacija = QCheckBox("Lokacija podatke")
        cb_lokacija.setFixedWidth(120)
        line2.addWidget(cb_lokacija)
        
        # Dropdown
        combo = QComboBox()
        combo.addItem("trgovački naziv")
        combo.setFixedWidth(150)
        line2.addWidget(combo)
        
        # Input polja
        input1 = QLineEdit("5506,000")
        input1.setFixedWidth(100)
        line2.addWidget(input1)
        
        input2 = QLineEdit("13426,17")
        input2.setFixedWidth(100)
        line2.addWidget(input2)
        
        # Dugmad
        btn_import = QPushButton("Import fakture")
        btn_import.setFixedWidth(98)
        line2.addWidget(btn_import)
        
        btn_xls = QPushButton("xls prikaz")
        btn_xls.setFixedWidth(78)
        line2.addWidget(btn_xls)
        
        btn_kreiraj = QPushButton("kreiraj naimenovanja")
        btn_kreiraj.setFixedWidth(138)
        line2.addWidget(btn_kreiraj)
        
        cb_obrisi = QCheckBox("obriši 3.red opisa u naimenovanjima")
        cb_obrisi.setFixedWidth(220)
        line2.addWidget(cb_obrisi)
        
        line2.addStretch()
        
        # Desna strana
        input3 = QLineEdit("133,0000")
        input3.setFixedWidth(80)
        line2.addWidget(input3)
        
        input4 = QLineEdit("133,0000")
        input4.setFixedWidth(80)
        line2.addWidget(input4)
        
        btn_azuriraj = QPushButton("ažuriraj trgovačke nazive")
        btn_azuriraj.setFixedWidth(148)
        line2.addWidget(btn_azuriraj)
        
        layout.addLayout(line2)
        
        return widget
    
    def _create_table(self):
        """Kreira tabelu za prikaz stavki fakture"""
        table = QTableWidget()
        table.setFont(ClassicFonts.normal())
        
        # Kolone
        columns = [
            ("naim red", 40),
            ("br trg.nazv", 80),
            ("naziv", 200),
            ("količina", 80),
            ("vrijednost", 80),
            ("popust", 60),
            ("zem.por", 60),
            ("tar.broj", 100),
            ("podjela", 60),
            ("neto", 80),
            ("bruto", 80),
            ("jed.mj", 50),
            ("povlastica", 80),
            ("koleta", 60)
        ]
        
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([col[0] for col in columns])
        
        # Postavi širine kolona
        for i, (_, width) in enumerate(columns):
            table.setColumnWidth(i, width)
        
        # Postavi visinu header-a
        table.horizontalHeader().setFixedHeight(24)
        
        # Postavi visinu redova
        table.verticalHeader().setDefaultSectionSize(24)
        table.verticalHeader().hide()
        
        # Dodaj test podatke
        self._populate_test_data(table)
        
        return table
    
    def _populate_test_data(self, table):
        """Popunjava tabelu test podacima"""
        test_data = [
            ["1", "1", "BATERIJA", "000,000000", "340,00", "0,00", "CN", "8506503000", "", "133,0000", "133,0000", "", "0,0000"],
            ["", "2", "BATERIJA", "500,000000", "510,00", "0,00", "CN", "8506503000", "", "0,0000", "0,0000", "", "0,0000"],
            ["2", "3", "KATANAC", "36,000000", "83,16", "0,00", "CN", "4820103000", "", "0,0000", "0,0000", "", "0,0000"],
            ["1", "4", "BATERIJA", "20,000000", "64,20", "0,00", "CN", "8506503000", "", "0,0000", "0,0000", "", "0,0000"],
            ["1", "5", "BATERIJA", "30,000000", "28,80", "0,00", "CN", "8506503000", "", "0,0000", "0,0000", "", "0,0000"],
        ]
        
        table.setRowCount(len(test_data))
        
        for row_idx, row_data in enumerate(test_data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter if col_idx > 2 else Qt.AlignLeft)
                table.setItem(row_idx, col_idx, item)
    
    def _create_navigation(self):
        """Kreira navigacione kontrole"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        btn_prev = QPushButton("◄ Prethodno")
        btn_prev.setFixedWidth(100)
        layout.addWidget(btn_prev)
        
        layout.addStretch()
        
        label = QLabel("Stavka 1 od 1")
        label.setFont(ClassicFonts.normal())
        layout.addWidget(label)
        
        layout.addStretch()
        
        btn_next = QPushButton("Sledeće ►")
        btn_next.setFixedWidth(100)
        layout.addWidget(btn_next)
        
        btn_nova = QPushButton("+ Nova stavka")
        btn_nova.setFixedWidth(100)
        layout.addWidget(btn_nova)
        
        btn_obrisi = QPushButton("🗑 Obriši")
        btn_obrisi.setFixedWidth(100)
        layout.addWidget(btn_obrisi)
        
        return widget
