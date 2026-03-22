# gui/tabs/zaglavlje_controller_refactored.py

"""
Refaktorisani ZaglavljeController koji koristi BaseTabController.
"""

import logging
from typing import Callable, Optional, TYPE_CHECKING

from gui.tabs.base_controller import BaseTabController
from utils.exceptions import ValidationError, DatabaseError

if TYPE_CHECKING:
    from gui.tabs.zaglavlje_view import ZaglavljeView
    from services.zaglavlje_service_refactored import ZaglavljeService
    from core.draft.draft import DeclarationDraft


logger = logging.getLogger(__name__)


class ZaglavljeController(BaseTabController):
    """
    Refaktorisani ZaglavljeController koji nasljeđuje BaseTabController.
    
    Odgovornosti:
    - Orkestracija između View i Service
    - Event handling
    - Error handling
    - Progress tracking
    """
    
    def __init__(
        self,
        view: 'ZaglavljeView',
        service: 'ZaglavljeService',
        save_draft_fn: Optional[Callable] = None,
        get_draft_fn: Optional[Callable] = None,
    ):
        """
        Inicijalizuj controller.
        
        Args:
            view: View instanca
            service: Service instanca
            save_draft_fn: Funkcija za čuvanje draft-a (opciono)
            get_draft_fn: Funkcija za dobavljanje draft-a (opciono)
        """
        super().__init__(view, service)
        self.save_draft_fn = save_draft_fn
        self.get_draft_fn = get_draft_fn
        
        # Auto-connect signals
        self._connect_signals()
    
    def _connect_signals(self) -> None:
        """
        Poveži view signale sa controller metodama.
        """
        # Ovdje ćemo povezati signale kada View bude refaktorisan
        # Za sada, ova metoda je prazna
        pass
    
    def load_data(self, draft: 'DeclarationDraft') -> None:
        """
        Učitaj podatke iz draft-a u view.
        
        Args:
            draft: DeclarationDraft objekat
        """
        try:
            # Koristimo with_progress za tracking
            self.with_progress(
                lambda: self._load_data_internal(draft),
                start_message="Učitavanje podataka...",
                success_message="Podaci uspješno učitani",
                error_message="Greška pri učitavanju podataka"
            )
        except Exception as e:
            self.handle_error(e, "load_data")
    
    def _load_data_internal(self, draft: 'DeclarationDraft') -> None:
        """
        Interna metoda za učitavanje podataka.
        
        Args:
            draft: DeclarationDraft objekat
        """
        # Konvertuj draft u UI podatke
        data = self.service.load_from_draft(draft)
        
        # Postavi podatke u view
        self.view.set_data(data)
        
        # Loguj operaciju
        self.log_operation("load_data", success=True)
    
    def save_data(self) -> Optional['DeclarationDraft']:
        """
        Sačuvaj podatke iz view-a u draft.
        
        Returns:
            Ažurirani DeclarationDraft ili None ako nije uspješno
        """
        try:
            return self.with_progress(
                lambda: self._save_data_internal(),
                start_message="Čuvanje podataka...",
                success_message="Podaci uspješno sačuvani",
                error_message="Greška pri čuvanju podataka"
            )
        except Exception as e:
            self.handle_error(e, "save_data")
            return None
    
    def _save_data_internal(self) -> 'DeclarationDraft':
        """
        Interna metoda za čuvanje podataka.
        
        Returns:
            Ažurirani DeclarationDraft
        """
        # Dobavi podatke iz view-a
        data = self.view.get_data()
        
        # Validacija podataka
        try:
            self.service.validate(data)
        except ValidationError as e:
            self.handle_validation_error(e, e.field)
            raise
        
        # Ako imamo funkciju za dobavljanje draft-a, koristimo je
        if self.get_draft_fn:
            draft = self.get_draft_fn()
        else:
            # Kreiraj novi draft ako nema funkcije
            from core.draft.draft import DeclarationDraft
            draft = DeclarationDraft()
        
        # Konvertuj UI podatke u draft
        updated_draft = self.service.save_to_draft(draft, data)
        
        # Ako imamo funkciju za čuvanje draft-a, pozovi je
        if self.save_draft_fn:
            self.save_draft_fn(updated_draft)
        
        # Loguj operaciju
        self.log_operation("save_data", success=True)
        
        return updated_draft
    
    def save_to_database(self) -> bool:
        """
        Sačuvaj podatke u bazu.
        
        Returns:
            True ako je uspješno, False inače
        """
        try:
            return self.with_progress(
                lambda: self._save_to_database_internal(),
                start_message="Čuvanje u bazu...",
                success_message="Podaci uspješno sačuvani u bazu",
                error_message="Greška pri čuvanju u bazu"
            )
        except Exception as e:
            self.handle_error(e, "save_to_database")
            return False
    
    def _save_to_database_internal(self) -> bool:
        """
        Interna metoda za čuvanje u bazu.
        
        Returns:
            True ako je uspješno
        """
        # Dobavi podatke iz view-a
        data = self.view.get_data()
        
        # Sačuvaj u bazu
        success = self.service.save_to_database(data)
        
        if success:
            self.log_operation("save_to_database", success=True)
        else:
            self.log_operation("save_to_database", success=False)
        
        return success
    
    def load_from_database(self, broj_deklaracije: str) -> bool:
        """
        Učitaj podatke iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije za učitavanje
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            return self.with_progress(
                lambda: self._load_from_database_internal(broj_deklaracije),
                start_message="Učitavanje iz baze...",
                success_message="Podaci uspješno učitani iz baze",
                error_message="Greška pri učitavanju iz baze"
            )
        except Exception as e:
            self.handle_error(e, "load_from_database")
            return False
    
    def _load_from_database_internal(self, broj_deklaracije: str) -> bool:
        """
        Interna metoda za učitavanje iz baze.
        
        Args:
            broj_deklaracije: Broj deklaracije
            
        Returns:
            True ako je uspješno
        """
        # Učitaj podatke iz baze
        data = self.service.load_from_database(broj_deklaracije)
        
        if data:
            # Postavi podatke u view
            self.view.set_data(data)
            self.log_operation("load_from_database", success=True)
            return True
        else:
            self.view.show_warning(f"Zaglavlje sa brojem {broj_deklaracije} nije pronađeno")
            self.log_operation("load_from_database", success=False)
            return False
    
    def clear_form(self) -> None:
        """
        Očisti formu.
        """
        try:
            self.view.clear_form()
            self.log_operation("clear_form", success=True)
        except Exception as e:
            self.handle_error(e, "clear_form")
    
    def search_zaglavlja(self, search_term: str = None, 
                        status: str = None,
                        start_date: str = None,
                        end_date: str = None) -> list:
        """
        Pretraži zaglavlja.
        
        Args:
            search_term: Tekst za pretragu
            status: Status filter
            start_date: Početni datum
            end_date: Krajnji datum
            
        Returns:
            Lista pronađenih zaglavlja
        """
        try:
            return self.with_progress(
                lambda: self.service.search_zaglavlja(
                    search_term=search_term,
                    status=status,
                    start_date=start_date,
                    end_date=end_date
                ),
                start_message="Pretraga u toku...",
                success_message="Pretraga završena",
                error_message="Greška pri pretrazi"
            )
        except Exception as e:
            self.handle_error(e, "search_zaglavlja")
            return []
    
    def get_statistika(self) -> dict:
        """
        Dobavi statističke podatke.
        
        Returns:
            Dictionary sa statističkim podacima
        """
        try:
            return self.with_progress(
                lambda: self.service.get_statistika(),
                start_message="Prikupljanje statistike...",
                success_message="Statistika prikupljena",
                error_message="Greška pri prikupljanju statistike"
            )
        except Exception as e:
            self.handle_error(e, "get_statistika")
            return {}
    
    def export_to_csv(self, filepath: str, 
                     start_date: str = None, 
                     end_date: str = None) -> str:
        """
        Izvezi zaglavlja u CSV.
        
        Args:
            filepath: Putanja do CSV fajla
            start_date: Početni datum
            end_date: Krajnji datum
            
        Returns:
            Putanja do kreiranog CSV fajla
        """
        try:
            return self.with_progress(
                lambda: self.service.export_to_csv(
                    filepath=filepath,
                    start_date=start_date,
                    end_date=end_date
                ),
                start_message="Izvoz u CSV u toku...",
                success_message="Izvoz završen",
                error_message="Greška pri izvozu u CSV"
            )
        except Exception as e:
            self.handle_error(e, "export_to_csv")
            raise
    
    def validate_duplicate(self, broj_deklaracije: str) -> bool:
        """
        Provjeri da li zaglavlje već postoji.
        
        Args:
            broj_deklaracije: Broj deklaracije
            
        Returns:
            True ako već postoji, False ako ne postoji
        """
        try:
            return self.service.validate_duplicate(broj_deklaracije)
        except Exception as e:
            self.handle_error(e, "validate_duplicate")
            return False
    
    def get_validation_errors(self) -> list:
        """
        Dobavi listu grešaka u validaciji trenutnih podataka.
        
        Returns:
            Lista grešaka
        """
        try:
            data = self.view.get_data()
            return self.service.get_validation_errors(data)
        except Exception as e:
            self.handle_error(e, "get_validation_errors")
            return ["Greška pri validaciji podataka"]
    
    def confirm_save(self) -> bool:
        """
        Zatraži potvrdu za čuvanje.
        
        Returns:
            True ako je korisnik potvrdio
        """
        return self.confirm_action(
            "Da li ste sigurni da želite sačuvati podatke?",
            title="Potvrda čuvanja"
        )
    
    def confirm_delete(self) -> bool:
        """
        Zatraži potvrdu za brisanje.
        
        Returns:
            True ako je korisnik potvrdio
        """
        return self.confirm_destructive_action(
            "Da li ste sigurni da želite obrisati ovo zaglavlje?\n"
            "Ova akcija se ne može poništiti.",
            title="Potvrda brisanja"
        )
    
    def confirm_export(self) -> bool:
        """
        Zatraži potvrdu za izvoz.
        
        Returns:
            True ako je korisnik potvrdio
        """
        return self.confirm_action(
            "Da li ste sigurni da želite izvesti podatke?",
            title="Potvrda izvoza"
        )
    
    def show_validation_errors(self) -> None:
        """
        Prikaži greške u validaciji.
        """
        errors = self.get_validation_errors()
        if errors:
            error_message = "\n".join(errors)
            self.view.show_error(f"Greške u validaciji:\n{error_message}")
    
    def auto_save_if_valid(self) -> bool:
        """
        Automatski sačuvaj ako su podaci validni.
        
        Returns:
            True ako je uspješno sačuvano
        """
        errors = self.get_validation_errors()
        if not errors:
            return self.save_data() is not None
        return False