# gui/tabs/base_controller.py

"""
Base Controller Class za Tab Controllers

Sadrži common funkcionalnost za sve tab controller-e.
Osigurava konzistentan interfejs za event handling i error management.

Primjer korišćenja:
    class ZaglavljeController(BaseTabController):
        def _connect_signals(self):
            self.view.save_requested.connect(self._on_save)
            self.view.delete_requested.connect(self._on_delete)
        
        def _on_save(self):
            try:
                data = self.view.get_data()
                self.service.save(data)
                self.handle_success("Sačuvano!")
            except Exception as e:
                self.handle_error(e)
"""

from typing import Optional, Any, Callable
from gui.tabs.base_view import BaseTabView


class BaseTabController:
    """
    Bazna klasa za tab controllers.
    
    Odgovornosti:
    - Orkestracija između View i Service
    - Event handling (signal/slot konekcije)
    - Error handling i display
    - Progress tracking
    
    NEMA:
    - Business logike (to je u Service)
    - UI konstrukcije (to je u View)
    - Database operacija (to je u Service)
    
    Primjer:
        class ZaglavljeController(BaseTabController):
            def __init__(self, view, service):
                super().__init__(view, service)
            
            def _connect_signals(self):
                self.view.save_requested.connect(self._on_save)
            
            def _on_save(self):
                try:
                    data = self.view.get_data()
                    self.service.save_zaglavlje(data)
                    self.handle_success("Sačuvano!")
                except ValidationError as e:
                    self.handle_error(e)
    """
    
    # ============================================================
    # INIT
    # ============================================================
    
    def __init__(
        self,
        view: BaseTabView,
        service: Optional[Any] = None,
        parent: Optional[Any] = None
    ):
        """
        Inicijalizuj controller.
        
        Args:
            view: View instanca za ovaj controller
            service: Optional Service instanca za business logiku
            parent: Optional parent object (npr. main tab widget)
        """
        self.view = view
        self.service = service
        self.parent = parent
        
        # Auto-connect signals
        self._connect_signals()
    
    # ============================================================
    # SIGNAL CONNECTIONS
    # ============================================================
    
    def _connect_signals(self) -> None:
        """
        Poveži view signale sa controller metodama.
        
        Subclass treba da override-uju ovu metodu i povežu
        specifične signale za svoj tab.
        
        Primjer:
            def _connect_signals(self):
                self.view.save_requested.connect(self._on_save)
                self.view.delete_requested.connect(self._on_delete)
                self.view.data_changed.connect(self._on_data_changed)
        """
        # Base implementation - empty
        # Subclass should override
        pass
    
    # ============================================================
    # ERROR HANDLING
    # ============================================================
    
    def handle_error(
        self,
        error: Exception,
        custom_message: Optional[str] = None
    ) -> None:
        """
        Prikaži error korisniku.
        
        Args:
            error: Exception koji je nastao
            custom_message: Optional custom poruka umjesto defaultne
        
        Primjer:
            >>> try:
            ...     self.service.save(data)
            ... except Exception as e:
            ...     self.handle_error(e, "Greška pri čuvanju")
        """
        if custom_message:
            message = f"{custom_message}: {error}"
        else:
            message = f"Greška: {error}"
        
        self.view.show_error(message)
    
    def handle_validation_error(
        self,
        error: Exception,
        field_name: Optional[str] = None
    ) -> None:
        """
        Prikaži validation error korisniku.
        
        Args:
            error: ValidationError koji je nastao
            field_name: Optional naziv polja koje nije validno
        
        Primjer:
            >>> try:
            ...     self.service.validate(data)
            ... except ValidationError as e:
            ...     self.handle_validation_error(e, "Broj deklaracije")
        """
        if field_name:
            message = f"Nevalidno polje '{field_name}': {error}"
        else:
            message = f"Validacija nije prošla: {error}"
        
        self.view.show_warning(message)
    
    # ============================================================
    # SUCCESS HANDLING
    # ============================================================
    
    def handle_success(self, message: str = "Operacija uspješna") -> None:
        """
        Prikaži success poruku korisniku.
        
        Args:
            message: Poruka za prikaz
        
        Primjer:
            >>> self.service.save(data)
            >>> self.handle_success("Podaci sačuvani!")
        """
        import logging
        logging.getLogger(self.__class__.__name__).info(f"✅ {message}")
    
    # ============================================================
    # CONFIRMATION DIALOGS
    # ============================================================
    
    def confirm_action(
        self,
        message: str,
        title: str = "Potvrda"
    ) -> bool:
        """
        Zatraži potvrdu od korisnika za akciju.
        
        Args:
            message: Poruka za potvrdu
            title: Naslov dialoga
        
        Returns:
            True ako je korisnik potvrdio, False inače
        
        Primjer:
            >>> if self.confirm_action("Da li ste sigurni?"):
            ...     self._perform_action()
        """
        return self.view.confirm(message, title)
    
    def confirm_destructive_action(
        self,
        message: str,
        title: str = "Upozorenje"
    ) -> bool:
        """
        Zatraži potvrdu za destructive akciju (brisanje, reset, itd.).
        
        Default je No (sigurnija opcija).
        
        Args:
            message: Poruka za potvrdu
            title: Naslov dialoga
        
        Returns:
            True ako je korisnik potvrdio, False inače
        
        Primjer:
            >>> if self.confirm_destructive_action("Ovo će obrisati sve podatke!"):
            ...     self._delete_all()
        """
        return self.view.confirm_warning(
            message,
            title,
            default_button=None  # Use default (No for warnings)
        )
    
    # ============================================================
    # PROGRESS TRACKING
    # ============================================================
    
    def with_progress(
        self,
        operation: Callable,
        start_message: str = "Pokretanje...",
        success_message: str = "Završeno!",
        error_message: str = "Greška tokom operacije"
    ) -> Any:
        """
        Izvrši operaciju sa progress tracking-om.
        
        Args:
            operation: Callable koji se izvršava
            start_message: Poruka na početku operacije
            success_message: Poruka nakon uspješnog završetka
            error_message: Poruka ako operacija ne uspije
        
        Returns:
            Rezultat operacije
        
        Raises:
            Exception: Re-raises any exception from operation
        
        Primjer:
            >>> result = self.with_progress(
            ...     lambda: self.service.import_large_file(filepath),
            ...     start_message="Uvoz u toku...",
            ...     success_message="Uvoz završen!",
            ...     error_message="Uvoz nije uspio"
            ... )
        """
        try:
            result = operation()
            return result
        except Exception as e:
            self.handle_error(e, error_message)
            raise
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def log_operation(self, operation: str, success: bool = True) -> None:
        """
        Loguj operaciju (za debugging).
        
        Args:
            operation: Naziv operacije
            success: Da li je operacija uspješna
        
        Primjer:
            >>> self.log_operation("Save zaglavlje", success=True)
        """
        import logging
        logger = logging.getLogger(self.__class__.__name__)
        
        if success:
            logger.info(f"✅ {operation} - uspješno")
        else:
            logger.error(f"❌ {operation} - neuspješno")
