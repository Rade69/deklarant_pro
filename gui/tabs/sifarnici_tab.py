"""
ASYCUDA Pro - Šifrarnici Tab
Tačna replika originalnog dizajna
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QLabel
)
from PySide6.QtCore import Qt
from gui.classic_style import ClassicColors, ClassicFonts


class SifarniciTab(QWidget):
    """Tab za pregled šifarnika"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {ClassicColors.BACKGROUND_WHITE};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Kontrole
        controls = self._create_controls()
        layout.addWidget(controls)
        
        # Search inputs
        search = self._create_search()
        layout.addWidget(search)
        
        # Tabela
        self.table = self._create_table()
        layout.addWidget(self.table)
        
        # Bottom label
        label = QLabel("ŠAMPON ZA KOSU")
        label.setFont(ClassicFonts.normal())
        layout.addWidget(label)
    
    def _create_controls(self):
        """Kreira kontrole"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        btn_novi = QPushButton("Novi")
        btn_novi.setFixedWidth(68)
        layout.addWidget(btn_novi)
        
        btn_brisi = QPushButton("Briši")
        btn_brisi.setFixedWidth(68)
        layout.addWidget(btn_brisi)
        
        cb_sve = QCheckBox("sve redove")
        cb_sve.setFixedWidth(90)
        layout.addWidget(cb_sve)
        
        # Dropdown
        combo = QComboBox()
        combo.addItem("šifarnik trgovački naziv")
        combo.setFixedWidth(180)
        layout.addWidget(combo)
        
        layout.addStretch()
        
        # Desna strana
        btn_imp = QPushButton("imp iz .xls")
        btn_imp.setFixedWidth(88)
        layout.addWidget(btn_imp)
        
        btn_exp = QPushButton("exp u .xls")
        btn_exp.setFixedWidth(88)
        layout.addWidget(btn_exp)
        
        return widget
    
    def _create_search(self):
        """Kreira search polja"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        for i in range(3):
            input_field = QLineEdit()
            input_field.setFixedWidth(80)
            layout.addWidget(input_field)
        
        layout.addStretch()
        
        return widget
    
    def _create_table(self):
        """Kreira tabelu šifarnika"""
        table = QTableWidget()
        table.setFont(ClassicFonts.normal())
        
        # Kolone
        columns = [
            ("", 30),  # Checkbox
            ("šifra", 80),
            ("naziv", 400),
            ("jed.mj", 60),
            ("tar.br", 100),
            ("opis 1.red", 200),
            ("opis 2.red", 200)
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
            ["✓", "VAIROŠTALINA", "VAIROŠTALINA POSUDA", "", "7013451000", "proizv.od stakla koji se koriste", "ostali.; od kaljenog stakla; od kal"],
            ["", "", "", "", "0000000000", "", ""],
            ["", "KGM", "2104100000", "Supe, corbe i preparati za njih:", "SUPE,PARADAJZ CORBA-po fakturi", "CIMET 3 gr"],
            ["", "KGM", "0904200000", "Cimet:droblijen ili mleven", "CIMET 3 gr", ""],
            ["", "KGM", "1103119000", "Griz od pšenice;griz;od obične pšen", "PŠENIČNI GRIZ", ""],
        ]
        
        table.setRowCount(len(test_data))
        
        for row_idx, row_data in enumerate(test_data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(row_idx, col_idx, item)
