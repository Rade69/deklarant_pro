"""
Komponenta za navigacione kontrole u Naimenovanja tabu.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame
)
from PySide6.QtCore import Signal


class NavigationControls(QWidget):
    """
    Komponenta za navigacione kontrole - dropdown, dugmad za navigaciju, CRUD operacije.
    """
    
    # Signali
    item_selected = Signal(int)  # Emituje kada se selektuje item iz dropdowna
    previous_clicked = Signal()   # Emituje kada se klikne Prethodno
    next_clicked = Signal()       # Emituje kada se klikne Sljedeće
    add_clicked = Signal()        # Emituje kada se klikne Dodaj
    delete_clicked = Signal()     # Emituje kada se klikne Obriši
    suggest_clicked = Signal()    # Emituje kada se klikne Sugeriši tarifu
    validate_clicked = Signal()   # Emituje kada se klikne Validacija
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Postavlja UI elemente."""
        self.setObjectName("navBar")
        self.setFixedHeight(50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        
        # Sekcija 1: Dropdown selektor
        lbl_nav = QLabel("Naimenovanje:")
        lbl_nav.setProperty("class", "nav-label")
        layout.addWidget(lbl_nav)
        
        self.combo_items = QComboBox()
        self.combo_items.setMinimumWidth(220)
        self.combo_items.setProperty("class", "nav-combo")
        layout.addWidget(self.combo_items)
        
        # Brojač
        self.lbl_indicator = QLabel("1 od 1")
        self.lbl_indicator.setProperty("class", "nav-counter")
        layout.addWidget(self.lbl_indicator)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Sekcija 2: Navigacija
        lbl_navigacija = QLabel("Navigacija:")
        lbl_navigacija.setProperty("class", "nav-label")
        layout.addWidget(lbl_navigacija)
        
        # Dugmad za navigaciju (narandžasta sa tekstom)
        self.btn_previous = QPushButton("◀ Prethodno")
        self.btn_previous.setProperty("class", "btn_navigation_orange")
        layout.addWidget(self.btn_previous)
        
        self.btn_next = QPushButton("Sljedeće ▶")
        self.btn_next.setProperty("class", "btn_navigation_orange")
        layout.addWidget(self.btn_next)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Sekcija 3: CRUD dugmad (SOLID boje)
        self.btn_add = QPushButton("+ Dodaj")
        self.btn_add.setProperty("class", "btn_solid_green")
        layout.addWidget(self.btn_add)
        
        self.btn_delete = QPushButton("🗑 Obriši")
        self.btn_delete.setProperty("class", "btn_solid_red")
        layout.addWidget(self.btn_delete)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Sekcija 4: Akciona dugmad (SOLID boje)
        self.btn_suggest = QPushButton("💡 Sugeriši tarifu")
        self.btn_suggest.setProperty("class", "btn_solid_yellow")
        layout.addWidget(self.btn_suggest)
        
        self.btn_validate = QPushButton("✓ Validacija")
        self.btn_validate.setProperty("class", "btn_solid_cyan")
        layout.addWidget(self.btn_validate)
        
        # Spacer
        layout.addStretch()
    
    def _create_separator(self) -> QFrame:
        """Kreira vertikalni separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedWidth(2)
        sep.setFixedHeight(30)
        return sep
    
    def _connect_signals(self):
        """Povezuje signale komponente."""
        self.combo_items.currentIndexChanged.connect(self._on_combo_changed)
        self.btn_previous.clicked.connect(self.previous_clicked.emit)
        self.btn_next.clicked.connect(self.next_clicked.emit)
        self.btn_add.clicked.connect(self.add_clicked.emit)
        self.btn_delete.clicked.connect(self.delete_clicked.emit)
        self.btn_suggest.clicked.connect(self.suggest_clicked.emit)
        self.btn_validate.clicked.connect(self.validate_clicked.emit)
    
    def _on_combo_changed(self, index: int):
        """Handler za promenu selekcije u dropdownu."""
        if index >= 0:
            self.item_selected.emit(index)
    
    def update_items(self, items_data: list):
        """
        Ažurira dropdown sa novim podacima.
        
        Args:
            items_data: Lista tuple-ova (ordinal_no, tariff_code)
        """
        self.combo_items.clear()
        for ordinal_no, tariff_code in items_data:
            label = f"#{ordinal_no} - {tariff_code}" if tariff_code else f"#{ordinal_no} - "
            self.combo_items.addItem(label)
    
    def set_current_index(self, index: int):
        """Postavlja trenutni indeks u dropdownu."""
        self.combo_items.setCurrentIndex(index)
    
    def update_indicator(self, current: int, total: int):
        """Ažurira indikator pozicije."""
        self.lbl_indicator.setText(f"{current} od {total}")
    
    def update_button_states(self, can_go_previous: bool, can_go_next: bool, can_delete: bool):
        """Ažurira stanje dugmadi."""
        self.btn_previous.setEnabled(can_go_previous)
        self.btn_next.setEnabled(can_go_next)
        self.btn_delete.setEnabled(can_delete)