# gui/tabs/naimenovanja_controller.py

"""
Naimenovanja Controller - Orchestration Layer

Koordinacija između View i Service layer-a.
NEMA direktne UI manipulacije ili business logike.

Odgovornosti:
- Event handling (navigation, add/delete, suggest tariff)
- Orchestration (View ↔ Service communication)
- Error handling i poruke korisniku
- State management
"""

from typing import Optional, List, Dict, Any
from gui.tabs.naimenovanja_view import NaimenovanjaView
from services.naimenovanja_service import NaimenovanjaService
from core.draft.draft import DeclarationDraft


class NaimenovanjaController:
    """
    Controller layer za Naimenovanja tab - orchestration!
    
    Odgovornosti:
    - Povezivanje View signala sa handler-ima
    - Navigation kroz stavke
    - Orchestration load/save operacija
    - Error handling
    
    NEMA:
    - Direktne UI manipulacije
    - Business logike
    """
    
    def __init__(self, view: NaimenovanjaView, service: NaimenovanjaService):
        """
        Inicijalizacija Controller-a.
        
        Args:
            view: NaimenovanjaView instanca
            service: NaimenovanjaService instanca
        """
        self.view = view
        self.service = service
        self.draft: Optional[DeclarationDraft] = None
        self.current_index = 0
        self.items_data: List[Dict[str, Any]] = []
        
        # Connect signals
        self._connect_signals()
    
    def _connect_signals(self):
        """Povezivanje View signala sa handler metodama."""
        # Navigation
        self.view.navigate_requested.connect(self._on_navigate)
        if self.view.combo_items:
            self.view.combo_items.currentIndexChanged.connect(self._on_item_changed)

        # Actions
        self.view.add_item_requested.connect(self._on_add_item)
        self.view.delete_item_requested.connect(self._on_delete_item)
        self.view.save_requested.connect(self._on_save)

        # Features
        self.view.suggest_tariff_requested.connect(self._on_suggest_tariff)
        self.view.validate_requested.connect(self._on_validate)

        # Data changes - emit to parent (MainWindow expects this)
        # No internal handling needed to avoid recursion
    
    # ============================================================
    # PUBLIC METHODS
    # ============================================================
    
    def load_data(self, draft: DeclarationDraft):
        """
        Orchestrate učitavanje podataka iz Draft-a.
        
        1. Pozovi Service da konvertuje Draft → data dict
        2. Sačuvaj stavke
        3. Pozovi View da prikaže podatke
        4. Handle errors
        """
        try:
            self.draft = draft
            data = self.service.load_from_draft(draft)
            self.items_data = data['items']
            self.current_index = data.get('current_item_index', 0)
            
            self._update_view()
            self.handle_success(f"Učitano {len(self.items_data)} stavki")
        except Exception as e:
            self.handle_error(e, "load_data")
    
    def save_data(self) -> Optional[DeclarationDraft]:
        """
        Orchestrate čuvanje podataka u Draft.
        
        1. Ažuriraj trenutnu stavku iz View
        2. Pozovi Service da konvertuje data → Draft
        3. Return Draft
        4. Handle errors
        """
        try:
            # Update current item from view
            self._update_current_item_from_view()
            
            # Save to draft
            if self.draft:
                data = {
                    'current_item_index': self.current_index,
                    'items': self.items_data,
                }
                self.draft = self.service.save_to_draft(self.draft, data)
                self.handle_success(f"Sačuvano {len(self.items_data)} stavki")
                return self.draft
            
            return None
            
        except Exception as e:
            self.handle_error(e, "save_data")
            return None
    
    def handle_error(self, error: Exception, context: str):
        """
        Centralizovano error handling.
        
        Args:
            error: Exception koji se desio
            context: Kontekst gdje se error desio
        """
        msg = f"Greška ({context}): {str(error)}"
        self.view.show_error(msg)
    
    def handle_success(self, msg: str):
        """
        Centralizovano success handling.
        
        Args:
            msg: Success poruka
        """
        self.view.show_success(msg)
    
    # ============================================================
    # EVENT HANDLERS
    # ============================================================
    
    def _on_navigate(self, direction: int):
        """
        Handler za navigaciju (prev/next).
        
        Args:
            direction: -1 za prev, +1 za next
        """
        if not self.items_data:
            return
        
        # Update current item from view before navigating
        self._update_current_item_from_view()
        
        # Calculate new index
        new_index = self.current_index + direction
        
        # Validate bounds
        if new_index < 0:
            new_index = 0
        elif new_index >= len(self.items_data):
            new_index = len(self.items_data) - 1
        
        # Navigate if index changed
        if new_index != self.current_index:
            self.current_index = new_index
            self._update_view()
    
    def _on_item_changed(self, index: int):
        """
        Handler za promjenu stavke u dropdown-u.
        
        Args:
            index: Novi indeks
        """
        if not self.items_data or index < 0 or index >= len(self.items_data):
            return
        
        # Update current item from view before switching
        self._update_current_item_from_view()
        
        # Switch to new item
        self.current_index = index
        self._update_view()
    
    def _on_add_item(self):
        """Handler za dodavanje stavke."""
        # Create new empty item
        new_item = {
            'item_id': '',
            'ordinal_no': len(self.items_data) + 1,
            'tariff_code': '',
            'goods_trade_name': '',
            'origin_country_code': '',
            'package_code': '',
            'package_name': '',
            'package_qty': 0,
            'container_number1': '',
            'container_number2': '',
            'goods_description': '',
        }
        
        self.items_data.append(new_item)
        self.current_index = len(self.items_data) - 1
        
        self._update_view()
        self.view.data_changed.emit()
    
    def _on_delete_item(self):
        """Handler za brisanje stavke."""
        if not self.items_data:
            self.view.show_warning("Nema stavki za brisanje")
            return
        
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self.view,
            "Brisanje stavke",
            f"Da li ste sigurni da želite obrisati stavku {self.current_index + 1}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove item
            del self.items_data[self.current_index]
            
            # Adjust index
            if self.current_index >= len(self.items_data):
                self.current_index = max(0, len(self.items_data) - 1)
            
            # Update view
            self._update_view()
            self.view.data_changed.emit()
    
    def _on_save(self):
        """Handler za čuvanje."""
        self.save_data()
    
    def _on_suggest_tariff(self):
        """Handler za sugestiju tarifnog broja."""
        # Get current item data
        current_item = self._get_current_item()

        if not current_item:
            self.view.show_warning("Nema trenutne stavke")
            return

        goods_name = current_item.get('goods_trade_name', '')
        origin_country = current_item.get('origin_country_code', '')

        if not goods_name:
            self.view.show_warning("Unesite naziv robe za sugestiju")
            return

        try:
            suggestions = self.service.suggest_tariff(
                goods_trade_name=goods_name,
                origin_country_code=origin_country,
            )

            if not suggestions:
                self.view.show_warning("Nema prijedloga za ovaj proizvod")
                return

            # Get first suggestion
            first = suggestions[0]
            confidence = first.get('similarity', 0.5)
            tariff_code = first['tariff_code']
            needs_review = first.get('needs_review', False)
            
            # Ako je confidence visok (>0.85), auto-popuni
            if confidence >= 0.85 and not needs_review:
                self.view.fields['tariff_code'].setText(tariff_code)
                self.handle_success(f"✅ Auto-popunjeno: {tariff_code} (confidence: {confidence:.0%})")
            else:
                # Prikaži dijalog za potvrdu
                from PySide6.QtWidgets import QMessageBox
                
                msg = QMessageBox(self.view)
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("🤖 AI Prijedlog")
                msg.setText(f"Pronađen prijedlog za tarifni broj:")
                msg.setInformativeText(
                    f"<b>{tariff_code}</b><br><br>"
                    f"Confidence: {confidence:.0%}<br>"
                    f"Metoda: {first.get('method', 'AI')}<br><br>"
                    f"Objašnjenje: {first.get('description', 'N/A')[:200]}"
                )
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                msg.setDefaultButton(QMessageBox.Ok)
                
                if msg.exec() == QMessageBox.Ok:
                    self.view.fields['tariff_code'].setText(tariff_code)
                    self.handle_success(f"Prihvaćen prijedlog: {tariff_code}")
                else:
                    self.handle_success("Odbijen prijedlog")

        except Exception as e:
            self.handle_error(e, "suggest_tariff")
    
    def _on_validate(self):
        """Handler za validaciju."""
        errors_by_index = self.service.validate_all_naimenovanja(self.items_data)
        
        if not errors_by_index:
            self.handle_success("✅ Sve stavke su validne")
            return
        
        # Show errors
        total_errors = sum(len(e) for e in errors_by_index.values())
        self.view.show_warning(f"Pronađeno {total_errors} grešaka u {len(errors_by_index)} stavki")
    
    def _on_data_changed(self):
        """Handler za promjenu podataka."""
        # Update current item from view
        # Disabled to avoid recursion - handled by save
        pass
    
    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    
    def _get_current_item(self) -> Optional[Dict[str, Any]]:
        """
        Dohvati trenutnu stavku.
        
        Returns:
            Dict sa podacima ili None
        """
        if not self.items_data or self.current_index >= len(self.items_data):
            return None
        return self.items_data[self.current_index]
    
    def _update_current_item_from_view(self):
        """Ažuriraj trenutnu stavku iz View podataka."""
        if not self.items_data or self.current_index >= len(self.items_data):
            return
        
        view_data = self.view.get_data()
        self.items_data[self.current_index].update(view_data)
    
    def _update_view(self):
        """Ažuriraj View sa trenutnom stavkom."""
        # Block combo_items signal to avoid recursion
        if self.view.combo_items:
            self.view.combo_items.blockSignals(True)

        # Update item selector
        self.view.update_item_selector(self.items_data)

        # Set current item data
        current_item = self._get_current_item()
        if current_item:
            self.view.set_data(current_item)

        # Update indicator and heading
        self.view.update_indicator(self.current_index + 1, len(self.items_data))
        if self.items_data and self.current_index < len(self.items_data):
            ordinal = self.items_data[self.current_index].get('ordinal_no', self.current_index + 1)
            self.view.update_heading(ordinal)

        # Update combo index and unblock signals
        if self.view.combo_items:
            self.view.combo_items.setCurrentIndex(self.current_index)
            self.view.combo_items.blockSignals(False)
