# gui/tabs/base_view.py

"""
Base View Class za Tab Views

Sadrži common funkcionalnost za sve tab view-ove.
Osigurava konzistentan interfejs i zajedničke utility metode.

Primjer korišćenja:
    class ZaglavljeView(BaseTabView):
        def get_data(self) -> Dict[str, Any]:
            # Implementacija
            pass
        
        def set_data(self, data: Dict[str, Any]):
            # Implementacija
            pass
        
        def clear_form(self):
            # Implementacija
            pass
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal
from typing import Callable, Dict, Any, Optional

from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class BaseTabView(QWidget):
    """
    Bazna klasa za tab views.
    
    Odgovornosti:
    - Samo UI konstrukcija (widgets, layouts)
    - Signal emission
    - Data display
    
    NEMA:
    - Business logike
    - Database operacija
    - Validacije podataka
    
    Primjer:
        class ZaglavljeView(BaseTabView):
            save_requested = Signal()
            
            def __init__(self):
                super().__init__()
                self._setup_ui()
            
            def get_data(self):
                return {'field': self.line_edit.text()}
    """
    
    # ============================================================
    # COMMON SIGNALS
    # ============================================================
    
    data_changed = Signal()
    """Emitovan kada se podaci u formi promijene."""
    
    error_occurred = Signal(str)
    """Emitovan kada dođe do greške. Prima error poruku."""
    
    # ============================================================
    # INIT
    # ============================================================
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Inicijalizuj base view.
        
        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
    
    # ============================================================
    # ABSTRACT METHODS (Subclass must implement)
    # ============================================================
    
    def get_data(self) -> Dict[str, Any]:
        """
        Vrati podatke iz UI widgeta.
        
        Returns:
            Dictionary sa podacima iz forme.
            Ključevi su nazivi polja, vrijednosti su podaci.
        
        Raises:
            NotImplementedError: Ako subclass ne implementira
        
        Primjer:
            >>> view.get_data()
            {'broj_deklaracije': '123', 'datum': '2024-01-01'}
        """
        raise NotImplementedError("Subclass must implement get_data()")
    
    def set_data(self, data: Dict[str, Any]) -> None:
        """
        Postavi podatke u UI widgete.
        
        Args:
            data: Dictionary sa podacima za formu.
                  Ključevi su nazivi polja, vrijednosti su podaci.
        
        Raises:
            NotImplementedError: Ako subclass ne implementira
        
        Primjer:
            >>> view.set_data({'broj_deklaracije': '123'})
        """
        raise NotImplementedError("Subclass must implement set_data()")
    
    def clear_form(self) -> None:
        """
        Očisti sve UI widgete.
        
        Resetuje sve field-ove na prazne vrijednosti.
        
        Raises:
            NotImplementedError: Ako subclass ne implementira
        
        Primjer:
            >>> view.clear_form()
        """
        raise NotImplementedError("Subclass must implement clear_form()")
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================

    def _message_parent(self) -> QWidget:
        win = self.window()
        return win if win else self

    def _with_preserved_window_geometry(self, callback: Callable[[QWidget], Any]) -> Any:
        win = self._message_parent()
        was_maximized = win.isMaximized()
        geom = win.geometry()
        result = callback(win)
        if was_maximized:
            win.showMaximized()
        else:
            win.setGeometry(geom)
        return result

    def _show_message(self, method: Callable[..., Any], title: str, message: str) -> Any:
        return self._with_preserved_window_geometry(
            lambda parent: method(parent, title, message)
        )

    def ask_question(
        self,
        message: str,
        title: str = "Potvrda",
        buttons: QMessageBox.StandardButton = (
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ),
        default_button: Optional[QMessageBox.StandardButton] = None,
    ) -> QMessageBox.StandardButton:
        def _ask(parent: QWidget) -> QMessageBox.StandardButton:
            if default_button is None:
                return QMessageBox.question(parent, title, message, buttons)
            return QMessageBox.question(parent, title, message, buttons, default_button)

        return self._with_preserved_window_geometry(_ask)
    
    def show_success(self, message: str = "Operacija uspješna", title: str = "Uspjeh") -> None:
        """
        Prikaži success poruku korisniku.
        
        Args:
            message: Poruka za prikaz
        
        Primjer:
            >>> view.show_success("Podaci sačuvani!")
        """
        self._show_message(QMessageBox.information, title, message)
    
    def show_error(self, message: str, title: str = "Greška") -> None:
        """
        Prikaži error poruku korisniku.
        
        Args:
            message: Error poruka za prikaz
        
        Emits:
            error_occurred: Signal sa error porukom
        
        Primjer:
            >>> view.show_error("Greška pri čuvanju podataka")
        """
        self._show_message(QMessageBox.critical, title, message)
        self.error_occurred.emit(message)
    
    def show_warning(self, message: str, title: str = "Upozorenje") -> None:
        """
        Prikaži warning poruku korisniku.
        
        Args:
            message: Warning poruka za prikaz
        
        Primjer:
            >>> view.show_warning("Nesačuvane promjene će biti izgubljene")
        """
        self._show_message(QMessageBox.warning, title, message)

    def show_info(self, message: str, title: str = "Info") -> None:
        self._show_message(QMessageBox.information, title, message)
    
    def confirm(self, message: str, title: str = "Potvrda") -> bool:
        """
        Prikazati confirmation dialog.
        
        Args:
            message: Poruka za potvrdu
            title: Naslov dialoga
        
        Returns:
            True ako je korisnik potvrdio (Yes), False inače (No)
        
        Primjer:
            >>> if view.confirm("Da li ste sigurni?"):
            ...     # Korak dalje
        """
        reply = self.ask_question(message, title)
        return reply == QMessageBox.StandardButton.Yes
    
    def confirm_warning(
        self,
        message: str,
        title: str = "Potvrda",
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.No
    ) -> bool:
        """
        Prikazati confirmation dialog za warning situacije.
        
        Razlika od confirm() je što ima default No (sigurnija opcija).
        
        Args:
            message: Poruka za potvrdu
            title: Naslov dialoga
            default_button: Koje dugme je default (preporučeno No za destructive actions)
        
        Returns:
            True ako je korisnik potvrdio Yes
        
        Primjer:
            >>> if view.confirm_warning("Ovo će obrisati sve podatke!"):
            ...     # Destructive action
        """
        reply = self.ask_question(
            message,
            title,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            default_button,
        )
        return reply == QMessageBox.StandardButton.Yes
