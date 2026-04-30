import logging
logger = logging.getLogger(__name__)
"""
Deklarant Pro - Naimenovanja Tab
IMPLEMENTACIJA SA POSTOJEĆIM .ui FAJLOM

Ova verzija:
✅ Učitava POSTOJEĆI .ui fajl (naimenovanja_tab_OPTIMIZED.ui)
✅ NE MIJENJA GUI strukturu
✅ Implementira samo FUNKCIONALNOST (data binding, navigation, CRUD)
✅ Dodaje samo navigation controls i summary panel iznad postojećeg grid-a

Author: Radovan + Claude
Date: February 2026
"""

import os
import re
import sys
import warnings
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path

from database.db import get_connection_pool, get_db_connection

HAS_POSTGRESQL = True

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QFrame,
    QApplication,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QGroupBox,
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt, Signal, QTimer, QPoint, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QTextOption

from services.naimenovanja.tariff_service import TariffService
from services.naimenovanja.constants import NaimenovanjaConstants
from services.tariff_mapping_service import TariffMapping, validate_preference
from services.tariff_controls_service import check_tariff_controls, get_required_docs
from gui.tabs.base_view import BaseTabView
from gui.dialogs.inspection_dialog import InspectionDialog

from core.draft import DeclarationDraft, NaimenovanjeDraft

try:
    import qtawesome as qta

    QTAWESOME_AVAILABLE = True
    sys.stderr.write(
        f"✅ [NaimenovanjaTab] QtAwesome učitan (verzija: {qta.__version__})\n"
    )
    sys.stderr.flush()
except ImportError as e:
    QTAWESOME_AVAILABLE = False
    sys.stderr.write(f"❌ [NaimenovanjaTab] QtAwesome import FAILED: {e}\n")
    sys.stderr.flush()


class BlackLineWidget(QWidget):
    """Widget koji direktno crta crnu liniju - zaobilazi sve probleme sa stylesheet-om"""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        painter.end()


class NaimenovanjaView(BaseTabView):
    """
    Naimenovanja Tab - respektuje postojeću .ui strukturu.

    Dodaje:
    - Navigation bar (dropdown, prev/next, add/delete)
    - Summary panel (key metrics)
    - Data binding (load/save)
    - CRUD operacije

    NE mijenja:
    - Grid strukturu iz .ui fajla
    - Widget pozicije
    - Layout form-a
    """

    # data_changed naslijeđen iz BaseTabView
    import_xml_requested = Signal(str)
    suggest_tariff_requested = Signal()

    def __init__(
        self, draft: Optional[DeclarationDraft] = None, on_dirty: Optional[Callable] = None
    ):
        super().__init__()
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        self.current_item_index = 0
        self.is_loading = False

        # Initialize timers for debouncing
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._batch_save_fields)

        self.tariff_timer = QTimer()
        self.tariff_timer.setSingleShot(True)
        self.tariff_timer.timeout.connect(self._perform_tariff_lookup)

        # Initialize cache for tariff descriptions
        self.tariff_cache = {}

        # Initialize connection pool (lazy initialization)
        self.connection_pool = None

        # Widget cache - brzi pristup widgetima bez findChild
        self.widget_cache = {}

        # Field mapping - PRILAGOĐENO widget names iz naimenovanja_tab_OPTIMIZED.ui!
        self._init_field_mapping()

        # 1. Load existing .ui file
        self._load_ui_from_file()

        # Initialize widget cache AFTER loading UI
        self._init_widget_cache()

        # 2. Hide old controls from .ui (keep only rubrike 31-46 form)
        self._hide_old_ui_controls()

        # 2.5 Setup package dropdown (replace QLineEdit with QComboBox)
        self._setup_package_dropdown()

        # 2.6 Setup trading name field (replace QLineEdit with QTextEdit for multi-line)
        self._setup_trading_name_field()

        # 2.7 Setup Rb. 40 widgets (X/Y/Z combo + JSON šifarnik)
        self._setup_rb40_widgets()

        # 3. Add my new navigation bar
        self._add_navigation_controls()

        # 5. Add section heading (now includes buttons)
        self._add_section_heading()

        # 6. Add status bar
        self._add_status_bar()

        # 8. Set .ui as main widget and position it below nav/summary
        if hasattr(self, "ui"):
            # Create main layout
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # Add navigation bar
            if hasattr(self, "nav_bar"):
                main_layout.addWidget(self.nav_bar)

            # Add section heading (now includes buttons inside)
            if hasattr(self, "section_heading"):
                main_layout.addWidget(self.section_heading)

            # Add .ui widget (with form fields) - move it up by reducing top margin
            # Set smaller top margin to move grid upward
            self.ui.setContentsMargins(0, 0, 0, 0)

            # Add UI widget without stretch - let it take its natural size
            main_layout.addWidget(self.ui)

            # Status bar will be positioned with absolute geometry (see _load_ui_from_file())
            # NOT in layout - it's a direct child of self.ui like the grid!

        # 6. Connect field signals for auto-save
        self._connect_field_signals()

        # 6.5 Setup "apply to all" visual indicators and signals
        self._setup_apply_to_all_indicators()
        self._connect_special_field_signals()

        # 6.6 Postavi redosljed Tab navigacije
        self._setup_tab_order()

        # 7. Load data — redosljed bitan: clear mora biti PRIJE load, inače briše tarife
        self.draft.ensure_min_items(1)
        self._clear_all_input_fields()
        self._update_all_ui()
        self._load_current_item()

    def _create_icon_button(self, text: str, icon_name: str) -> QPushButton:
        """Create a button with an icon from QtAwesome."""
        btn = QPushButton(" " + text)  # razmak između ikone i teksta

        if QTAWESOME_AVAILABLE:
            try:
                qta_icon = qta.icon(icon_name, color="#FFFFFF")
                pixmap = qta_icon.pixmap(QSize(16, 16))
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(16, 16))
            except Exception as e:
                sys.stderr.write(f"❌ Could not load icon {icon_name}: {e}\n")
                sys.stderr.flush()

        return btn

    def _handle_error(self, error: Exception, context: str = "") -> None:
        """
        Centralizovani handler za greške.
        Loguje grešku, prikazuje korisniku i šalje u stderr.
        """
        error_msg = f"Greška {context}: {str(error)}"
        sys.stderr.write(f"❌ {error_msg}\n")
        sys.stderr.flush()

        # Prikaz korisniku (samo ako nema UI ili ako je glavni thread)
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Greška", f"{context}\n\n{str(error)}", QMessageBox.Ok
            )
        except Exception:
            # Ako ne može da prikaže UI, samo loguj
            pass

    def _get_connection_pool(self) -> None:
        """Dohvati PostgreSQL connection pool koristeći get_connection_pool()"""
        try:
            self.connection_pool = get_connection_pool()
            sys.stderr.write(
                f"✅ PostgreSQL connection pool dohvaćen (get_connection_pool)\n"
            )
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"⚠️  PostgreSQL connection pool nije uspešan: {e}\n")
            sys.stderr.flush()
            self.connection_pool = None

    def _init_field_mapping(self) -> None:
        """
        Field mapping: widget objectName → NaimenovanjeDraft field

        PRILAGOĐENO tačnim widget names iz naimenovanja_tab_OPTIMIZED.ui!
        """
        self.field_map = {
            # Rubrika 31 - Pakovanje
            "le_r31_oznake_br": "package_marks",  # Oznake (default: "X")
            "le_r31_paketa": "package_marks",  # Broj paketa (isto: "X")
            "le_r31_broj": "package_qty",  # ISPRAVLJENO: Broj (količina)
            "le_r31_vrsta": "package_code",  # ISPRAVLJENO: Vrsta (šifra - PK, CT...)
            "le_r31_vrsta_naziv": "package_name",  # Naziv pakovanja (auto-popunjava se)
            "te_r31_opis": "tariff_description1",    # Opis podbroja (8 cifara) — referenca
            "te_r31_opis_2": "tariff_description2",  # Heading opis (4-6 cifara) — referenca
            "le_r31_trg_naziv": "goods_trade_name",  # Trgovački naziv (automatski popunjava opis robe)
            # Rubrika 32
            "le_rubrika32": "ordinal_no",
            # Rubrika 33
            "le_rubrika33": "tariff_code",
            "le_rubrika33_podbroj": "tariff_suffix",  # Podbroj (000 za većinu, 100 za lijekove)
            # Rubrika 34
            "le_rubrika34_zemlja": "origin_country_code",
            "le_rubrika34_regija": "",  # Regija (custom)
            # Rubrika 35
            "le_rubrika35": "gross_mass_kg",
            # Rubrika 36
            "le_rubrika36": "preference_code",
            # Rubrika 37
            "le_rubrika37_1": "procedure_code",
            "le_rubrika37_2": "procedure_prev_code",  # Procedure code 2 (custom)
            # Rubrika 38
            "le_rubrika38": "net_mass_kg",
            # Rubrika 39
            "le_rubrika39": "quota_code",
            # Rubrika 40 – prethodni dokumenti
            "le_rubrika40_1": "previous_document",
            "le_rubrika40_2": "previous_document2",
            "le_rubrika40_3": "previous_document3",
            # Rubrika 41 — količina u dopunskim jedinicama
            "le_rubrika41": "supplementary_unit_qty",
            # Rubrika 42
            "le_rubrika42": "item_value",
            # Rubrika 43 M.V. — šifra dopunske mjerne jedinice
            "le_rubrika43": "supplementary_unit_code",
            # Rubrika 44 – P.D. kodovi + priložene isprave + formula troškova
            "le_rubrika44_1": "pd_codes",             # P.D. šifre iz zaglavlja (from_rule, auto, read-only)
            "le_rubrika44_3": "attached_document1",   # dokument porijekla (ref. br.)
            "le_rubrika44_4": "attached_document4",   # master polje (PE1/PE2 + broj)
            "le_rubrika44_5": "attached_document5",   # slobodno polje (nije auto-obračun)
            # Rubrika 45
            "le_rubrika45_sifra": "",  # Prilagođenje šifra
            "le_rubrika45_iznos": "",  # Prilagođenje iznos
            # Rubrika 46
            "le_rubrika46": "statistical_value",
        }

    def _init_widget_cache(self) -> None:
        """Build cache of all widgets by objectName for fast access"""
        if not hasattr(self, "ui") or not self.ui:
            return

        # Cache all widgets from ui
        self.widget_cache = {}
        widgets = self.ui.findChildren(QWidget)
        for widget in widgets:
            name = widget.objectName()
            if name:
                self.widget_cache[name] = widget

        # Also cache special combo box
        if hasattr(self, "combo_vrsta_pakovanja"):
            self.widget_cache["le_r31_vrsta"] = self.combo_vrsta_pakovanja

    def _get_widget(self, widget_name: str) -> Optional[QWidget]:
        """Get widget from cache or ui.findChild as fallback.
        Handles deleted C++ objects gracefully."""
        # Try cache first — but check if widget is still valid
        if widget_name in self.widget_cache:
            widget = self.widget_cache[widget_name]
            try:
                # Try to access the widget — raises RuntimeError if deleted
                _ = widget.objectName()
                return widget
            except RuntimeError:
                # C++ object deleted — remove from cache and re-find
                del self.widget_cache[widget_name]

        # Fallback: find in UI
        if hasattr(self, "ui") and self.ui:
            try:
                widget = self.ui.findChild(QWidget, widget_name)
                if widget:
                    self.widget_cache[widget_name] = widget
                return widget
            except RuntimeError:
                pass
        return None

    def _load_ui_from_file(self) -> None:
        """Load existing .ui file - NE mijenjamo strukturu!"""
        # Try multiple paths
        possible_paths = [
            Path(__file__).parent / "naimenovanja_tab_OPTIMIZED.ui",
            Path(__file__).parent.parent.parent
            / "ui"
            / "naimenovanja_tab_OPTIMIZED.ui",
            Path("ui/naimenovanja_tab_OPTIMIZED.ui"),
        ]

        ui_file_path = None
        for path in possible_paths:
            if path.exists():
                ui_file_path = str(path)
                break

        if not ui_file_path:
            logger.error(f"  ❌ UI file not found in any of these locations:")
            for path in possible_paths:
                logger.debug(f"     - {path}")
            QMessageBox.critical(
                self, "Error", "UI file not found:\nnaimenovanja_tab_OPTIMIZED.ui"
            )
            return

        ui_file = QFile(ui_file_path)
        if ui_file.open(QFile.ReadOnly):
            loader = QUiLoader()
            self.ui = loader.load(ui_file, self)
            ui_file.close()

            # Apply scaling and font increases to all elements inside .ui
            self._apply_ui_scaling()

            logger.info(f"  ✅ UI file loaded: {ui_file_path}")
        else:
            logger.error(f"  ❌ Cannot open UI file: {ui_file_path}")

    def _apply_ui_scaling(self) -> None:
        """
        Apply proportional scaling to all QGroupBox elements and increase fonts.
        Makes rubrike 31-46 form larger while keeping it within bounds.
        """
        if not hasattr(self, "ui"):
            return

        # Apply CSS class for styling (defined in naimenovanja_components.qss)
        self.ui.setObjectName("naimenovanjaUiWidget")

        # Scale up the main grid frame AND all widgets inside it (1.30x)
        main_grid = self.ui.findChild(QFrame, "main_grid_frame")
        if main_grid:
            scale_factor = 1.30

            # Scale the frame itself
            current_geom = main_grid.geometry()
            new_width = int(current_geom.width() * scale_factor)
            new_height = int(current_geom.height() * scale_factor)

            # OPCIJA B: Back to setGeometry() - we'll position status bar manually too
            main_grid.setGeometry(
                current_geom.x(), current_geom.y(), new_width, new_height
            )

            # CRITICAL: Scale ALL child widgets inside the frame
            for widget in main_grid.findChildren(QWidget):
                geom = widget.geometry()
                widget.setGeometry(
                    int(geom.x() * scale_factor),
                    int(geom.y() * scale_factor),
                    int(geom.width() * scale_factor),
                    int(geom.height() * scale_factor),
                )

            # Replace all VLine/HLine separators with BlackLineWidget (stylesheet doesn't work)
            all_frames = main_grid.findChildren(QFrame)

            line_count = 0
            for line_frame in all_frames:
                frame_shape = line_frame.frameShape()
                if frame_shape in (QFrame.VLine, QFrame.HLine):
                    # Get ABSOLUTE position relative to main_grid
                    absolute_pos = line_frame.mapTo(
                        main_grid, line_frame.rect().topLeft()
                    )
                    geo = line_frame.geometry()

                    # Create BlackLineWidget at absolute position
                    black_line = BlackLineWidget(main_grid)
                    black_line.setObjectName(f"black_{line_frame.objectName()}")
                    black_line.setGeometry(
                        absolute_pos.x(), absolute_pos.y(), geo.width(), geo.height()
                    )
                    black_line.show()
                    black_line.raise_()

                    # Hide original gray line
                    line_frame.hide()

                    line_count += 1
                    line_type = "VLine" if frame_shape == QFrame.VLine else "HLine"

            # Keep grid at scaled size (no extension - border stays visible)
            extra_height = 0
            final_height = new_height + extra_height

            # OPCIJA B: Set geometry with final height
            main_grid.setGeometry(
                current_geom.x(), current_geom.y(), new_width, final_height
            )

            # Store grid bottom position for status bar positioning
            self.grid_bottom_y = current_geom.y() + final_height
            self.grid_x = current_geom.x()
            self.grid_width = new_width


            # Add 2px border around main grid using BlackLineWidget (like before)
            # OPCIJA B: Borders on parent widget (absolute positioning)
            parent = main_grid.parent()
            border_width = 2

            # TOP border
            top_border = BlackLineWidget(parent)
            top_border.setObjectName("main_grid_border_top")
            top_border.setGeometry(
                current_geom.x(), current_geom.y(), new_width, border_width
            )
            top_border.show()
            top_border.raise_()

            # BOTTOM border
            bottom_border = BlackLineWidget(parent)
            bottom_border.setObjectName("main_grid_border_bottom")
            bottom_border.setGeometry(
                current_geom.x(),
                current_geom.y() + final_height - border_width,
                new_width,
                border_width,
            )
            bottom_border.show()
            bottom_border.raise_()

            # LEFT border
            left_border = BlackLineWidget(parent)
            left_border.setObjectName("main_grid_border_left")
            left_border.setGeometry(
                current_geom.x(), current_geom.y(), border_width, final_height
            )
            left_border.show()
            left_border.raise_()

            # RIGHT border
            right_border = BlackLineWidget(parent)
            right_border.setObjectName("main_grid_border_right")
            right_border.setGeometry(
                current_geom.x() + new_width - border_width,
                current_geom.y(),
                border_width,
                final_height,
            )
            right_border.show()
            right_border.raise_()

            logger.info(f" ✅ Grid extended: {new_height}px → {final_height}px (added {extra_height}px to fill gap)")
            logger.info(f"  ✅ Added 2px border around grid using BlackLineWidget (4 lines)")

            # Status bar is now IN .ui FILE with absolute geometry (y=715) - no positioning needed!
            logger.debug(f" 🎯 Status bar in .ui file at y=715, grid ends at y={current_geom.y() + final_height}")

        # Clear ALL input fields to ensure they're empty
        self._clear_all_input_fields()

    def _clear_all_input_fields(self) -> None:
        """Clear all QLineEdit and QTextEdit fields in the .ui to ensure they're empty"""
        if not hasattr(self, "ui"):
            return

        cleared = 0

        # Find and clear all QLineEdit widgets
        for line_edit in self.ui.findChildren(QLineEdit):
            line_edit.clear()
            cleared += 1

        # Find and clear all QTextEdit widgets
        for text_edit in self.ui.findChildren(QTextEdit):
            text_edit.clear()
            cleared += 1

    def _hide_old_ui_controls(self) -> None:
        """
        No old controls to delete - they were already removed from .ui file!

        The .ui file now contains ONLY:
        - main_grid_frame with rubrike 31-46 input fields
        - All old navigation buttons/labels/checkboxes were deleted from XML
        """
        if not hasattr(self, "ui"):
            return

        logger.info(f"  ✅ UI file is clean (no old controls to delete)")

    def _setup_package_dropdown(self) -> None:
        """
        Replace le_r31_vrsta QLineEdit with QComboBox for package type selection.
        Loads package codes from database (pakovanja table).
        Also enhances the le_r31_vrsta_naziv field for better visibility.
        """
        if not hasattr(self, "ui"):
            return

        # First, enhance the naziv field for better visibility
        le_naziv = self.ui.findChild(QLineEdit, "le_r31_vrsta_naziv")
        if le_naziv:
            # KRITIČNO: Postavi readOnly=False da bi setText() radio!
            le_naziv.setReadOnly(False)

            # KRITIČNO: Učini widget VIDLJIVIM!
            le_naziv.setVisible(True)
            le_naziv.show()

            # NE MENJAJ POZICIJU - ostavi kako je u .ui fajlu (x=250, width=295)!
            le_naziv.raise_()  # Postavi na vrh
            le_naziv.setEnabled(True)

            le_naziv.setStyleSheet(
                """
                QLineEdit {
                    background-color: #e3f2fd;
                    border: 2px solid #2196f3;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: bold;
                    font-size: 14px;
                    color: #1565c0;
                }
            """
            )
            le_naziv.setPlaceholderText("(auto)")

            # KRITIČNO: Podigni widget IZNAD combo box-a (z-order)
            le_naziv.raise_()

            logger.info(f" ✅ Enhanced le_r31_vrsta_naziv: readOnly=False, visible=True, using UI file geometry")

        # Find the existing QLineEdit for code
        old_widget = self.ui.findChild(QLineEdit, "le_r31_vrsta")
        if not old_widget:
            logger.warning("  ⚠️  le_r31_vrsta not found!")
            return

        # Get parent and geometry
        parent = old_widget.parent()
        geometry = old_widget.geometry()

        # Create QComboBox with wider width for better visibility
        self.combo_vrsta_pakovanja = QComboBox(parent)
        self.combo_vrsta_pakovanja.setObjectName(
            "le_r31_vrsta"
        )  # Keep same name for mapping
        # Increase width for better visibility
        geometry.setWidth(50)
        self.combo_vrsta_pakovanja.setGeometry(geometry)
        self.combo_vrsta_pakovanja.setEditable(True)  # Allow manual entry

        # Store package names for lookup
        self.package_names = {}  # {code: name}

        # Populate with package codes from database
        self.combo_vrsta_pakovanja.addItem("")  # Empty option
        self.package_names[""] = ""

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, opis FROM catalogs.pakovanja ORDER BY sifra")
                    rows = cur.fetchall()

            for r in rows:
                self.combo_vrsta_pakovanja.addItem(r["sifra"], r["sifra"])
                self.package_names[r["sifra"]] = r["opis"]

            logger.info(f"  ✅ Loaded {len(rows)} package codes from database")

        except Exception as e:
            logger.error(f"  ❌ Error loading package codes from database: {e}")
            # Ne propagiraj - tab se kreira sa praznim dropdown-om

        # Modern, professional style
        self.combo_vrsta_pakovanja.setStyleSheet(
            """
            QComboBox {
                border: 2px solid #28a745;
                border-radius: 6px;
                padding: 5px 15px;
                background-color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }

            QComboBox:hover {
                border: 2px solid #4a90e2;
            }

            QComboBox:focus {
                border: 2px solid #4a90e2;
                background-color: #f8faff;
            }

            QComboBox:editable {
                background-color: #ffffff;
            }

            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #28a745;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }

            /* Strelica nadole - CSS triangle */
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #666;
            }

            /* Stil za popup listu */
            QComboBox QAbstractItemView {
                border: 1px solid #4a90e2;
                selection-background-color: #4a90e2;
                selection-color: white;
                background-color: #ffffff;
                outline: 0px;
                border-radius: 6px;
                padding: 5px;
                font-size: 14px;
                min-width: 600px;
            }

            QComboBox QAbstractItemView::item {
                height: 30px;
                padding-left: 10px;
                border-radius: 4px;
                margin: 2px 5px;
            }

            QComboBox QAbstractItemView::item:hover {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
        """
        )

        # Replace widget
        old_widget.setParent(None)
        old_widget.deleteLater()

        # Connect signals - use MULTIPLE signals for reliable auto-fill
        self.combo_vrsta_pakovanja.currentTextChanged.connect(self._on_field_changed)
        self.combo_vrsta_pakovanja.currentTextChanged.connect(
            self._on_package_code_changed
        )
        # Also connect currentIndexChanged for dropdown selection
        self.combo_vrsta_pakovanja.currentIndexChanged.connect(
            lambda: self._on_package_code_changed(
                self.combo_vrsta_pakovanja.currentText()
            )
        )
        # KRITIČNO: Connect editingFinished for manual entry with Enter key
        self.combo_vrsta_pakovanja.lineEdit().editingFinished.connect(
            lambda: self._on_package_code_changed(
                self.combo_vrsta_pakovanja.currentText()
            )
        )

        # Onemogući autocomplete da ne prikazuje "CODE - Description" format
        self.combo_vrsta_pakovanja.setCompleter(None)

    def _on_package_code_changed(self, text: str) -> None:
        """
        Handle package code change - auto-populate package name field.
        """

        if self.is_loading:
            return

        # Extract code from combo (might be "PK" or just the code)
        code = text.strip()

        # Find the naziv field using cached access
        le_naziv = self._get_widget("le_r31_vrsta_naziv")

        if le_naziv:
            if hasattr(self, "package_names"):
                naziv = self.package_names.get(code, "")

                if naziv:
                    le_naziv.setText(naziv)

                # Also save to model
                if not self.is_loading and self.draft.items:
                    item = self.draft.items[self.current_item_index]
                    item.package_name = naziv

    def _on_package_selection_changed(self, index: int) -> None:
        """
        Handle package selection from dropdown - ensure only code is displayed.
        """
        if self.is_loading:
            return

        # Get the selected code from the combo box data
        code = self.combo_vrsta_pakovanja.currentData()
        if code:
            # Set only the code in the edit field
            self.combo_vrsta_pakovanja.setEditText(str(code))
            # Update the associated name field
            self._update_package_naziv(str(code))

    def _on_package_manual_entry(self) -> None:
        """
        Handle manual package entry - ensure only code is displayed.
        """
        if self.is_loading:
            return

        text = self.combo_vrsta_pakovanja.currentText()
        # Parse "PK - Description" → "PK" format if entered that way
        code = text.split(" - ")[0].strip() if " - " in text else text.strip()
        # Set only the code in the edit field
        self.combo_vrsta_pakovanja.setEditText(code)
        # Update the associated name field
        self._update_package_naziv(code)

    def _update_package_naziv(self, code: str) -> None:
        """
        Update the package name field based on the selected code.
        """
        if hasattr(self, "package_names") and code:
            le_naziv = self._get_widget("le_r31_vrsta_naziv")
            if le_naziv:
                naziv = self.package_names.get(code, "")
                le_naziv.setText(naziv)

                # Also save to model if we have items
                if (
                    not self.is_loading
                    and self.draft.items
                    and hasattr(self, "current_item_index")
                ):
                    item = self.draft.items[self.current_item_index]
                    item.package_name = naziv

    def _setup_trading_name_field(self) -> None:
        """
        Zamijeni le_r31_trg_naziv QLineEdit sa QTextEdit za multi-line prikaz.
        QTextEdit omogućava prikaz više linija teksta sa zalamanjem i scroll-om.
        """
        if not hasattr(self, "ui"):
            return

        # Pronađi postojeći QLineEdit
        old_widget = self.ui.findChild(QLineEdit, "le_r31_trg_naziv")
        if not old_widget:
            logger.warning("  ⚠️  le_r31_trg_naziv (QLineEdit) nije pronađen!")
            return

        # Dobij parent i geometriju
        parent = old_widget.parent()
        geometry = old_widget.geometry()

        logger.debug(f" 🔍 Pronađen le_r31_trg_naziv - pozicija: x={geometry.x()}, y={geometry.y()}, w={geometry.width()}, h={geometry.height()}")

        # Kreiraj QTextEdit na istom mjestu
        self.te_trg_naziv = QTextEdit(parent)
        self.te_trg_naziv.setObjectName("le_r31_trg_naziv")  # Zadrži isto ime
        self.te_trg_naziv.setGeometry(geometry)

        # Postavke za polje sa word wrap (sada omogućeno uređivanje)
        self.te_trg_naziv.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.te_trg_naziv.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.te_trg_naziv.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Postavi stylesheet - svijetlo plava pozadina, tekst počinje od vrha
        self.te_trg_naziv.setStyleSheet(
            """
            QTextEdit {
                background-color: #e3f2fd;
                border: 2px solid #2196f3;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
                font-weight: 600;
                color: #1565c0;
            }
        """
        )

        # Auto-expand: prilagodi visinu sadržaju (do dostupnog prostora u parent-u)
        # group_31 ima height=380, widget počinje na y=200 → max raspoloživo ~170px
        self._trg_naziv_min_h = geometry.height()  # originalna visina iz .ui (71px)
        self._trg_naziv_max_h = parent.height() - geometry.y() - 10  # do dna parent-a minus margina
        self.te_trg_naziv.document().contentsChanged.connect(self._adjust_trg_naziv_height)
        self.te_trg_naziv.textChanged.connect(self._check_trg_naziv_limit)

        # Podigni widget na vrh (z-order)
        self.te_trg_naziv.setVisible(True)
        self.te_trg_naziv.show()
        self.te_trg_naziv.raise_()

        # Ukloni stari widget
        old_widget.setParent(None)
        old_widget.deleteLater()

        logger.info(f" ✅ Zamijenjen le_r31_trg_naziv: QLineEdit → QTextEdit (auto-expand, multi-line)")

    _TRG_NAZIV_MAX = 280  # ASYCUDA Rb.31 limit za Description_of_goods

    def _check_trg_naziv_limit(self) -> None:
        """Rezervisano — limit od 280 karaktera primjenjuje se samo pri bildovanju XML-a."""
        pass

    def _adjust_trg_naziv_height(self) -> None:
        """Prilagodi visinu te_trg_naziv prema sadržaju (auto-expand do dna group_31)."""
        if not hasattr(self, "te_trg_naziv"):
            return
        doc_h = int(self.te_trg_naziv.document().size().height()) + 16  # +padding
        min_h = getattr(self, "_trg_naziv_min_h", 71)
        max_h = getattr(self, "_trg_naziv_max_h", 170)
        new_h = max(min_h, min(doc_h, max_h))
        geo = self.te_trg_naziv.geometry()
        if geo.height() != new_h:
            geo.setHeight(new_h)
            self.te_trg_naziv.setGeometry(geo)

    def _setup_rb40_widgets(self) -> None:
        """
        Zamijeni le_rubrika40_1 sa QComboBox (X/Y/Z) i
        le_rubrika40_2 sa editabilnim QComboBox iz baze (tabela prethodni_dokumenti).
        Redoslijed: [X/Y/Z] [Šifra dokumenta] [Prethodni dokument tekst]
        """
        from PySide6.QtCore import QRect

        if not hasattr(self, "ui"):
            return

        # ── Polje 40.1: X / Y / Z ───────────────────────────────────────────
        old1 = self.ui.findChild(QLineEdit, "le_rubrika40_1")
        if old1:
            parent1 = old1.parent()
            geom1 = old1.geometry()  # iz .ui: QRect(5, 28, 30, 25)
            old1.hide()
            old1.setParent(None)

            self.combo_rb40_tip = QComboBox(parent1)
            self.combo_rb40_tip.setObjectName("le_rubrika40_1")
            self.combo_rb40_tip.setEditable(False)
            self.combo_rb40_tip.addItems(["", "X", "Y", "Z"])
            # Globalni QSS ima "QComboBox { min-width: 100px }" koji overrideuje setFixedWidth.
            # Fix: widget-level stylesheet ima veći prioritet od QApplication stylesheet-a.
            FIELD1_W = 32
            self.combo_rb40_tip.setStyleSheet(
                f"QComboBox {{ min-width: {FIELD1_W}px; max-width: {FIELD1_W}px; }}"
            )
            self.combo_rb40_tip.setFixedWidth(FIELD1_W)
            self.combo_rb40_tip.setGeometry(
                QRect(geom1.x(), geom1.y(), FIELD1_W, geom1.height())
            )
            self.combo_rb40_tip.setToolTip(
                "X – Skraćena deklaracija\n"
                "Y – Prva deklaracija-pojednostavljena\n"
                "Z – Prethodni dokument"
            )
            self.combo_rb40_tip.show()
            self.widget_cache["le_rubrika40_1"] = self.combo_rb40_tip

            # Disconnect default handler first (signal možda nije bio konektovan)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    self.combo_rb40_tip.currentTextChanged.disconnect(
                        self._on_field_changed
                    )
                except Exception:
                    pass

            # currentIndexChanged: direktno snimanje u model (pouzdanije od activated)
            # Čuva se is_loading guardom da ne okine tokom učitavanja podataka
            self.combo_rb40_tip.currentIndexChanged.connect(
                self._on_rubrika40_1_index_changed
            )
            # activated ostaje za kompatibilnost (poziva puni _save_current_item)
            self.combo_rb40_tip.activated.connect(self._on_rubrika40_1_finished)
            logger.info("  ✅ le_rubrika40_1: QLineEdit → QComboBox (X/Y/Z)")
        else:
            logger.warning("  ⚠️  le_rubrika40_1 nije pronađen")

        # ── Učitaj šifre iz baze ─────────────────────────────────────────────
        skracenice_display = []
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT skracenica, vrsta_dokumenta FROM catalogs.prethodni_dokumenti ORDER BY skracenica")
                    rows = cur.fetchall()
            skracenice_display = [f"{r['skracenica']} – {r['vrsta_dokumenta']}" for r in rows]
            logger.info(f" ✅ Učitano {len(skracenice_display)} vrsta dok. iz baze (prethodni_dokumenti)")
        except Exception as e:
            logger.warning(f"  ⚠️  Greška pri učitavanju Rb.40 iz baze: {e}")

        # ── Polje 40.2: šifra dokumenta — zamijeni QLineEdit sa QComboBox ──────
        # Isti pattern kao IspravaDelegate u zaglavlje_tab:
        #   dropdown prikazuje "N380 – Faktura komercijalna"
        #   nakon odabira u polju ostaje samo šifra "N380" (usko polje)
        # Dodatno: pri otvaranju popup-a combo se vizuelno širi, pri zatvaranju sužava.

        class _ExpandCombo(QComboBox):
            """QComboBox koji se vizuelno širi pri otvaranju i sužava pri zatvaranju."""

            def __init__(self, parent, collapsed_w: int, expanded_w: int):
                super().__init__(parent)
                self._cw = collapsed_w
                self._ew = expanded_w

            def showPopup(self):
                g = self.geometry()
                self.setGeometry(g.x(), g.y(), self._ew, g.height())
                self.raise_()
                # Ako je u polju samo šifra, privremeno prikaži i naziv
                if self.lineEdit():
                    txt = self.lineEdit().text().strip()
                    if txt and " –" not in txt:
                        for i in range(self.count()):
                            if self.itemText(i).startswith(txt + " –"):
                                self.lineEdit().setText(self.itemText(i))
                                break
                super().showPopup()

            def hidePopup(self):
                super().hidePopup()
                g = self.geometry()
                self.setGeometry(g.x(), g.y(), self._cw, g.height())
                # Nakon zatvaranja ostavi samo šifru
                if self.lineEdit():
                    txt = self.lineEdit().text().strip()
                    if " –" in txt:
                        self.lineEdit().setText(txt.split(" –")[0].strip())

        old2 = self.ui.findChild(QLineEdit, "le_rubrika40_2")
        le3 = self.ui.findChild(QLineEdit, "le_rubrika40_3")
        if old2 and hasattr(self, "combo_rb40_tip"):
            parent2 = old2.parent()
            old2.hide()
            old2.setParent(None)

            # Izračunaj pozicije na osnovu stvarne geometrije field1
            g1 = self.combo_rb40_tip.geometry()
            GAP = 15  # vidljivi razmak između rubrika
            RIGHT_MARGIN = 5
            parent_w = parent2.geometry().width()

            # Field 2: usko polje za šifru — povećano za uštedu od field1
            # (FIELD1_W=32, originalna geom1.width()~39 → ~7px ušteđeno → prebačeno u w2)
            x2 = g1.x() + g1.width() + GAP
            w2 = 100  # suženo — prikazuje samo šifru "N380"
            h2 = g1.height()
            y2 = g1.y()

            # Proširena širina: od x2 do desnog ruba (za expand pri klikanju)
            expanded_w2 = max(parent_w - x2 - RIGHT_MARGIN, 280)

            logger.debug(f"  🔍 Rb.40 layout: parent_w={parent_w}, g1={g1}")
            logger.debug(f" 🔍 field2(šifra): x={x2}, w_collapsed={w2}, w_expanded={expanded_w2}")

            self.combo_rb40_skr = _ExpandCombo(parent2, w2, expanded_w2)
            self.combo_rb40_skr.setObjectName("le_rubrika40_2")
            self.combo_rb40_skr.setEditable(True)
            self.combo_rb40_skr.addItem("")
            self.combo_rb40_skr.addItems(skracenice_display)
            self.combo_rb40_skr.setGeometry(QRect(x2, y2, w2, h2))

            from PySide6.QtWidgets import QCompleter
            from PySide6.QtCore import Qt

            completer = QCompleter(skracenice_display, self.combo_rb40_skr)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.popup().setMinimumWidth(420)  # popup dovoljno širok za puni naziv
            self.combo_rb40_skr.setCompleter(completer)
            self.combo_rb40_skr.setPlaceholderText("Šifra")
            self.combo_rb40_skr.show()
            self.widget_cache["le_rubrika40_2"] = self.combo_rb40_skr
            self.combo_rb40_skr.currentTextChanged.connect(self._on_field_changed)

            def _on_skr_activated(idx, c=self.combo_rb40_skr):
                """Nakon odabira: polje prikazuje samo šifru, tooltip = puni naziv."""
                if idx > 0 and c.lineEdit():
                    full = c.itemText(idx)
                    kod = full.split(" –")[0].strip() if " –" in full else full
                    c.lineEdit().setToolTip(full)  # puni naziv u tooltip-u
                    from PySide6.QtCore import QTimer

                    def _set_kod(combo=c, code=kod):
                        if combo.lineEdit():
                            combo.setEditText(code)  # prikaži samo šifru u polju

                    QTimer.singleShot(0, _set_kod)

            self.combo_rb40_skr.activated.connect(_on_skr_activated)
            logger.info(f" ✅ le_rubrika40_2 _ExpandCombo kreiran (collapsed={w2}, expanded={expanded_w2})")
        else:
            logger.warning("  ⚠️  le_rubrika40_2 ili combo_rb40_tip nije pronađen")

        # ── Polje 40.3: referenca — puni preostali prostor do desnog ruba ─────
        if le3 and hasattr(self, "combo_rb40_skr"):
            parent3 = le3.parent()
            g2 = self.combo_rb40_skr.geometry()
            GAP = 15
            RIGHT_MARGIN = 5
            parent_w3 = parent3.geometry().width()
            x3_actual = g2.x() + g2.width() + GAP
            w3_actual = max(parent_w3 - x3_actual - RIGHT_MARGIN, 80)
            le3.setGeometry(QRect(x3_actual, g2.y(), w3_actual, g2.height()))
            le3.setPlaceholderText("Referenca / broj prethodnog dokumenta")
            le3.raise_()
            le3.show()
            logger.info(f"  ✅ le_rubrika40_3 referenca: {le3.geometry()}")
        elif le3:
            le3.setPlaceholderText("Referenca / broj prethodnog dokumenta")
            le3.raise_()
            le3.show()

    def _load_tariff_descriptions_sqlite(self, tariff_code: str) -> tuple[str, str]:
        """
        Učitaj opise tarife iz SQLite (uvijek dostupan, bez PostgreSQL).

        Returns:
            (full_description, short_description)
            full_description  → opis podbroja (8 cifara) → ide u te_r31_opis
            short_description → opis glave (4 cifre)    → ide u te_r31_opis_2
        """
        if not tariff_code:
            return "", ""
        try:
            from services.tariff.tarifa_service import trazi_po_kodu
            digits = "".join(filter(str.isdigit, str(tariff_code)))
            code8 = digits[:8]

            # Opis podbroja (8 cifara → lookup koji interno probava 10 cifara)
            result8 = trazi_po_kodu(code8)
            full = self._clean_tariff_description(result8['naziv']) if result8 else ""

            # Opis glave (4 cifre)
            code4 = digits[:4]
            result4 = trazi_po_kodu(code4) if code4 != code8 else None
            short = self._clean_tariff_description(result4['naziv']) if result4 else ""

            return full, short
        except Exception as e:
            logger.debug(f"SQLite tariff lookup greška: {e}")
            return "", ""

    def _load_tariff_description_from_db(self, tariff_code: str, nivo: str = "podbroj") -> str:
        """
        Učitaj opis tarife iz PostgreSQL catalogs.zvanicna_tarifa.

        nivo='podbroj' → te_r31_opis  (tačan opis podbroja, 8-10 cifara)
        nivo='glava'   → te_r31_opis_2 (heading opis, 4-6 cifara)

        Strategija:
          1. Tačan match po tarifni_kod + nivo
          2. Prefix fallback (kraći kod, isti nivo) ako tačan match ne postoji
        """
        if not tariff_code or not tariff_code.strip():
            return ""

        if not HAS_POSTGRESQL:
            logger.warning("⚠️ PostgreSQL nije dostupan za lookup tarife")
            return ""

        digits = "".join(filter(str.isdigit, str(tariff_code)))
        if not digits:
            return ""

        # Za glava lookup uvijek koristimo prvih 4 cifre
        if nivo == "glava":
            lookup_code = digits[:4]
        else:
            lookup_code = digits

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:

                    if nivo == "podbroj":
                        # Tačan match: 8-cifreni BiH kod + '00' = 10-cifreni PG zapis
                        candidates = [lookup_code]
                        if len(lookup_code) == 8:
                            candidates.append(lookup_code + "00")
                        elif len(lookup_code) < 10:
                            candidates.append(lookup_code.ljust(10, "0"))

                        result = None
                        for candidate in candidates:
                            cursor.execute(
                                """
                                SELECT tarifni_kod, opis
                                FROM catalogs.zvanicna_tarifa
                                WHERE tarifni_kod = %s AND nivo = 'podbroj'
                                LIMIT 1
                                """,
                                (candidate,),
                            )
                            result = cursor.fetchone()
                            if result:
                                break

                        # Progressivni prefix fallback: 8→7→6 cifara
                        # npr. 56074900 → LIKE '56074900%' (nema) → LIKE '5607490%' (nema)
                        #                → LIKE '560749%' (nađe 5607491100 ✓)
                        if not result:
                            for prefix_len in range(min(8, len(lookup_code)), 5, -1):
                                cursor.execute(
                                    """
                                    SELECT tarifni_kod, opis
                                    FROM catalogs.zvanicna_tarifa
                                    WHERE tarifni_kod LIKE %s || '%%'
                                      AND nivo = 'podbroj'
                                    ORDER BY tarifni_kod ASC
                                    LIMIT 1
                                    """,
                                    (lookup_code[:prefix_len],),
                                )
                                result = cursor.fetchone()
                                if result:
                                    break

                    else:
                        # Tražimo heading opis: prvo 4-cifreni 'glava', pa 6-cifreni 'podglava'
                        # Neke glave (npr. 1601) ne postoje na glava nivou nego samo kao podglava
                        cursor.execute(
                            """
                            SELECT tarifni_kod, opis
                            FROM catalogs.zvanicna_tarifa
                            WHERE tarifni_kod = %s AND nivo = 'glava'
                            LIMIT 1
                            """,
                            (lookup_code,),
                        )
                        result = cursor.fetchone()

                        if not result:
                            # Fallback: 6-cifreni podglava (npr. '160100' za '16010091')
                            digits_for_sub = "".join(filter(str.isdigit, str(tariff_code)))
                            subheading_code = digits_for_sub[:6] if len(digits_for_sub) >= 6 else digits_for_sub
                            cursor.execute(
                                """
                                SELECT tarifni_kod, opis
                                FROM catalogs.zvanicna_tarifa
                                WHERE tarifni_kod = %s AND nivo = 'podglava'
                                LIMIT 1
                                """,
                                (subheading_code,),
                            )
                            result = cursor.fetchone()

                    if result:
                        raw = result["opis"] or ""
                        cleaned = self._clean_tariff_description(raw)
                        logger.info(f"✅ Tariff [{nivo}] {result['tarifni_kod']} → {cleaned[:50]}")
                        return cleaned
                    else:
                        logger.warning(f"⚠️ Nema opisa tarife [{nivo}] za: {tariff_code}")
                        return ""

        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL greška pri lookup-u tarife: {e}")
            return ""

    def _extract_short_code(self, tariff_code: str) -> str:
        """
        Vrati 4-cifreni prefiks za traženje heading opisa (viši nivo klasifikacije).
        Primjer: "1601009100" → "1601", "1602421000" → "1602"
        """
        if not tariff_code:
            return ""
        digits = "".join(filter(str.isdigit, tariff_code))
        if len(digits) >= 4:
            return digits[:4]
        return digits

    def _clean_tariff_description(self, description: str) -> str:
        """
        Uklanja tehničke tarifne stope s kraja opisa.
        Primjeri:
          '– ostalo – 15 0 0 10,' → '– ostalo'
          '– – – – punjeni – 10+1KM/kg 0 0 6+1KM/kg 0 0 0 0' → '– – – – punjeni'
          '– – od domaće svinje – 10+3,5KM/kg 10+3,5KM/kg 0 ...' → '– – od domaće svinje'
        """
        if not description:
            return ""

        import re

        # Ukloni "ex NNNN NN NN NN" i sve iza toga (podtarifni izuzetak)
        cleaned = re.sub(r"\s*\bex\s+\d[\d\s]*.*$", "", description, flags=re.IGNORECASE)
        # Ukloni KM/kg stope: npr. "10+3,5KM/kg", "0+1,5KM/kg", "10+3KM/kg"
        cleaned = re.sub(
            r"\s+\d+(?:[+/]\d+(?:[,.]\d+)?)*[A-Z/%][A-Za-z/kg%]*.*$",
            "",
            cleaned,
        )
        # Ukloni sufiks sa 4+ prostorima odvojena broja (npr. "kd 0 0 0 0 5 5 5")
        cleaned = re.sub(r"(?:\s+\w{1,3})?(?:\s+\d+){4,}[\s,]*$", "", cleaned)
        # Ukloni trailing crtice i razmake (en-dash, em-dash, hyphen)
        cleaned = cleaned.rstrip(" \u2012\u2013\u2014-").strip()

        return cleaned if cleaned else description

    def _add_navigation_controls(self) -> None:
        """
        Add navigation controls matching the second screenshot design.
        """
        # Create navigation bar container - INCREASED HEIGHT
        self.nav_bar = QWidget()
        self.nav_bar.setObjectName(
            "navBar"
        )  # CSS styling in naimenovanja_components.qss
        self.nav_bar.setFixedHeight(50)  # Increased from 40 to 50

        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(12, 8, 12, 8)  # Increased vertical margins
        nav_layout.setSpacing(10)  # Increased spacing

        # Section 1: Dropdown selector
        lbl_nav = QLabel("Naimenovanje:")
        lbl_nav.setProperty("class", "nav-label")  # CSS in naimenovanja_components.qss
        nav_layout.addWidget(lbl_nav)

        self.combo_items = QComboBox()
        self.combo_items.setMinimumWidth(380)
        self.combo_items.setFixedHeight(34)
        self.combo_items.setMaxVisibleItems(99)
        self.combo_items.setStyleSheet("""
            QComboBox {
                font-size: 14px;
                font-weight: 600;
                padding: 4px 10px;
                border: 2px solid #4A7FA5;
                border-radius: 5px;
                background: white;
                color: #1a1a2e;
            }
            QComboBox:focus {
                border-color: #2563eb;
                background: #f0f7ff;
            }
            QComboBox::drop-down {
                width: 28px;
                border-left: 1px solid #4A7FA5;
            }
        """)
        self.combo_items.setProperty(
            "class", "nav-combo"
        )  # CSS in naimenovanja_components.qss
        self.combo_items.currentIndexChanged.connect(self._on_combo_changed)
        nav_layout.addWidget(self.combo_items)

        # Counter
        self.lbl_indicator = QLabel("1 od 1")
        self.lbl_indicator.setProperty(
            "class", "nav-counter"
        )  # CSS in naimenovanja_components.qss
        nav_layout.addWidget(self.lbl_indicator)

        # Separator
        nav_layout.addWidget(self._create_separator())

        # Section 2: Navigacija
        lbl_navigacija = QLabel("Navigacija:")
        lbl_navigacija.setProperty(
            "class", "nav-label"
        )  # CSS in naimenovanja_components.qss
        nav_layout.addWidget(lbl_navigacija)

        # Previous button
        self.btn_previous = self._create_icon_button("Prethodno", "fa5s.arrow-left")
        self.btn_previous.setObjectName(
            "btnPrethodno"
        )  # žuta/braon — navigacija unazad
        self.btn_previous.clicked.connect(self._on_previous)
        nav_layout.addWidget(self.btn_previous)

        # Next button
        self.btn_next = self._create_icon_button("Sljedeće", "fa5s.arrow-right")
        self.btn_next.setObjectName("btnSljedece")  # teal — navigacija naprijed
        self.btn_next.clicked.connect(self._on_next)
        nav_layout.addWidget(self.btn_next)

        # Separator
        nav_layout.addWidget(self._create_separator())

        # Section 3: CRUD buttons
        self.btn_add = self._create_icon_button("Dodaj", "fa5s.plus")
        self.btn_add.setObjectName("btnDodaj")  # zelena
        self.btn_add.clicked.connect(self._on_add_item)
        nav_layout.addWidget(self.btn_add)

        self.btn_delete = self._create_icon_button("Obriši", "fa5s.trash-alt")
        self.btn_delete.setObjectName("btnObrisi")  # crvena
        self.btn_delete.clicked.connect(self._on_delete_item)
        nav_layout.addWidget(self.btn_delete)

        # Separator
        nav_layout.addWidget(self._create_separator())

        # Section 4: Action buttons
        self.btn_suggest = self._create_icon_button("Sugeriši tarifu", "fa5s.lightbulb")
        self.btn_suggest.setObjectName("btnAutoPopuni")  # ljubičasta (AI)
        self.btn_suggest.clicked.connect(self._on_suggest_tariff)
        nav_layout.addWidget(self.btn_suggest)

        # Section 5: Import XML
        self.btn_import_xml = self._create_icon_button("Uvezi XML", "fa5s.file-import")
        self.btn_import_xml.setObjectName("btnUveziXMLNaim")  # teal/zelena
        self.btn_import_xml.setToolTip("Uvezi naimenovanja iz ASYCUDA XML fajla")
        self.btn_import_xml.clicked.connect(self._on_import_xml)
        nav_layout.addWidget(self.btn_import_xml)

        # Section 6: Inspekcije
        self.btn_inspekcije = self._create_icon_button("Inspekcije", "fa5s.clipboard-check")
        self.btn_inspekcije.setObjectName("btnInspekcije")
        self.btn_inspekcije.setToolTip("Pregled naimenovanja koja zahtijevaju inspekciju")
        self.btn_inspekcije.clicked.connect(self._on_inspekcije)
        nav_layout.addWidget(self.btn_inspekcije)

        # Spacer
        nav_layout.addStretch()

    def _add_section_heading(self) -> None:
        """Add section heading with integrated action buttons positioned above group_32_39"""
        self.section_heading = QWidget()
        self.section_heading.setObjectName(
            "sectionHeading"
        )  # CSS in naimenovanja_components.qss
        self.section_heading.setFixedHeight(32)

        heading_layout = QHBoxLayout(self.section_heading)
        heading_layout.setContentsMargins(20, 4, 20, 4)
        heading_layout.setSpacing(12)

        # Left: Heading label
        self.lbl_heading = QLabel("📋 Naimenovanje #1")
        self.lbl_heading.setProperty(
            "class", "section-heading-label"
        )  # CSS in naimenovanja_components.qss
        heading_layout.addWidget(self.lbl_heading)

        # Upozorenje o inspekcijskoj kontroli (skriveno dok nema kontrolisanog tarifnog broja)
        self.lbl_tariff_warning = QLabel()
        self.lbl_tariff_warning.setStyleSheet("""
            QLabel {
                background-color: #FF8C00;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 14px;
                padding: 2px 10px;
                border-radius: 4px;
                border: 1px solid #CC6600;
            }
        """)
        self.lbl_tariff_warning.setVisible(False)
        heading_layout.addWidget(self.lbl_tariff_warning)

        # Spacer to position buttons at 1257px from left edge
        heading_layout.addSpacing(1017)

        # Create a separate layout for action buttons to allow independent positioning
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)  # No margins around button layout
        button_layout.setSpacing(10)  # Space between buttons

        # Action buttons (Sačuvaj, Poništi) - positioned above group_32_39
        self.btn_sacuvaj = self._create_icon_button("Sačuvaj", "fa5.save")
        self.btn_sacuvaj.setObjectName("btnSnimi")  # zelena
        self.btn_sacuvaj.clicked.connect(self._on_save)
        self.btn_sacuvaj.raise_()  # Bring to front
        button_layout.addWidget(self.btn_sacuvaj)

        self.btn_ponisti = self._create_icon_button("Poništi", "fa5s.undo-alt")
        self.btn_ponisti.setObjectName("btnIzlaz")  # siva
        self.btn_ponisti.clicked.connect(self._on_ponisti)
        self.btn_ponisti.raise_()  # Bring to front
        button_layout.addWidget(self.btn_ponisti)

        # Add the button layout to the main heading layout
        heading_layout.addLayout(button_layout)

        # Right spacer
        heading_layout.addStretch()

    def _position_section_heading_buttons(self) -> None:
        """Place Save/Cancel buttons above group_32_39 using exact geometry (no layout guessing)."""
        if not hasattr(self, "ui") or not hasattr(self, "section_heading"):
            return

        group = self.ui.findChild(QGroupBox, "group_32_39")
        if not group or not group.isVisible():
            return

        # group x in coordinate system of 'self'
        gx_in_self = group.mapTo(self, QPoint(0, 0)).x()

        # convert to section_heading coordinates (safety; usually section_heading.x == 0)
        heading_x_in_self = self.section_heading.mapTo(self, QPoint(0, 0)).x()
        target_x = gx_in_self - heading_x_in_self

        # vertical center within heading bar
        y = (self.section_heading.height() - self.btn_sacuvaj.height()) // 2

        # small inner padding so it doesn't sit exactly on the border
        pad = 10

        self.btn_sacuvaj.move(target_x + pad, y)
        self.btn_ponisti.move(target_x + pad + self.btn_sacuvaj.width() + 12, y)

        # Debug (da vidiš da se X mijenja realno)
        # print(f"DEBUG: group_32_39.x(self)={gx_in_self}, heading.x(self)={heading_x_in_self}, target_x={target_x}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # keep buttons aligned even when window/tab resizes
        if hasattr(self, "section_heading") and hasattr(self, "btn_sacuvaj"):
            self._position_section_heading_buttons()

    def _add_status_bar(self) -> None:
        """Find status bar from .ui file (it's already there with absolute geometry!)"""
        if not hasattr(self, "ui"):
            return

        # Status bar is now IN THE .ui FILE with absolute geometry!
        self.status_bar = self.ui.findChild(QWidget, "status_bar_widget")

        if self.status_bar:
            # Find labels (they're already created in .ui file)
            self.lbl_status_total = self.ui.findChild(QLabel, "lbl_status_total")
            self.lbl_status_items = self.ui.findChild(QLabel, "lbl_status_items")
            self.lbl_status_bruto = self.ui.findChild(QLabel, "lbl_status_bruto")
            self.lbl_status_netto = self.ui.findChild(QLabel, "lbl_status_netto")
            self.lbl_status_validation = self.ui.findChild(
                QLabel, "lbl_status_validation"
            )

            # Add a message label for "apply to all" notifications
            # Use the validation label for temporary messages
            if hasattr(self, "lbl_status_validation"):
                self.lbl_status_message = self.lbl_status_validation

            logger.debug("  🎯 Grid ends at y=715, status bar at y=715 → GAP = 0px!")
        else:
            logger.warning("  ⚠️  Status bar widget not found in .ui file!")

    def _create_separator(self) -> QFrame:
        """Create vertical separator"""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedWidth(2)
        sep.setFixedHeight(30)
        return sep

    def _connect_field_signals(self) -> None:
        """Connect field change signals to auto-save"""
        if not hasattr(self, "ui"):
            return

        connected = 0

        for widget_name, field_name in self.field_map.items():
            if not field_name:  # Skip empty mappings
                continue

            widget = self._get_widget(widget_name)
            if widget:
                if isinstance(widget, QLineEdit):
                    widget.textChanged.connect(self._on_field_changed)
                    connected += 1
                elif isinstance(widget, QTextEdit):
                    widget.textChanged.connect(self._on_field_changed)
                    connected += 1

        # Broj paketa — samo cijeli brojevi
        le_broj = self._get_widget("le_r31_broj")
        if le_broj:
            from PySide6.QtGui import QIntValidator
            le_broj.setValidator(QIntValidator(0, 9999999, le_broj))

        # Rubrika 33: odspoji od batch-save timera (ne smije okidati dijalog pri kucanju)
        le_tariff = self._get_widget("le_rubrika33")
        if le_tariff:
            try:
                le_tariff.textChanged.disconnect(self._on_field_changed)
            except RuntimeError:
                pass
            # Lookup opisa dok korisnik kuca (bez dijaloga)
            le_tariff.textChanged.connect(self._on_tariff_changed)
            # Enter — eventFilter hvata Key_Return/Key_Enter direktno na widgetu
            le_tariff.installEventFilter(self)
            logger.debug(f"✅ eventFilter instaliran na le_rubrika33: {le_tariff.objectName()}")

    def _on_tariff_changed(self, text: str) -> None:
        """Debounced tariff lookup - query nakon 400ms pauze u kucanju"""
        if self.is_loading:
            return

        # Auto-popuni podbroj sa "000" ako je prazan i tarifni broj je unesen
        podbroj_widget = self._get_widget("le_rubrika33_podbroj")
        if podbroj_widget and not podbroj_widget.text().strip() and text.strip():
            podbroj_widget.setText("000")

        # Odmah vizualno obriši stare opise dok korisnik kuca novu tarifu
        te_opis = self._get_widget("te_r31_opis")
        te_opis_2 = self._get_widget("te_r31_opis_2")
        for w in (te_opis, te_opis_2):
            if w:
                w.setReadOnly(False)
                w.setText("")
                w.setReadOnly(True)
                w.setStyleSheet("")

        # Spremi pending kod u Qt property (spremanje stanja izmedju poziva)
        self.tariff_timer.setProperty("pending_code", text.strip())
        # Resetuj timer - ako korisnik kuca jos jedan karakter, countdown pocinje iznova
        self.tariff_timer.stop()
        self.tariff_timer.start(400)

    def _on_tariff_enter(self) -> None:
        """
        Korisnik je pritisnuo Enter u polju Rb.33.
        Sačuvaj tarifni broj i ponudi ažuriranje baze znanja.
        """
        if self.is_loading:
            return

        le_tariff = self._get_widget("le_rubrika33")
        new_tariff = (le_tariff.text().strip() if le_tariff else "")
        if not new_tariff:
            return

        self._save_current_item()
        self._auto_populate_supplementary_unit(new_tariff)
        # Uvijek ponudi KB update kad korisnik potvrdi Enter —
        # old_tariff može već biti jednak new_tariff zbog batch save, ali
        # korisnik svjesno pritiskuje Enter da potvrdi ovu tarifu
        self._ask_update_knowledge_base(new_tariff)

    # Mapiranje šifara iz carinske tarife → ASYCUDA kodovi za dopunsku JM
    _DOPUNSKA_JM_MAP = {
        'kd':   'NAR',   # komad
        'kom':  'NAR',
        'nar':  'NAR',
        'par':  'NAR',
        'l':    'LTR',   # litar
        'lit':  'LTR',
        'ltr':  'LTR',
        'm2':   'MTK',   # kvadratni metar
        'm²':   'MTK',
        'mtk':  'MTK',
        'm3':   'MTQ',   # kubni metar
        'm³':   'MTQ',
        'mtq':  'MTQ',
        'm':    'MTR',   # metar
        'mtr':  'MTR',
        'g':    'GRM',   # gram
        'grm':  'GRM',
        'kg':   'KGM',
        'kgm':  'KGM',
        'ce':   'CE',    # container
        'ct':   'CT',
    }

    def _auto_populate_supplementary_unit(self, tariff_code: str) -> None:
        """Auto-popuni Rb.41/43 ako tarifa propisuje dopunsku JM."""
        if not tariff_code or len(tariff_code) < 2:
            return

        le_code = self._get_widget("le_rubrika43")
        le_qty  = self._get_widget("le_rubrika41")
        if not le_code or not le_qty:
            return
        if le_code.text().strip():
            return  # korisnik je već unio

        # Lookup dopunske JM iz tarife
        unit_code = self._resolve_supplementary_unit(tariff_code)
        if not unit_code:
            return

        le_code.setText(unit_code)

        # Za KGM — auto-popuni neto masu iz Rb.38
        if unit_code == "KGM":
            le_neto = self._get_widget("le_rubrika38")
            neto_kg = 0.0
            if le_neto:
                try:
                    neto_kg = float(le_neto.text().replace(",", ".").strip())
                except (ValueError, AttributeError):
                    pass
            if neto_kg > 0:
                le_qty.setText(f"{neto_kg:.2f}")
        # Za NAR — uzmi broj iz le_r31_broj (Rb.31 — broj komada)
        elif unit_code == "NAR":
            le_broj = self._get_widget("le_r31_broj")
            if le_broj:
                try:
                    qty = float(le_broj.text().replace(",", ".").strip())
                    if qty > 0:
                        le_qty.setText(f"{qty:.0f}")
                except (ValueError, AttributeError):
                    pass

        self._save_current_item()

    def _resolve_supplementary_unit(self, tariff_code: str) -> str:
        """Vrati ASYCUDA kod dopunske JM za tarifni broj, ili '' ako ne postoji."""
        try:
            from services.naimenovanja.create_naimenovanja_service import get_supplementary_unit
            return get_supplementary_unit(tariff_code)
        except Exception:
            pass
        return ""

    def _ask_update_knowledge_base(self, new_tariff: str) -> None:
        """Pitaj korisnika da li želi ažurirati bazu znanja za ovaj proizvod."""
        item = self.draft.items[self.current_item_index] if self.draft.items else None
        if not item:
            return

        invoice_line = None
        line_idx = item.ordinal_no - 1
        if hasattr(self.draft, 'invoice_lines') and self.draft.invoice_lines:
            if 0 <= line_idx < len(self.draft.invoice_lines):
                invoice_line = self.draft.invoice_lines[line_idx]

        # Trgovački naziv — čitaj direktno iz te_r31_trg_naziv (ono što korisnik vidi)
        naziv_robe = ""
        trg_w = self._get_widget("le_r31_trg_naziv")
        if trg_w:
            try:
                naziv_robe = trg_w.toPlainText().strip()  # QTextEdit
            except AttributeError:
                naziv_robe = trg_w.text().strip()          # QLineEdit fallback
        if not naziv_robe:
            naziv_robe = (
                invoice_line.naziv_robe if invoice_line
                else (item.goods_description or item.goods_trade_name or "")
            )
        naziv_robe = naziv_robe.split("\n")[0][:100]  # samo prvi red, max 100 znakova

        msg = (
            f"Tarifni broj: <b>{new_tariff}</b><br><br>"
            f"Proizvod: <b>{naziv_robe}</b><br><br>"
            f"Ažurirati bazu znanja?<br>"
            f"<small>(Pri sljedećem uvozu ovaj artikal će automatski dobiti tarifu <b>{new_tariff}</b>)</small>"
        )

        reply = QMessageBox.question(
            self,
            "Ažuriranje baze znanja",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            try:
                # Učenje — docs/TARIFF_FACADE_REFACTORING.md
                from services.tariff_facade import TariffFacade
                product_code = invoice_line.product_code if invoice_line else ""
                zemlja = invoice_line.zemlja_porijekla if invoice_line else (item.origin_country_code or "")
                new_suffix = item.tariff_suffix or "000"

                # Obriši sve stare zapise za ovaj naziv/product_code sa drugom tarifom
                if naziv_robe:
                    from database.db import get_db_connection
                    with get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                DELETE FROM catalogs.product_tariff_mapping
                                WHERE (naziv_robe ILIKE %s OR product_code = %s)
                                  AND commodity_code != %s
                            """, (f"%{naziv_robe}%", product_code or "__NONE__", new_tariff))

                if naziv_robe and new_tariff:
                    TariffFacade.get_instance().learn(
                        product_code=product_code or "",
                        naziv_robe=naziv_robe,
                        tarifni_broj=new_tariff,
                        zemlja_porijekla=zemlja or "",
                        povlastica="",
                        precision_1=new_suffix,
                    )
                import logging
                logging.getLogger(__name__).info(
                    f"✅ KB ažuriran: '{naziv_robe[:40]}' → {new_tariff}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Greška", f"Nije moguće ažurirati bazu znanja:\n{e}")

    def _perform_tariff_lookup(self) -> None:
        """Izvrsi tariff lookup sa cache-om (poziva se nakon 400ms pauze).

        Popunjava dva nivoa opisa:
          - te_r31_opis   → 6-8 cifreni podbroj (precizni opis, npr. "847130")
          - te_r31_opis_2 → 4-cifreni heading (npr. "8471")
        Uvijek poziva _populate_tariff_description kako bi se polja očistila
        kada novi tarifni broj nije pronađen.
        """
        tariff_code = self.tariff_timer.property("pending_code")
        if not tariff_code or len(tariff_code.strip()) == 0:
            # Ako je polje prazno — obriši oba opisa
            self._populate_tariff_description("", "")
            return

        digits = "".join(filter(str.isdigit, tariff_code.strip()))

        # 4-cifreni heading (viši nivo)
        heading_code = digits[:4] if len(digits) >= 4 else digits

        # 6-cifreni subheading (srednji nivo, ako postoji dovoljno cifara)
        subheading_code = digits[:6] if len(digits) >= 6 else ""

        def _get_cached_or_lookup(code: str, nivo: str) -> str:
            cache_key = f"{nivo}:{code}"
            if cache_key in self.tariff_cache:
                return self.tariff_cache[cache_key]
            desc = self._load_tariff_description_from_db(code, nivo=nivo)
            if desc:
                self.tariff_cache[cache_key] = desc
            return desc

        # Tačan opis podbroja (10 cifara, sa fallback na kraće)
        full_description = _get_cached_or_lookup(digits, "podbroj") if digits else ""

        # Heading opis (4 cifre, nivo='glava')
        heading_description = _get_cached_or_lookup(heading_code, "glava") if heading_code else ""

        self._populate_tariff_description(full_description, heading_description)

        # tariff_description2 (heading) ide u le_r31_trg_naziv ako je prazno
        if heading_description:
            trg = self._get_widget("le_r31_trg_naziv")
            trg_empty = not (trg and (trg.toPlainText() if hasattr(trg, 'toPlainText') else trg.text()).strip())
            if trg_empty and hasattr(self, "te_trg_naziv"):
                trg_empty = not self.te_trg_naziv.toPlainText().strip()
            if trg_empty:
                if hasattr(self, "te_trg_naziv"):
                    self.te_trg_naziv.setPlainText(heading_description)
                item = self.draft.items[self.current_item_index] if self.draft.items else None
                if item:
                    item.goods_trade_name = heading_description

        # Provjeri inspekcijsku kontrolu za uneseni tarifni broj
        self._check_and_show_tariff_warning(tariff_code)

        # Automatski dodaj potrebne priložene dokumente u header_attached_documents
        self._add_tariff_control_docs(tariff_code)
        self._add_history_docs(tariff_code)

    def _add_history_docs(self, tariff_code: str) -> None:
        """Dodaj priložene dokumente iz istorije XML deklaracija za dati tarifni broj."""
        if not tariff_code or len(tariff_code.strip()) < 4:
            return
        header_docs = getattr(self.draft, "header_attached_documents", None)
        if header_docs is None:
            return
        try:
            from services.tariff_doc_history_service import get_tariff_doc_history_service
            svc = get_tariff_doc_history_service()
            suggestions = svc.get_suggested_docs(tariff_code, min_count=3)
        except Exception as e:
            logger.warning(f"Greška pri dohvatanju istorije dokumenata za {tariff_code}: {e}")
            return
        existing_codes = {d.code for d in header_docs}
        added = False
        from core.draft.draft import AttachedDocument
        for doc in suggestions:
            code = doc["code"]
            if code not in existing_codes:
                header_docs.append(AttachedDocument(
                    code=code,
                    name=doc["name"],
                    number="",
                    from_rule=False,
                ))
                existing_codes.add(code)
                added = True
                logger.info(f"  📚 Istorija: dodat {code} ({doc['name']}) za tarifu {tariff_code} (count={doc['count']})")
        if added:
            self.draft.mark_dirty()

    def _add_tariff_control_docs(self, tariff_code: str) -> None:
        """Automatski dodaj priložene dokumente u header_attached_documents
        na osnovu tarifnog broja (inspekcijske kontrole)."""
        if not tariff_code or len(tariff_code.strip()) < 2:
            return

        # Pronađi potrebne dokumente
        try:
            docs = get_required_docs(tariff_code)
        except Exception as e:
            logger.warning(f"Greška pri dohvatanju dokumenta za {tariff_code}: {e}")
            return

        if not docs:
            return

        # Dodaj u header_attached_documents
        header_docs = getattr(self.draft, "header_attached_documents", None)
        if header_docs is None:
            return

        added = False
        for doc in docs:
            code = doc["code"]
            # Provjeri da li već postoji
            exists = any(d.code == code for d in header_docs)
            if not exists:
                from core.draft.draft import AttachedDocument
                header_docs.append(AttachedDocument(
                    code=code,
                    name=doc["name"],
                    number="",  # prazno — korisnik treba da unese broj
                    from_rule=False,  # fizički priloženo
                ))
                added = True
                logger.info(f"  📄 Automatski dodat dokument {code} ({doc['name']}) za tarifu {tariff_code}")

        if added:
            self.draft.mark_dirty()

    def _check_and_show_tariff_warning(self, tariff_code: str) -> None:
        """Provjeri da li tarifni broj podlijeze inspekcijskoj kontroli i pokazi upozorenje."""
        if not hasattr(self, "lbl_tariff_warning"):
            return

        if not tariff_code or len(tariff_code.strip()) < 4:
            self.lbl_tariff_warning.setVisible(False)
            return

        try:
            result = check_tariff_controls(tariff_code)
        except Exception as e:
            logger.warning(f"Greška pri provjeri kontrola: {e}")
            self.lbl_tariff_warning.setVisible(False)
            return

        if result and result.ima_kontrolu:
            kontrole = result.skracenice
            self.lbl_tariff_warning.setText(f"⚠️  Kontrolisana roba: {kontrole}")
            self.lbl_tariff_warning.setToolTip(
                "Roba podlijeze inspekcijskoj kontroli:\n"
                + "\n".join(f"  • {k}" for k in result.opis_kontrola)
                + (f"\n\nNapomena: {result.napomena}" if result.napomena else "")
                + "\n\nIzvor: BiH UIO Objedinjen spisak inspekcijskih kontrola (mart 2015)"
            )
            self.lbl_tariff_warning.setVisible(True)
            logger.info(f"⚠️  Tarifni broj {tariff_code} podlijeze kontroli: {kontrole}")
        else:
            self.lbl_tariff_warning.setVisible(False)

    def _populate_tariff_description(
        self, description_full: str, description_short: str = ""
    ) -> None:
        """Popuni tariff description polja - sada popunjava trgovački naziv"""
        # Popuni polje za tačan opis podbroja (8-10 cifara) — te_r31_opis (gornje, editabilno)
        te_opis = self._get_widget("te_r31_opis")
        if te_opis:
            te_opis.setReadOnly(False)
            te_opis.setText(description_full)
            te_opis.setStyleSheet(
                """
                QLineEdit {
                    background-color: #e8f5e8;
                    border: 2px solid #4caf50;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: bold;
                    font-size: 14px;
                    color: #2e7d32;
                }
            """
            )

        # Popuni polje za heading opis (4-6 cifara) — te_r31_opis_2 (donje, plavo, editabilno)
        te_opis_2 = self._get_widget("te_r31_opis_2")
        if te_opis_2:
            te_opis_2.setReadOnly(False)
            te_opis_2.setText(description_short)
            te_opis_2.setStyleSheet(
                """
                QLineEdit {
                    background-color: #e3f2fd;
                    border: 2px solid #2196f3;
                    border-radius: 4px;
                    padding: 3px 6px;
                    font-weight: bold;
                    font-size: 14px;
                    color: #1565c0;
                }
            """
            )

        # Novo: Popuni trgovački naziv sa svim stavkama koje pripadaju naimenovanju
        if hasattr(self, "te_trg_naziv"):
            self.te_trg_naziv.clear()  # Obriši postojeći sadržaj
            # Formatuj sve nazive proizvoda iz fakture koji pripadaju ovom naimenovanju
            trading_names = self._format_trading_names()
            self.te_trg_naziv.setPlainText(
                trading_names
            )  # QTextEdit koristi setPlainText

    def _format_trading_names(self, max_chars: int = 280) -> str:
        # docs/sections/export-pdf-excel.md — dodaje footer sa Faktura: info
        """
        Formatuj sve nazive proizvoda iz fakture koji pripadaju trenutnom naimenovanju.
        Na dnu dodaje spisak faktura i rednih brojeva stavki koje ulaze u naimenovanje.

        Args:
            max_chars: Maksimalan broj karaktera — ASYCUDA Rb.31 limit je 280

        Returns:
            Nazivi proizvoda + na dnu "Faktura: broj (rb. x, y)" informacija
        """
        if len(self.draft.items) == 0:
            logger.warning("  ⚠️ _format_trading_names: Nema naimenovanja u draft.items")
            return ""

        # Get current naimenovanje ordinal
        current_item = self.draft.items[self.current_item_index]
        ordinal_no = current_item.ordinal_no

        # Filter invoice lines assigned to this naimenovanje
        assigned_lines = [
            line
            for line in self.draft.invoice_lines
            if line.assigned_naimenovanje_ordinal == ordinal_no
        ]

        if not assigned_lines:
            return ""

        # --- 1. Opis 4-cifrene glave (tariff_description2) ---
        tariff_heading = (current_item.tariff_description2 or "").strip()

        # --- 2. Nazivi proizvoda ---
        product_names = [line.naziv_robe for line in assigned_lines if line.naziv_robe]
        nazivi_dio = ", ".join(product_names) if product_names else ""

        # --- 3. Faktura info na dnu ---
        from collections import OrderedDict
        fakture: dict = OrderedDict()
        for line in assigned_lines:
            inv = line.invoice_number or "?"
            if inv not in fakture:
                fakture[inv] = []
            fakture[inv].append(str(line.line_no))

        fakture_dio_parts = []
        for inv, rb_list in fakture.items():
            fakture_dio_parts.append(f"{inv} (rb. {', '.join(rb_list)})")

        fakture_dio = "Faktura: " + ", ".join(fakture_dio_parts)

        # --- 4. Kombinuj: prioritet nazivi > faktura > heading ---
        # Fiksni dio: nazivi + faktura (uvijek se prikazuju puni)
        core_parts = [p for p in [nazivi_dio, fakture_dio] if p]
        core = ", ".join(core_parts)

        if tariff_heading:
            # Koliko prostora ostaje za heading (+ ", " separator)
            heading_budget = max_chars - len(core) - 2  # -2 za ", "
            if heading_budget >= len(tariff_heading):
                final_heading = tariff_heading
            elif heading_budget > 6:
                # Skrati heading, pokušaj na granici riječi
                cut = tariff_heading[:heading_budget - 3]
                last_space = cut.rfind(" ")
                final_heading = (cut[:last_space] if last_space > 0 else cut) + "..."
            else:
                final_heading = ""  # nema mjesta ni za skraćeni heading
            parts = [p for p in [final_heading, nazivi_dio, fakture_dio] if p]
        else:
            parts = core_parts

        result = ", ".join(parts)

        # Ako čak i bez headinga core > max_chars, skrati nazive
        if len(result) > max_chars:
            fakture_len = len(fakture_dio) + 2
            nazivi_max = max_chars - fakture_len - 3
            if nazivi_max > 20 and product_names:
                truncated_nazivi = nazivi_dio[:nazivi_max]
                last_comma = truncated_nazivi.rfind(", ")
                if last_comma > 0:
                    truncated_nazivi = truncated_nazivi[:last_comma]
                result = ", ".join([truncated_nazivi + "...", fakture_dio])
            else:
                result = result[:max_chars - 3] + "..."

        logger.debug(f"  📝 Ukupna dužina: {len(result)} karaktera")
        return result

    # ═══════════════════════════════════════════════════════════
    # DATA BINDING
    # ═══════════════════════════════════════════════════════════

    def _parse_cost(self, val) -> float:
        """Parse trošak iz stringa (podržava zarez i tačku kao decimalni separator)."""
        try:
            return float(str(val or 0).replace(",", ".").replace(" ", ""))
        except Exception:
            return 0.0

    def _compute_pd_codes(self) -> str:
        """Rb.44 P.D. — šifre from_rule priloženih dokumenata iz zaglavlja (N380 DIS DV1)."""
        header_docs = getattr(self.draft, "header_attached_documents", []) or []
        codes = [doc.code for doc in header_docs if getattr(doc, "from_rule", False) and doc.code]
        return " ".join(codes)

    def _compute_statistical_value(self, item) -> str:
        """Rb.46 — statistička vrijednost: (item_value_EUR × kurs) + ext_freight_BAM."""
        item_value = float(item.item_value or 0)
        total_items_value = sum(float(it.item_value or 0) for it in self.draft.items)
        if total_items_value <= 0 or item_value <= 0:
            return ""
        kurs = float(self.draft.kurs or 1.0) or 1.0
        alpha = item_value / total_items_value
        t1 = self._parse_cost(getattr(self.draft, "trosak_1", 0))
        ext_freight = t1 * alpha
        stat_val = round(item_value * kurs, 2) + ext_freight
        return f"{stat_val:.2f}"

    def _load_current_item(self) -> None:
        """Load current item from draft into form fields"""
        if len(self.draft.items) == 0 or not hasattr(self, "ui"):
            return

        # Sakrij upozorenje pri svakom prelasku na novi item (ažurira se u _perform_tariff_lookup)
        if hasattr(self, "lbl_tariff_warning"):
            self.lbl_tariff_warning.setVisible(False)

        self.is_loading = True
        item = self.draft.items[self.current_item_index]

        loaded = 0
        not_found = 0

        for widget_name, field_name in self.field_map.items():
            if not field_name:
                continue

            # Use cached widget access
            widget = self._get_widget(widget_name)

            if widget:
                # Virtuelna polja — dinamički izračun, ne čitaju se iz drafta
                if field_name == "statistical_value":
                    value = self._compute_statistical_value(item)
                elif field_name == "pd_codes":
                    value = self._compute_pd_codes()
                else:
                    value = getattr(item, field_name, "")

                if isinstance(widget, QComboBox):
                    if value:
                        # Special handling for rubrika40_2 - show only code
                        if widget_name == "le_rubrika40_2":
                            value_str = str(value)
                            # Extract only code if full text "CODE – Description" is saved
                            code = (
                                value_str.split(" –")[0].strip()
                                if " –" in value_str
                                else value_str
                            )
                            # Find matching item by code
                            found_idx = -1
                            for i in range(widget.count()):
                                item_txt = widget.itemText(i)
                                item_code = (
                                    item_txt.split(" –")[0].strip()
                                    if " –" in item_txt
                                    else item_txt
                                )
                                if item_code == code:
                                    found_idx = i
                                    break
                            if found_idx >= 0:
                                widget.setCurrentIndex(found_idx)
                                full_tooltip = widget.itemText(found_idx)
                                if widget.lineEdit():
                                    widget.lineEdit().setToolTip(full_tooltip)
                            # Always show only code in the field (not full text)
                            widget.setEditText(code)
                        else:
                            # Standard handling for other combos
                            index = widget.findText(str(value))
                            if index >= 0:
                                widget.setCurrentIndex(index)
                            else:
                                # Fallback: set current text directly
                                widget.setCurrentText(str(value))
                    else:
                        widget.setCurrentIndex(0)
                    loaded += 1
                elif isinstance(widget, QLineEdit):
                    # Broj paketa — cijeli broj
                    if field_name == "package_qty":
                        if value and float(value) != 0:
                            widget.setText(str(int(float(value))))
                        else:
                            widget.setText("")
                    # Format float fields to 2 decimal places
                    elif field_name in [
                        "gross_mass_kg",
                        "net_mass_kg",
                        "item_value",
                        "statistical_value",
                        "supplementary_unit_qty",
                    ]:
                        # Format as float with 2 decimals, but only if value is not empty/zero
                        if value and float(value) != 0:
                            widget.setText(f"{float(value):.2f}")
                        else:
                            widget.setText("")
                    else:
                        widget.setText(str(value) if value else "")
                    # FORCE: osiguraj da je vidljiv (QUiLoader bug)
                    if not widget.isVisible():
                        widget.setVisible(True)
                    loaded += 1
                elif isinstance(widget, QTextEdit):
                    widget.setPlainText(str(value) if value else "")
                    # FORCE: osiguraj da je vidljiv (QUiLoader bug)
                    if not widget.isVisible():
                        widget.setVisible(True)
                    loaded += 1
            else:
                not_found += 1

        # FORCE: osiguraj da je main_grid_frame vidljiv
        if hasattr(self, "ui") and self.ui:
            grid = self.ui.findChild(QFrame, "main_grid_frame")
            if grid and not grid.isVisible():
                grid.setVisible(True)
            # FORCE: postavi direktni stylesheet na main_grid_frame (QUiLoader bug workaround)
            if grid:
                grid.setStyleSheet("QFrame#main_grid_frame { background-color: #f0f0f0; border: 1px solid #999; }")

        # Rb.40: Z i N821 combosi vidljivi samo za prvo naimenovanje
        is_first_item = (self.current_item_index == 0)
        rb40_1 = self._get_widget("le_rubrika40_1")
        rb40_2 = self._get_widget("le_rubrika40_2")
        if rb40_1:
            rb40_1.setVisible(is_first_item)
        if rb40_2:
            rb40_2.setVisible(is_first_item)

        # Automatski dodaj priložene dokumente na osnovu tarifnog broja
        if item and item.tariff_code:
            self._add_tariff_control_docs(item.tariff_code)

        self.is_loading = False

        # KRITIČNO: Auto-popuni naziv pakovanja NAKON učitavanja podataka
        # Ovo mora biti NAKON is_loading=False da bi se naziv zaista postavio
        if hasattr(self, "combo_vrsta_pakovanja"):
            package_code = self.combo_vrsta_pakovanja.currentText().strip()
            if package_code and hasattr(self, "package_names"):
                le_naziv = self._get_widget("le_r31_vrsta_naziv")
                if le_naziv:
                    naziv = self.package_names.get(package_code, "")
                    le_naziv.setText(naziv)

                    # DETALJNA DIJAGNOSTIKA
                    logger.debug(f"  🔍 WIDGET DIAGNOSTICS:")
                    logger.debug(f"     - text(): '{le_naziv.text()}'")
                    logger.debug(f"     - isVisible(): {le_naziv.isVisible()}")
                    logger.debug(f"     - isEnabled(): {le_naziv.isEnabled()}")
                    logger.debug(f"     - isReadOnly(): {le_naziv.isReadOnly()}")
                    logger.debug(f"     - geometry(): {le_naziv.geometry()}")
                    logger.debug(f"     - styleSheet(): {le_naziv.styleSheet()}")
                    logger.debug(f"     - font(): {le_naziv.font().toString()}")

        # KRITIČNO: Ako postoji tariff_code, pozovi lookup za opis tarife
        if item.tariff_code:
            logger.debug(f"  🔍 Tariff code found in model: {item.tariff_code}")
            # Primarno: SQLite (uvijek dostupan); fallback: PostgreSQL
            full_description, short_description = self._load_tariff_descriptions_sqlite(item.tariff_code)

            # Fallback na PostgreSQL ako SQLite nije vratio ništa
            if not full_description and not short_description:
                full_description = self._load_tariff_description_from_db(item.tariff_code, nivo="podbroj")
                short_code = self._extract_short_code(item.tariff_code)
                if short_code and short_code != item.tariff_code:
                    short_description = self._load_tariff_description_from_db(short_code, nivo="glava")

            if full_description or short_description:
                self._populate_tariff_description(full_description or "", short_description or "")
                # Sačuvaj u draft da ne mora svaki put raditi lookup
                item.tariff_description1 = full_description or ""
                item.tariff_description2 = short_description or ""
                # tariff_description2 (heading) ide u le_r31_trg_naziv ako je prazno
                if short_description and not (item.goods_trade_name or "").strip():
                    item.goods_trade_name = short_description
            else:
                logger.warning(f"  ⚠️  No tariff description found for code: {item.tariff_code}")
        # Auto-popuni Rb.41 ako tarifa zahtjeva i polje je prazno
        if item.tariff_code and not (item.supplementary_unit_code or "").strip():
            self._auto_populate_supplementary_unit(item.tariff_code)

        # Auto-popuni trgovački naziv sa svim stavkama iz fakture
        # (ima prioritet nad tariff_description2 ako postoje faktura linije)
        if hasattr(self, "te_trg_naziv"):
            trading_names = self._format_trading_names()
            if trading_names:
                self.te_trg_naziv.setPlainText(trading_names)
            elif item.goods_trade_name:
                self.te_trg_naziv.setPlainText(item.goods_trade_name)

    def _save_current_item(self) -> None:
        """Save form data to current item in draft"""
        if self.is_loading or len(self.draft.items) == 0 or not hasattr(self, "ui"):
            return

        item = self.draft.items[self.current_item_index]

        # Zapamtimo stari tarifni broj prije izmjene (za sinhronizaciju)
        old_tariff = item.tariff_code or ""
        old_suffix = item.tariff_suffix or "000"

        # Virtualna polja (auto-izračun) — ne čuvaju se u draftu
        _READONLY_VIRTUAL_FIELDS = {"statistical_value", "pd_codes"}

        for widget_name, field_name in self.field_map.items():
            if not field_name or field_name in _READONLY_VIRTUAL_FIELDS:
                continue

            # Use cached widget access
            widget = self._get_widget(widget_name)

            if widget:
                value = None

                if isinstance(widget, QComboBox):
                    # For QComboBox, use currentText() to get selected value
                    value = widget.currentText().strip()
                elif isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                elif isinstance(widget, QTextEdit):
                    value = widget.toPlainText().strip()

                # Type conversion
                if field_name == "package_qty":
                    try:
                        value = int(float(value)) if value else 0
                    except ValueError:
                        value = 0
                elif field_name in [
                    "gross_mass_kg",
                    "net_mass_kg",
                    "item_value",
                    "statistical_value",
                    "supplementary_unit_qty",
                ]:
                    try:
                        value = float(value) if value else 0.0
                    except ValueError:
                        value = 0.0
                elif field_name == "ordinal_no":
                    try:
                        value = int(value) if value else 0
                    except ValueError:
                        value = 0
                elif field_name == "tariff_code" and value:
                    # Normalizuj "ex" unose: "ex 8511 80 00 10" → "8511800010"
                    # 10 cifara s posljednjim 2 = "00" → skrati na 8; ≠ "00" → čuvaj 10
                    _d = re.sub(r"\D", "", value)
                    if len(_d) > 10:
                        _d = _d[:10]
                    if len(_d) == 10 and _d[8:] == "00":
                        _d = _d[:8]
                    value = _d

                setattr(item, field_name, value)

        self.draft.mark_dirty()
        if self.on_dirty:
            self.on_dirty()

        # ── Sinhronizacija tarifnog broja ako je promijenjen ──────────────
        new_tariff = item.tariff_code or ""
        new_suffix = item.tariff_suffix or "000"
        if new_tariff and (new_tariff != old_tariff or new_suffix != old_suffix):
            self._sync_tariff_to_source(old_tariff, old_suffix, new_tariff, new_suffix, item)

    def _sync_tariff_to_source(
        self, old_tariff: str, old_suffix: str,
        new_tariff: str, new_suffix: str,
        naim_item,
    ) -> None:
        """
        Sinhronizacija promjene tarifnog broja na 3 mjesta:
        1. InvoiceLine (source iz PDF-a) — tarifni_broj + tariff_suffix
        2. Baza znanja (product_tariff_mapping) — commodity_code + precision_1
        3. Log obavijest korisniku

        Pokreće se samo kad korisnik RUČNO promijeni tarif u Naimenovanja tabu.
        """
        import logging
        log = logging.getLogger(__name__)

        # ── 1. Pronađi izvornu InvoiceLine ────────────────────────────────
        invoice_line = None
        # Za 1:1 mapiranje: ordinal_no = index + 1
        line_idx = naim_item.ordinal_no - 1
        if hasattr(self.draft, 'invoice_lines') and self.draft.invoice_lines:
            if 0 <= line_idx < len(self.draft.invoice_lines):
                invoice_line = self.draft.invoice_lines[line_idx]

        # Ako nismo našli po indexu, probaj po nazivu robe (za grupisane)
        if invoice_line is None:
            naziv = naim_item.goods_description or naim_item.goods_trade_name or ""
            if naziv:
                for line in self.draft.invoice_lines:
                    if (line.naziv_robe or "").lower() == naziv.lower():
                        invoice_line = line
                        break

        # ── 2. Ažuriraj InvoiceLine ───────────────────────────────────────
        if invoice_line:
            old_line_tariff = invoice_line.tarifni_broj or ""
            invoice_line.tarifni_broj = new_tariff
            invoice_line.tariff_suffix = new_suffix
            if old_line_tariff and old_line_tariff != new_tariff:
                log.info(
                    f"🔄 Tariff sync: InvoiceLine '{invoice_line.naziv_robe[:40]}' "
                    f"{old_line_tariff} → {new_tariff}/{new_suffix}"
                )

        # ── 3. Ažuriraj bazu znanja ───────────────────────────────────────
        product_code = invoice_line.product_code if invoice_line else ""
        naziv_robe = (
            invoice_line.naziv_robe if invoice_line
            else (naim_item.goods_description or naim_item.goods_trade_name or "")
        )
        zemlja = invoice_line.zemlja_porijekla if invoice_line else naim_item.origin_country_code

        try:
            # Učenje — docs/TARIFF_FACADE_REFACTORING.md
            from services.tariff_facade import TariffFacade

            # Prvo izbriši STARE zapise sa pogrešnom tarifom (isti naziv ili product_code)
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM catalogs.product_tariff_mapping
                        WHERE (naziv_robe ILIKE %s OR product_code = %s)
                          AND commodity_code = %s
                    """, (f"%{naziv_robe}%", product_code or "__NONE__", old_tariff))
                    deleted = cursor.rowcount

            # Zatim sačuvaj novi tarif
            if naziv_robe and new_tariff:
                TariffFacade.get_instance().learn(
                    product_code=product_code or "",
                    naziv_robe=naziv_robe,
                    tarifni_broj=new_tariff,
                    zemlja_porijekla=zemlja or "",
                    povlastica="",
                    precision_1=new_suffix,
                )
                log.info(
                    f"✅ KB sync: '{naziv_robe[:40]}' → {new_tariff}/{new_suffix} "
                    f"({deleted} starih zapisa obrisano)"
                )

        except Exception as e:
            log.warning(f"⚠️ Tariff KB sync failed for '{naziv_robe[:40]}': {e}")

        # Obavijest se prikazuje samo iz _ask_update_knowledge_base (na Enter)
        pass

    def _update_all_ui(self) -> None:
        """Update all UI elements"""
        self._update_combo()
        self._update_summary()
        self._update_navigation_buttons()
        self._update_heading()
        self._update_status_bar()

    def _update_combo(self) -> None:
        """Update dropdown combobox - ALWAYS show tariff code"""
        self.is_loading = True
        self.combo_items.clear()

        for i, item in enumerate(self.draft.items):
            # Format: "#1 - 84713000" (always show tariff, even if empty)
            tariff = item.tariff_code if item.tariff_code else ""
            label = f"#{item.ordinal_no} - {tariff}"
            self.combo_items.addItem(label)

        self.combo_items.setCurrentIndex(self.current_item_index)
        self.lbl_indicator.setText(
            f"{self.current_item_index + 1} od {len(self.draft.items)}"
        )

        self.is_loading = False

    def _update_summary(self) -> None:
        """Ažurira status bar (summary panel je uklonjen)."""
        self._update_status_bar()

    def _update_navigation_buttons(self) -> None:
        """Update button states"""
        self.btn_previous.setEnabled(self.current_item_index > 0)
        self.btn_next.setEnabled(self.current_item_index < len(self.draft.items) - 1)
        self.btn_delete.setEnabled(len(self.draft.items) > 1)

    def _update_heading(self) -> None:
        """Update section heading"""
        if hasattr(self, "lbl_heading") and len(self.draft.items) > 0:
            item = self.draft.items[self.current_item_index]
            self.lbl_heading.setText(f"📋 Naimenovanje #{item.ordinal_no}")

    def _update_status_bar(self) -> None:
        """Update status bar with summary metrics - redoslijed: Ukupno, Broj komada, Bruto, Neto, Validacija"""
        if not hasattr(self, "lbl_status_total"):
            return

        # Ukupna cijena
        total = sum(item.item_value or 0 for item in self.draft.items)
        currency = self.draft.items[0].currency if self.draft.items else "EUR"
        self.lbl_status_total.setText(f"💰 Ukupno: {total:,.2f} {currency}")

        # Ukupan broj komada (suma količina svih naimenovanja)
        total_qty = sum(item.package_qty or 0 for item in self.draft.items)
        self.lbl_status_items.setText(f"📦 Broj komada: {total_qty:,.0f}")

        # Ukupna bruto masa
        bruto = sum(item.gross_mass_kg or 0 for item in self.draft.items)
        self.lbl_status_bruto.setText(f"⚖️ Bruto: {bruto:.2f} kg")

        # Ukupna neto masa
        netto = sum(item.net_mass_kg or 0 for item in self.draft.items)
        self.lbl_status_netto.setText(f"📊 Netto: {netto:.2f} kg")

        # Validacija statusa
        errors = self._validate_all_items()
        if errors:
            msg = " · ".join(errors[:3])
            if len(errors) > 3:
                msg += f" (+{len(errors) - 3})"
            self.lbl_status_validation.setText(f"⚠️ {msg}")
            self.lbl_status_validation.setStyleSheet(
                "color: #856404; background: #fff3cd; padding: 2px 6px; border-radius: 3px;"
            )
        else:
            self.lbl_status_validation.setText("✅ Sva naimenovanja kompletna")
            self.lbl_status_validation.setStyleSheet(
                "color: #155724; background: #d4edda; padding: 2px 6px; border-radius: 3px;"
            )

    def _sync_header_packages(self) -> None:
        """Calculate total package quantity across all items and write it to
        draft.uk_paketa so that Zaglavlje tab (rub.6) stays in sync.

        This method should be called whenever item quantities change or when
        items are added/deleted. It formats the value as an integer string.
        """
        total_qty = sum(item.package_qty or 0 for item in self.draft.items)
        # store as plain integer string (no decimal point)
        self.draft.uk_paketa = f"{int(total_qty)}"

    # ════════���════════════════����════════════════════════════════��
    # EVENT HANDLERS
    # ════════════���════════════���═══════════════════════════════��═

    def _on_combo_changed(self, index: int) -> None:
        """Dropdown selection changed"""
        if not self.is_loading and index >= 0:
            self._navigate_to_item(index)

    def _on_previous(self) -> None:
        """Previous button clicked"""
        if self.current_item_index > 0:
            self._navigate_to_item(self.current_item_index - 1)

    def _on_next(self) -> None:
        """Next button clicked"""
        if self.current_item_index < len(self.draft.items) - 1:
            self._navigate_to_item(self.current_item_index + 1)

    def _navigate_to_item(self, index: int) -> None:
        """Navigate to specific item"""
        self._save_current_item()
        self.current_item_index = index
        self._load_current_item()
        self._update_all_ui()

    def _on_add_item(self) -> None:
        """Add new naimenovanje"""
        logger.debug("  ➕ Adding item...")
        self._save_current_item()

        new_item = self.draft.add_item()
        new_item.ordinal_no = len(self.draft.items)

        self._navigate_to_item(len(self.draft.items) - 1)

        # Focus first field (tariff code)
        if hasattr(self, "ui"):
            first_field = self._get_widget("le_rubrika33")
            if first_field:
                first_field.setFocus()

    def _on_delete_item(self) -> None:
        """Delete current naimenovanje"""
        if len(self.draft.items) <= 1:
            QMessageBox.warning(
                self, "Greška", "Mora postojati bar jedno naimenovanje!"
            )
            return

        reply = QMessageBox.question(
            self,
            "Potvrda",
            f"Obrisati naimenovanje #{self.current_item_index + 1}?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            del self.draft.items[self.current_item_index]

            if self.current_item_index >= len(self.draft.items):
                self.current_item_index = len(self.draft.items) - 1

            # Renumber
            for i, item in enumerate(self.draft.items):
                item.ordinal_no = i + 1

            self.draft.mark_dirty()
            if self.on_dirty:
                self.on_dirty()

            self._load_current_item()
            self._update_all_ui()

    def _on_save(self) -> None:
        """Save button clicked"""
        self._save_current_item()
        QMessageBox.information(self, "Uspjeh", "✅ Naimenovanje sačuvano!")

    def _on_field_changed(self) -> None:
        """Debounced field change handler - spašava nakon 300ms pauze u kucanju"""
        if not self.is_loading:
            # Zaustavi prethodni timer (resetuj countdown)
            self.save_timer.stop()
            # Pokreni novi timer - ako korisnik kuca jos jedan karakter prije 300ms, timer se resetuje
            self.save_timer.start(300)

    def _on_rubrika40_1_index_changed(self, idx: int) -> None:
        """Master polje: primijeni X/Y/Z tip na SYA naimenovanja.
        Isto ponašanje kao rb40_2 i rb40_3 — korisnik bira jednom, važi za sve.
        is_loading guard sprječava lažno snimanje tokom učitavanja."""
        if self.is_loading:
            return
        if not self.draft.items:
            return
        text = self.combo_rb40_tip.currentText().strip()
        for item in self.draft.items:
            item.previous_document = text
        self.draft.mark_dirty()
        if self.on_dirty:
            self.on_dirty()

    def _on_rubrika40_1_finished(self, idx: int = 0) -> None:
        """Poziva puni _save_current_item() on activated (za ostale rubrike 40 i bočne efekte)."""
        if self.is_loading:
            return
        self._save_current_item()
        self._update_status_bar()

    def _batch_save_fields(self) -> None:
        """Batch spašavanje nakon pauze u kucanju (300ms bez aktivnosti)"""
        if not self.is_loading and len(self.draft.items) > 0:
            self._save_current_item()
            self._update_summary()
            # Opcionalno: log za dijagnostiku
            # print(f"✅ Batch saved after 300ms pause (item #{self.current_item_index + 1})")

    def _setup_apply_to_all_indicators(self) -> None:
        """
        Setup visual indicators for "apply to all" master fields.
        Adds tooltips and persistent border styling to indicate these fields apply to all items.
        """
        if not hasattr(self, "ui"):
            return

        # Find the special fields
        # le_rubrika40_2 je QComboBox (šifra dokumenta) — master polje
        le_rubrika40_2 = self._get_widget("le_rubrika40_2")
        le_rubrika44_4 = self.ui.findChild(QLineEdit, "le_rubrika44_4")

        # Master field style
        master_combo_style = """
            QComboBox {
                border: 2px solid #17a2b8;
                border-radius: 3px;
                padding: 2px 4px;
                background-color: #f0f9ff;
                color: #333;
            }
            QComboBox:focus {
                border: 2px solid #138496;
                background-color: white;
                color: #333;
            }
            QComboBox QLineEdit {
                color: #333;
                background-color: transparent;
            }
        """
        master_field_style = """
            QLineEdit {
                border: 2px solid #17a2b8;
                border-radius: 3px;
                padding: 4px;
                background-color: #f0f9ff;
                color: #333;
            }
            QLineEdit:focus {
                border: 2px solid #138496;
                background-color: white;
                color: #333;
            }
        """

        # Configure rubrika 40.1 (X/Y/Z tip – master polje)
        # Čuvamo min/max-width iz _setup_rb40_widgets, samo dodajemo master boju
        if hasattr(self, "combo_rb40_tip"):
            self.combo_rb40_tip.setToolTip(
                "🔗 MASTER POLJE\n\n"
                "Vrijednost se automatski primjenjuje na sva naimenovanja.\n"
                "Rubrika 40.1 - Tip dokumenta (X/Y/Z)"
            )
            FIELD1_W = 32
            self.combo_rb40_tip.setStyleSheet(
                f"QComboBox {{ min-width: {FIELD1_W}px; max-width: {FIELD1_W}px; "
                f"border: 2px solid #17a2b8; border-radius: 3px; background-color: #f0f9ff; color: #333; }}"
            )

        # Configure rubrika 40.2 (šifra – master polje)
        if le_rubrika40_2 and isinstance(le_rubrika40_2, QComboBox):
            le_rubrika40_2.setToolTip(
                "🔗 MASTER POLJE\n\n"
                "Vrijednost se automatski primjenjuje na sva naimenovanja.\n"
                "Rubrika 40.2 - Šifra dokumenta"
            )
            le_rubrika40_2.setStyleSheet(master_combo_style)

        # Configure rubrika 44.4
        if le_rubrika44_4:
            le_rubrika44_4.setToolTip(
                "🔗 MASTER POLJE\n\n"
                "Vrijednost se automatski primjenjuje na sva naimenovanja.\n"
                "Rubrika 44.4 - Priložena isprava"
            )
            le_rubrika44_4.setStyleSheet(master_field_style)
            le_rubrika44_4.setPlaceholderText(
                "🔗 Master polje - primjenjuje se na sve..."
            )

        # Configure rubrika 40.3 - Referenca dokumenta
        le_rubrika40_3 = self._get_widget("le_rubrika40_3")
        if le_rubrika40_3:
            le_rubrika40_3.setToolTip(
                "🔗 MASTER POLJE\n\n"
                "Vrijednost se automatski primjenjuje na sva naimenovanja.\n"
                "Rubrika 40.3 - Referenca dokumenta"
            )
            le_rubrika40_3.setStyleSheet(master_field_style)
            le_rubrika40_3.setPlaceholderText(
                "🔗 Master polje - primjenjuje se na sve..."
            )

    def _setup_tab_order(self) -> None:
        """Postavi logički redosljed Tab/Shift+Tab navigacije između polja."""
        from PySide6.QtWidgets import QWidget
        if not hasattr(self, "ui"):
            return

        def w(name: str):
            cached = self.widget_cache.get(name)
            if cached is not None:
                return cached
            return self.ui.findChild(QWidget, name)

        # Redosljed polja: od Rb.31 do Rb.44/45/46
        order = [
            # Rb.31 — Pakovanje i opis
            w("le_r31_oznake_br"),
            w("le_r31_paketa"),
            w("le_r31_broj"),
            w("le_r31_vrsta"),
            w("le_r31_vrsta_naziv"),
            w("te_r31_opis"),
            w("te_r31_opis_2"),
            w("le_r31_trg_naziv"),
            # Rb.33/34/35/36/37/38/39
            w("le_rubrika33"),
            w("le_rubrika33_podbroj"),
            w("le_rubrika34_zemlja"),
            w("le_rubrika34_regija"),
            w("le_rubrika35"),
            w("le_rubrika36"),
            w("le_rubrika37_1"),
            w("le_rubrika37_2"),
            w("le_rubrika38"),
            w("le_rubrika39"),
            # Rb.40 — Prethodni dokument
            w("le_rubrika40_1"),   # X/Y/Z combo
            w("le_rubrika40_2"),   # šifra dokumenta combo
            w("le_rubrika40_3"),   # broj
            # Rb.41/42/43
            w("le_rubrika41"),
            w("le_rubrika42"),
            w("le_rubrika43"),
            # Rb.44
            w("le_rubrika44_3"),
            w("le_rubrika44_4"),
            w("le_rubrika44_5"),
            # Rb.45/46
            w("le_rubrika45_sifra"),
            w("le_rubrika45_iznos"),
            w("le_rubrika46"),
        ]

        # Filtriraj None (widget ne postoji) i postavi tab order
        valid = [wgt for wgt in order if wgt is not None]
        for i in range(len(valid) - 1):
            QWidget.setTabOrder(valid[i], valid[i + 1])

    def _connect_special_field_signals(self) -> None:
        """
        Connect special field signals for "apply to all" functionality.
        These fields apply their value to ALL items in the draft.
        """
        logger.debug(f"🔍 DIAG SPECIAL: _connect_special_field_signals pozvan, hasattr(ui)={hasattr(self, 'ui')}")
        if not hasattr(self, "ui"):
            logger.debug(f"🔍 DIAG SPECIAL: nema ui, return")
            return

        # Find the special fields using cached access
        # le_rubrika40_2 je QComboBox šifara — master polje
        le_rubrika40_2 = self._get_widget("le_rubrika40_2")
        le_rubrika40_3 = self._get_widget("le_rubrika40_3")
        le_rubrika44_4 = self._get_widget("le_rubrika44_4")
        logger.debug(f"🔍 DIAG SPECIAL: le_rubrika40_3={le_rubrika40_3}, le_rubrika44_4={le_rubrika44_4}")
        logger.debug(f"🔍 DIAG SPECIAL: ui postoji? {hasattr(self, 'ui')}")

        if le_rubrika40_2 and isinstance(le_rubrika40_2, QComboBox):
            # Disconnect default handler first
            try:
                le_rubrika40_2.currentTextChanged.disconnect(self._on_field_changed)
            except Exception:
                pass
            le_rubrika40_2.currentTextChanged.connect(self._on_rubrika40_2_finished)
            logger.info("  ✅ Connected rubrika40_2 'apply to all' signal")

        if le_rubrika40_3:
            # Rubrika 40.3 - Referenca dokumenta - primeni na sva ostala naimenovanja
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    le_rubrika40_3.editingFinished.disconnect(self._on_rubrika40_3_finished)
                except Exception:
                    pass
            le_rubrika40_3.editingFinished.connect(self._on_rubrika40_3_finished)
            logger.info("  ✅ Connected rubrika40_3 'apply to all' signal")

        if le_rubrika44_4:
            # Disconnect default handler first
            try:
                le_rubrika44_4.textChanged.disconnect(self._on_field_changed)
            except:
                pass
            # Connect to special handler using editingFinished instead of textChanged
            le_rubrika44_4.editingFinished.connect(self._on_rubrika44_4_finished)

    def _on_rubrika40_2_finished(self) -> None:
        """Primijeni šifru dokumenta (rubrika40_2) na sve iteme."""
        if self.is_loading:
            return

        le_rubrika40_2 = self._get_widget("le_rubrika40_2")
        if not le_rubrika40_2:
            return

        text = (
            le_rubrika40_2.currentText().strip()
            if isinstance(le_rubrika40_2, QComboBox)
            else ""
        )

        # 1. Sacuvaj trenutni item
        self._save_current_item()

        # 2. Primijeni na sve ostale iteme
        if len(self.draft.items) > 1:
            for i, item in enumerate(self.draft.items):
                if i != self.current_item_index:
                    item.previous_document2 = text

        # 3. Azuriraj summary i validaciju
        self._update_summary()
        self._update_status_bar()

    def _on_rubrika44_4_finished(self) -> None:
        """Primijeni rubrika44_4 na sve iteme NAKON zavrsetka uredivanja (Enter/blur).

        Automatski dodaje PE1/PE2/PE3 u header_attached_documents
        radi prikaza u tabeli priloženih dokumenata u zaglavlju.
        Vidi docs/sections/pe-rub44-4.md
        """
        if self.is_loading:
            return

        le_rubrika44_4 = self._get_widget("le_rubrika44_4")
        if not le_rubrika44_4:
            return

        text = le_rubrika44_4.text().strip()

        # 1. Sacuvaj trenutni item
        self._save_current_item()

        # 2. Primijeni na sve ostale iteme
        if len(self.draft.items) > 1:
            for i, item in enumerate(self.draft.items):
                if i != self.current_item_index:
                    item.attached_document4 = text

        # 3. Sinhronizuj PE šifre iz rub.44.4 u header_attached_documents
        self._sync_pe_docs_to_header()

        # 4. Azuriraj summary
        self._update_summary()

    def _sync_pe_docs_to_header(self) -> None:
        """Sinhronizuj PE1/PE2/PE3 dokumente iz naimenovanja u header_attached_documents.

        Čita attached_document4 sa svih naimenovanja, parsira format "ŠIFRA broj",
        i dodaje AttachedDocument(code=ŠIFRA, number=broj) u draft.header_attached_documents.
        Stari PE unosi se uklanjaju i zamjenjuju aktuelnim.
        """
        header_docs = getattr(self.draft, "header_attached_documents", None)
        if header_docs is None:
            return

        # 1. Sakupi sve jedinstvene (sifra, broj) parove iz svih naimenovanja
        pe_entries: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in self.draft.items:
            doc4 = (getattr(item, 'attached_document4', '') or '').strip()
            if not doc4:
                continue
            # Format: "ŠIFRA broj" (npr. "PE1 12345", "PE2 INV-001")
            parts = doc4.split(' ', 1)
            sifra = parts[0].strip()
            broj = parts[1].strip() if len(parts) > 1 else ''
            if sifra in ("PE1", "PE2", "PE3"):
                key = (sifra, broj)
                if key not in seen:
                    seen.add(key)
                    pe_entries.append(key)

        # 2. Ukloni postojeće PE1/PE2/PE3 unose iz header_attached_documents
        header_docs[:] = [d for d in header_docs if d.code not in ("PE1", "PE2", "PE3")]

        # 3. Dodaj nove unose
        if pe_entries:
            from core.draft.draft import AttachedDocument
            for sifra, broj in pe_entries:
                # Mapiraj šifru u naziv dokumenta
                naziv_map = {
                    "PE1": "EUR.1 obrazac",
                    "PE2": "Izjava na fakturi",
                    "PE3": "Izjava ovlaštenog izvoznika",
                }
                naziv = naziv_map.get(sifra, f"Dokument {sifra}")
                header_docs.append(AttachedDocument(
                    code=sifra,
                    name=naziv,
                    number=broj,
                    from_rule=sifra == "PE1",  # EUR.1 je fizički priložen
                ))

            # Obavijesti zaglavlje da se podaci promijenili
            self.draft.mark_dirty()

    def _on_rubrika40_3_finished(self) -> None:
        """Primijeni referencu dokumenta (rubrika40_3) na sve iteme.
        
        Automatski dodaje OST u header_attached_documents — vidi docs/sections/ost-rb40.md
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"🔍 DIAG: _on_rubrika40_3_finished POZVAN, is_loading={self.is_loading}")

        if self.is_loading:
            return

        le_rubrika40_3 = self._get_widget("le_rubrika40_3")
        if not le_rubrika40_3:
            logger.debug(f"🔍 DIAG: le_rubrika40_3 widget nije pronađen!")
            return

        text = le_rubrika40_3.text().strip()
        logger.debug(f"🔍 DIAG: text='{text}', draft.header_attached_documents postoji? {hasattr(self.draft, 'header_attached_documents')}")

        # 1. Sacuvaj trenutni item
        self._save_current_item()

        # 2. Primijeni na sve ostale iteme
        if len(self.draft.items) > 1:
            for i, item in enumerate(self.draft.items):
                if i != self.current_item_index:
                    item.previous_document3 = text

        # 3. Azuriraj OST (ostali prateći dokument) u header_attached_documents
        #    da bi se prikazao u zaglavlju u tabeli priloženih dokumenata
        if text:
            header_docs = getattr(self.draft, "header_attached_documents", None)
            logger.debug(f"🔍 DIAG: header_docs={header_docs}")
            if header_docs is not None:
                ost = next((d for d in header_docs if d.code == "OST"), None)
                logger.debug(f"🔍 DIAG: postojeci OST={ost}")
                if ost:
                    ost.number = text
                    logger.debug(f"🔍 DIAG: OST azuriran: number={text}")
                else:
                    from core.draft.draft import AttachedDocument
                    header_docs.append(AttachedDocument(
                        code="OST",
                        name="Ostali prateći dokumenti",
                        number=text,
                        from_rule=False,
                    ))
                    logger.debug(f"🔍 DIAG: OST DODAT: code=OST, number={text}")
                # Obavijesti zaglavlje da se podaci promijenili
                logger.debug(f"🔍 DIAG: pozivam draft.mark_dirty()")
                self.draft.mark_dirty()
            else:
                logger.debug(f"🔍 DIAG: header_docs je None!")
        else:
            logger.debug(f"🔍 DIAG: text je prazan, preskacem OST")

        # 4. Azuriraj summary i validaciju
        self._update_summary()
        self._update_status_bar()

    def _flash_field_border(self, widget: QWidget, color: str = "#28a745") -> None:
        """
        Flash a colored border on a widget for visual feedback.
        Uses QTimer to animate the border appearance and disappearance.
        For master fields (with cyan border), restores the master field style after flash.

        Args:
            widget: The widget to flash
            color: Border color (default: green #28a745)
        """
        # Store original stylesheet
        original_style = widget.styleSheet()

        # Check if this is a master field (has cyan border)
        is_master_field = "17a2b8" in original_style or "138496" in original_style

        # Apply flash border
        flash_style = f"""
            QLineEdit {{
                border: 3px solid {color};
                background-color: rgba(40, 167, 69, 0.1);
                border-radius: 3px;
                padding: 4px;
            }}
        """
        widget.setStyleSheet(flash_style)

        # Restore original style after 500ms
        if is_master_field:
            # For master fields, restore the cyan border style
            master_field_style = """
                QLineEdit {
                    border: 2px solid #17a2b8;
                    border-radius: 3px;
                    padding: 4px;
                    background-color: #f0f9ff;
                    color: #333;
                }
                QLineEdit:focus {
                    border: 2px solid #138496;
                    background-color: white;
                    color: #333;
                }
            """
            QTimer.singleShot(500, lambda: widget.setStyleSheet(master_field_style))
        else:
            # For regular fields, restore original style
            QTimer.singleShot(500, lambda: widget.setStyleSheet(original_style))

    def _on_suggest_tariff(self) -> None:
        """Pokreni sugestiju tarifnog broja direktno (view implementacija)."""
        self._suggest_tariff_impl()

    def _on_import_xml(self) -> None:
        """Otvori file dialog i uvezi naimenovanja iz XML fajla."""
        import traceback
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        try:
            filename, _ = QFileDialog.getOpenFileName(
                self,
                "Uvezi naimenovanja iz XML fajla",
                "",
                "XML Files (*.xml);;All Files (*)",
            )
            if not filename:
                return

            # 1. Parsiraj naimenovanja iz XML
            from services.zaglavlje_service import ZaglavljeService
            svc = ZaglavljeService()
            items = svc.parse_naimenovanja_from_xml(filename)

            if not items:
                self.show_warning(
                    "XML fajl ne sadrži naimenovanja (Item sekcije).\n\n"
                    "Provjerite da li je XML u ASYCUDA World ili Pro formatu."
                )
                return

            # 2. Potvrda
            reply = QMessageBox.question(
                self,
                "Uvoz naimenovanja",
                f"Pronađeno {len(items)} naimenovanja u XML fajlu.\n\n"
                f"Ovo će zamijeniti trenutna naimenovanja.\n"
                f"Da li želite nastaviti?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

            # 3. Zamijeni draft.items
            self.draft.items = items
            self.draft.mark_dirty()

            # 4. Resetuj na prvu stavku i reload
            self.current_item_index = 0
            self.reload_data()

            self.show_success(
                f"✅ Uvezeno {len(items)} naimenovanja iz XML-a.\n"
                f"Kliknite 'Sačuvaj' da potvrdite promjene."
            )

        except Exception as e:
            logger.error(f"Greška pri uvozu XML naimenovanja: {e}", exc_info=True)
            self.show_error(f"Greška pri uvozu: {e}")

        # Emituj signal za controller (ako postoji)
        self.import_xml_requested.emit(filename)

    def _on_inspekcije(self) -> None:
        """Otvori dijalog sa inspekcijskim pregledom naimenovanja."""
        try:
            dlg = InspectionDialog(self.draft, parent=self)
            dlg.exec()
        except Exception as e:
            logger.error(f"Greška pri otvaranju inspekcijskog dijaloga: {e}")
            self.show_error(f"Greška pri otvaranju inspekcijskog pregleda:\n{e}")

    def _suggest_tariff_impl(self) -> None:
        """
        Sugeriši tarifni broj za trenutno selektovano naimenovanje.

        Koristi TariffService za pronalaženje top 3 prijedloga
        baziranih na nazivu robe i zemlji porijekla.

        Edge Cases:
        - EC1: Naziv robe prazan
        - EC2: Naziv previše generički
        - EC3: Nema nijednog matcha
        - EC4: Score ispod praga
        - EC8: Validacija tarife
        """
        # Edge Case 1: Nema stavki
        if not self.draft.items:
            QMessageBox.warning(
                self,
                "Sugeriši tarifu",
                "❌ Nema naimenovanja.\n\n💡 Prvo kreirajte naimenovanje.",
            )
            return

        # Sačuvaj trenutne vrijednosti iz UI u draft prije pretrage
        # (korisnik možda nije napustio polje, pa draft nije ažuriran)
        self._save_current_item()

        current_item = self.draft.items[self.current_item_index]

        logger.debug(f"[suggest] goods_trade_name={current_item.goods_trade_name!r}")

        # Edge Case 1: Naziv robe prazan
        if (
            not current_item.goods_trade_name
            or current_item.goods_trade_name.strip() == ""
        ):
            QMessageBox.warning(
                self,
                "Sugeriši tarifu",
                "❌ Naziv robe nije unesen.\n\n"
                "💡 Prvo popunite Rubriku 31 (Trgovački naziv).",
            )
            return

        naziv_lower = current_item.goods_trade_name.strip().lower()

        # Edge Case 2: Naziv previše generički (stop words)
        STOP_WORDS = {
            "goods",
            "material",
            "item",
            "items",
            "parts",
            "product",
            "products",
            "roba",
            "materijal",
            "proizvod",
            "proizvodi",
            "artikal",
            "artikli",
            "stuff",
            "thing",
            "things",
            "misc",
            "miscellaneous",
            "other",
            "various",
        }

        if naziv_lower in STOP_WORDS:
            QMessageBox.warning(
                self,
                "Sugeriši tarifu",
                f"❌ Naziv robe je previše opšti za automatsku sugestiju.\n\n"
                f'Naziv: "{current_item.goods_trade_name}"\n\n'
                "💡 Unesite precizniji opis proizvoda.",
            )
            return

        # Edge Case 2: Naziv previše kratak
        if len(naziv_lower) < 5:
            QMessageBox.warning(
                self,
                "Sugeriši tarifu",
                f"❌ Naziv robe je previše kratak za automatsku sugestiju.\n\n"
                f'Naziv: "{current_item.goods_trade_name}" ({len(naziv_lower)} karaktera)\n\n'
                "💡 Unesite detaljniji opis proizvoda (minimum 5 karaktera).",
            )
            return

        # Pokušaj pronaći top 3 prijedloga koristeći TariffService
        try:
            service = TariffService(self)

            logger.debug(f"\n🔍 Tražim prijedloge za:")
            logger.debug(f"   Naziv: {current_item.goods_trade_name[:60]}...")
            logger.debug(f"   Zemlja: {current_item.origin_country_code or 'N/A'}")

            mappings = service.suggest_tariff(
                goods_trade_name=current_item.goods_trade_name,
                origin_country_code=current_item.origin_country_code or "",
            )

            # Edge Case 3: Nema match-eva
            if not mappings or len(mappings) == 0:
                QMessageBox.information(
                    self,
                    "Sugeriši tarifu",
                    "❌ Nije pronađen prijedlog za ovaj proizvod.\n\n"
                    "💡 Savjet: Nakon ručnog unosa, sistem će zapamtiti\n"
                    "   ovaj proizvod za buduće deklaracije.",
                )
                logger.error("   ❌ Nema match-eva")
                return

            # Edge Case 4: Najbolji score ispod praga
            if mappings[0].similarity < NaimenovanjaConstants.MIN_SIMILARITY_THRESHOLD:
                QMessageBox.information(
                    self,
                    "Sugeriši tarifu",
                    f"⚠️  Pronađeni prijedlozi imaju nisku pouzdanost.\n\n"
                    f"Najbolji match: {mappings[0].similarity:.0%}\n"
                    f"Minimalni prag: {NaimenovanjaConstants.MIN_SIMILARITY_THRESHOLD:.0%}\n\n"
                    "💡 Savjet: Koristite ručnu pretragu ili detaljniji naziv.",
                )
                logger.warning(f" ⚠️ Score {mappings[0].similarity:.0%} < prag {NaimenovanjaConstants.MIN_SIMILARITY_THRESHOLD:.0%}")
                return

            logger.info(f"   ✅ Pronađeno {len(mappings)} prijedloga:")
            for i, m in enumerate(mappings, 1):
                logger.debug(f" {i}. {m.tarifni_broj} (match: {m.similarity:.0%}, korišćeno: {m.usage_count}×)")

            # Edge Case 8: Validacija tarifnih brojeva
            valid_mappings = self._validate_mappings(mappings)

            if not valid_mappings:
                QMessageBox.warning(
                    self,
                    "Sugeriši tarifu",
                    "❌ Pronađeni prijedlozi nisu validni prema zvaničnoj tarifi.\n\n"
                    "💡 Koristite ručnu pretragu.",
                )
                logger.error("   ❌ Nijedan prijedlog nije validan")
                return

            # Prikaži dialog sa prijedlozima
            self._show_tariff_suggestion_dialog(valid_mappings, current_item)

        except Exception as e:
            import traceback

            traceback.print_exc()

            QMessageBox.critical(
                self,
                "Greška",
                f"❌ Greška pri traženju prijedloga:\n\n{str(e)}\n\n"
                "Provjerite konzolu za detalje.",
            )

    def _validate_mappings(
        self, mappings: List["TariffMapping"]
    ) -> List["TariffMapping"]:
        """
        Validira tarifne brojeve iz prijedloga.

        Edge Case 8: Konflikt sa validacijom tarife

        Args:
            mappings: Lista TariffMapping objekata

        Returns:
            Lista validnih TariffMapping objekata
        """
        from database.db import get_tarifa_opis

        valid_mappings = []

        for mapping in mappings:
            # Provjeri da li postoji u zvaničnoj tarifi
            try:
                opis = get_tarifa_opis(mapping.tarifni_broj)

                if opis:  # Postoji u tarifi
                    valid_mappings.append(mapping)
                    logger.info(f"      ✅ {mapping.tarifni_broj} je validan")
                else:
                    logger.warning(f" ⚠️ {mapping.tarifni_broj} ne postoji u zvaničnoj tarifi")

            except Exception as e:
                logger.error(f"      ❌ Greška pri validaciji {mapping.tarifni_broj}: {e}")

        return valid_mappings

    def _show_tariff_suggestion_dialog(
        self, mappings: List["TariffMapping"], current_item: "NaimenovanjeDraft"
    ) -> None:
        """
        Prikaži dialog sa prijedlozima tarifnih brojeva.

        Args:
            mappings: Lista validnih TariffMapping objekata
            current_item: Trenutno naimenovanje
        """
        from gui.dialogs.tariff_suggestion_dialog import TariffSuggestionDialog

        dialog = TariffSuggestionDialog(mappings, current_item, self)

        # Connect signal za prihvaćeni prijedlog
        dialog.suggestion_accepted.connect(self._on_tariff_suggestion_accepted)

        # Connect signal za ručnu pretragu
        dialog.manual_search_requested.connect(self._on_manual_tariff_search)

        self._active_suggestion_dialog = dialog
        dialog.exec()
        self._active_suggestion_dialog = None

    def _on_tariff_suggestion_accepted(self, result: dict) -> None:
        """
        Korisnik prihvatio prijedlog tarifnog broja.

        Args:
            result: Dictionary sa {tarifni_broj, povlastica, zemlja_porijekla, similarity, usage_count}
        """
        logger.debug(f"\n{'=' * 70}")
        logger.debug(f"🎯 _on_tariff_suggestion_accepted() POZVANA!")
        logger.debug(f"   Result: {result}")
        logger.debug(f"{'=' * 70}")

        current_item = self.draft.items[self.current_item_index]

        logger.info(f"\n✅ Prijedlog prihvaćen:")
        logger.debug(f"   Tarifni broj: {result.get('tarifni_broj')}")
        logger.debug(f"   Povlastica: {result.get('povlastica')}")
        logger.debug(f"   Zemlja: {result.get('zemlja_porijekla')}")
        logger.debug(f"   Similarity: {result.get('similarity'):.0%}")

        # Track original value za Edge Case 7 (ručna izmjena nakon prihvatanja)
        self._auto_filled_tariff = result.get("tarifni_broj")

        # Primijeni tarifni broj
        if result.get("tarifni_broj"):
            current_item.tariff_code = result["tarifni_broj"]

        # Primijeni zemlju porijekla (opciono)
        if result.get("zemlja_porijekla"):
            current_item.origin_country_code = result["zemlja_porijekla"]

        # Primijeni povlasticu — validiraj kombinaciju zemlja+povlastica
        if result.get("povlastica"):
            zemlja = current_item.origin_country_code or result.get(
                "zemlja_porijekla", ""
            )
            valid_pref = validate_preference(zemlja, result["povlastica"])
            if valid_pref:
                current_item.preference_code = valid_pref
            elif result["povlastica"]:
                logger.warning(f"⚠️ Povlastica {result['povlastica']!r} odbijena za zemlju {zemlja!r}")

        # Reload trenutni item u GUI
        self._load_current_item()

        logger.debug(f"📝 Podaci učitani u form")

        # Mark as dirty
        self.data_changed.emit()
        if self.on_dirty:
            self.on_dirty()

        # Inkrementiraj usage_count — docs/TARIFF_FACADE_REFACTORING.md
        try:
            from services.tariff_facade import TariffFacade
            TariffFacade.get_instance().increment_usage(
                result["tarifni_broj"],
                None,
                current_item.goods_trade_name,
            )
        except Exception as e:
            logger.warning(f"⚠️  Greška pri ažuriranju usage_count: {e}")

        QMessageBox.information(
            self,
            "Uspjeh",
            f"✅ Tarifni broj prihvaćen!\n\n"
            f"Tarifni broj: {result['tarifni_broj']}\n"
            f"Pouzdanost: {result['similarity']:.0%}",
        )

    def _on_manual_tariff_search(self) -> None:
        """Korisnik traži ručnu pretragu tarife — otvara TariffSearchDialog."""
        from gui.dialogs.tariff_search_dialog import TariffSearchDialog
        from PySide6.QtWidgets import QDialog

        search_dialog = TariffSearchDialog(self)
        if search_dialog.exec() == QDialog.Accepted:
            code = search_dialog.get_selected_code()
            if code:
                current_item = self.draft.items[self.current_item_index]
                current_item.tariff_code = code
                self._load_current_item()
                self.data_changed.emit()
                if self.on_dirty:
                    self.on_dirty()

                # Zatvori TariffSuggestionDialog ako je otvoren
                active = getattr(self, "_active_suggestion_dialog", None)
                if active:
                    active.accept()

    def _validate_all_items(self) -> list:
        """
        Provjeri sva naimenovanja i vrati listu grešaka.

        Pravila:
        - Rb.33: tarifni broj mora biti popunjen
        - Rb.34: zemlja porijekla mora biti popunjena
        - Rb.40: opcionalna (nije obavezna za export)
        - Količina i vrijednost moraju biti > 0
        - Ako Rb.34 + Rb.36 popunjeni → Rb.44 mora biti popunjen
        """
        errors = []

        # Per-naimenovanje provjere
        for i, item in enumerate(self.draft.items, 1):
            item_errors = []

            if not (item.tariff_code or '').strip():
                item_errors.append("nema tarifnog")

            if not (item.origin_country_code or '').strip():
                item_errors.append("nema zemlje porijekla")

            # Rb.40 nije obavezna — korisnik popunjava po potrebi

            if not (item.package_qty or 0) > 0:
                item_errors.append("nema količine")

            if not (item.item_value or 0) > 0:
                item_errors.append("nema vrijednosti")

            # Ako zemlja + povlastica → mora biti Rb.44
            has_country = bool((item.origin_country_code or '').strip())
            has_preference = bool((item.preference_code or '').strip())
            has_doc = bool(
                (item.attached_document1 or '').strip() or
                (item.attached_document2 or '').strip() or
                (item.attached_document3 or '').strip() or
                (item.attached_document4 or '').strip() or
                (item.attached_document5 or '').strip()
            )
            if has_country and has_preference and not has_doc:
                item_errors.append("povlastica bez Rb.44")

            if item_errors:
                errors.append(f"Naim. {i}: {', '.join(item_errors)}")

        return errors

    def _on_ponisti(self) -> None:
        """Poništi - reload current item"""
        self._load_current_item()
        self._update_all_ui()
        QMessageBox.information(self, "Poništeno", "Promjene su poništene.")

    def clear_tariff_cache(self):
        """Clear tariff cache if database was updated externally"""
        self.tariff_cache.clear()

    def reload_data(self):
        """
        Public method to reload all naimenovanja data.
        Call this after naimenovanja are created/modified externally.
        """
        if len(self.draft.items) == 0:
            self.current_item_index = -1
            logger.warning("  ⚠️  No naimenovanja to display")
            return

        if self.current_item_index >= len(self.draft.items):
            self.current_item_index = 0

        self._load_current_item()
        self._update_all_ui()
        if hasattr(self, "ui") and self.ui:
            self.ui.update()
            self.ui.repaint()
        self.update()
        self.repaint()
        logger.info(f"  ✅ Naimenovanja Tab reloaded: {len(self.draft.items)} items")

    def eventFilter(self, obj, event):
        """Intercept Enter na le_rubrika33 — okida _on_tariff_enter."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            try:
                obj_name = obj.objectName()
            except RuntimeError:
                return super().eventFilter(obj, event)
            if obj_name == "le_rubrika33":
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._on_tariff_enter()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Keyboard shortcuts"""
        if event.modifiers() == Qt.AltModifier:
            if event.key() == Qt.Key_Left:
                self._on_previous()
            elif event.key() == Qt.Key_Right:
                self._on_next()
        elif event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_N:
                self._on_add_item()
            elif event.key() == Qt.Key_D:
                self._on_delete_item()
            elif event.key() == Qt.Key_S:
                self._on_save()

    # ============================================================
    # BaseTabView interface
    # ============================================================

    def get_data(self) -> Dict[str, Any]:
        """Vraća podatke iz view-a (BaseTabView interface)."""
        return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        """Postavlja podatke u view (BaseTabView interface)."""
        pass

    def clear_form(self) -> None:
        """Čisti formu (BaseTabView interface) - delegira na _clear_all_input_fields."""
        self._clear_all_input_fields()


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═════════════���═════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Empty draft - NO test data at all
    draft = DeclarationDraft()
    draft.ensure_min_items(1)
    # CRITICAL: Override default currency value
    draft.items[0].currency = ""

    window = NaimenovanjaTab(draft)
    window.resize(1400, 850)  # Reduced height so bottom bar is closer to grid
    window.setWindowTitle("Deklarant Pro - Naimenovanja (Existing .ui Structure)")
    window.show()

    logger.info("\n✅ Naimenovanja Tab loaded with existing .ui structure!")

    sys.exit(app.exec())
