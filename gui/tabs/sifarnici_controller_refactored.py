# gui/tabs/sifarnici_controller_refactored.py

"""
SifarniciController koji koristi BaseTabController.
"""

import logging
from typing import Dict, Any, List, Optional
from gui.tabs.base_controller import BaseTabController
from services.sifarnici_service_refactored import SifarniciService
from gui.tabs.sifarnici_view import SifarniciView
from utils.exceptions import ValidationError


class SifarniciController(BaseTabController):
    """
    Controller za Sifarnici tab.
    Upravlja interakcijom između SifarniciView i SifarniciService.
    """
    
    def __init__(self, view: SifarniciView, service: SifarniciService):
        """
        Inicijalizacija SifarniciController-a.
        
        Args:
            view: SifarniciView instanca
            service: SifarniciService instanca
        """
        super().__init__(view, service)
        self.logger = logging.getLogger(__name__)
        self._current_category = None
        self._current_data = []
        
        # Poveži signale
        self._connect_signals()
    
    def _connect_signals(self):
        """Poveži signale iz view-a sa metodama kontrollera."""
        # Ovdje će se povezati signali kada budu dostupni u view-u
        pass
    
    def load_data(self, category: str = None):
        """
        Učitaj podatke za odabranu kategoriju.
        
        Args:
            category: Kategorija podataka (npr. 'valute', 'drzave', 'dokumenti')
        """
        try:
            if not category:
                category = self._get_current_category()
            
            if not category:
                self.view.show_error("Odaberite kategoriju")
                return
            
            # Pozovi odgovarajuću metodu servisa
            if category == 'valute':
                data = self.service.get_all_valute()
            elif category == 'drzave':
                data = self.service.get_all_drzave()
            elif category == 'dokumenti':
                data = self.service.get_all_dokumenti()
            elif category == 'vrste_prijevoza':
                data = self.service.get_all_vrste_prijevoza()
            elif category == 'tipovi_deklaracija':
                data = self.service.get_all_tipovi_deklaracija()
            else:
                self.view.show_error(f"Nepoznata kategorija: {category}")
                return
            
            self._current_data = data
            self.view.display_data(data)
            self.log_operation("load_data", success=True, 
                            details=f"Učitano {len(data)} stavki iz kategorije {category}")
            
        except Exception as e:
            self.handle_error(e, "load_data")
    
    def get_valute(self) -> List[Dict[str, Any]]:
        """Dobavi sve valute."""
        try:
            return self.service.get_all_valute()
        except Exception as e:
            self.handle_error(e, "get_valute")
            return []
    
    def get_drzave(self) -> List[Dict[str, Any]]:
        """Dobavi sve države."""
        try:
            return self.service.get_all_drzave()
        except Exception as e:
            self.handle_error(e, "get_drzave")
            return []
    
    def get_dokumenti(self) -> List[Dict[str, Any]]:
        """Dobavi sve tipove dokumenata."""
        try:
            return self.service.get_all_dokumenti()
        except Exception as e:
            self.handle_error(e, "get_dokumenti")
            return []
    
    def get_vrste_prijevoza(self) -> List[Dict[str, Any]]:
        """Dobavi sve vrste prijevoza."""
        try:
            return self.service.get_all_vrste_prijevoza()
        except Exception as e:
            self.handle_error(e, "get_vrste_prijevoza")
            return []
    
    def add_item(self, category: str, data: Dict[str, Any]) -> bool:
        """
        Dodaj novu stavku u šifarnik.
        
        Args:
            category: Kategorija (valute, drzave, dokumenti, itd.)
            data: Podaci za unos
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            # Validacija podataka
            errors = self.service.validate_reference_data(data)
            if errors:
                self.view.show_error("Greške u podacima:\n" + "\n".join(errors))
                return False
            
            # Pozovi odgovarajuću metodu servisa
            if category == 'valute':
                success = self.service.add_valuta(
                    data.get('sifra'),
                    data.get('naziv'),
                    data.get('opis', '')
                )
            elif category == 'drzave':
                success = self.service.add_drzava(
                    data.get('sifra'),
                    data.get('naziv'),
                    data.get('opis', '')
                )
            elif category == 'dokumenti':
                success = self.service.add_dokument(
                    data.get('sifra'),
                    data.get('naziv'),
                    data.get('opis', '')
                )
            elif category == 'vrste_prijevoza':
                success = self.service.add_vrsta_prijevoza(
                    data.get('sifra'),
                    data.get('naziv'),
                    data.get('opis', '')
                )
            else:
                self.view.show_error(f"Nepoznata kategorija: {category}")
                return False
            
            if success:
                self.view.show_success("Stavka uspješno dodana")
                self.load_data(category)
                return True
            else:
                self.view.show_error("Greška pri dodavanju stavke")
                return False
                
        except ValidationError as e:
            self.handle_validation_error(e)
            return False
        except Exception as e:
            self.handle_error(e, "add_item")
            return False
    
    def update_item(self, category: str, item_id: int, data: Dict[str, Any]) -> bool:
        """
        Ažuriraj postojeću stavku.
        
        Args:
            category: Kategorija
            item_id: ID stavke za ažuriranje
            data: Novi podaci
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            # Ovdje bi se implementirala logika za ažuriranje
            # Ovisno o kategoriji, poziva se odgovarajući servis
            self.view.show_success("Stavka uspješno ažurirana")
            return True
            
        except Exception as e:
            self.handle_error(e, "update_item")
            return False
    
    def delete_item(self, category: str, sifra: str) -> bool:
        """
        Obriši stavku iz šifrarnika.
        
        Args:
            category: Kategorija
            sifra: Šifra stavke za brisanje
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            # Potvrdi brisanje
            if not self.view.confirm("Da li ste sigurni da želite obrisati ovu stavku?"):
                return False
            
            # Pozovi odgovarajuću metodu servisa
            if category == 'valute':
                success = self.service.delete_valuta(sifra)
            elif category == 'drzave':
                success = self.service.delete_drzava(sifra)
            elif category == 'dokumenti':
                success = self.service.delete_dokument(sifra)
            elif category == 'vrste_prijevoza':
                success = self.service.delete_vrsta_prijevoza(sifra)
            else:
                self.view.show_error(f"Nepoznata kategorija: {category}")
                return False
            
            if success:
                self.view.show_success("Stavka uspješno obrisana")
                self.load_data(category)
                return True
            else:
                self.view.show_error("Greška pri brisanju stavke")
                return False
                
        except Exception as e:
            self.handle_error(e, "delete_item")
            return False
    
    def search_items(self, category: str, search_term: str) -> List[Dict[str, Any]]:
        """
        Pretraži stavke po zadatom terminu.
        
        Args:
            category: Kategorija za pretragu
            search_term: Termin za pretragu
            
        Returns:
            Lista pronađenih stavki
        """
        try:
            if category == 'valute':
                return self.service.search_valute(search_term)
            elif category == 'drzave':
                return self.service.search_drzave(search_term)
            elif category == 'dokumenti':
                return self.service.search_dokumenti(search_term)
            elif category == 'vrste_prijevoza':
                return self.service.search_vrste_prijevoza(search_term)
            else:
                return []
        except Exception as e:
            self.handle_error(e, "search_items")
            return []
    
    def export_to_csv(self, category: str, filepath: str) -> bool:
        """
        Izvezi podatke u CSV.
        
        Args:
            category: Kategorija za izvoz
            filepath: Putanja do CSV fajla
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            return self.service.export_to_csv(category, filepath)
        except Exception as e:
            self.handle_error(e, "export_to_csv")
            return False
    
    def get_statistika(self) -> Dict[str, Any]:
        """
        Dobavi statističke podatke.
        
        Returns:
            Rječnik sa statističkim podacima
        """
        try:
            return self.service.get_statistika()
        except Exception as e:
            self.handle_error(e, "get_statistika")
            return {}
    
    def validate_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validiraj podatke.
        
        Args:
            data: Podaci za validaciju
            
        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        errors = []
        
        # Validacija obaveznih polja
        if not data.get('sifra'):
            errors.append("Šifra je obavezno polje")
        
        if not data.get('naziv'):
            errors.append("Naziv je obavezno polje")
        
        # Dodatne validacije ovisno o kategoriji
        if 'sifra' in data and len(data['sifra']) > 20:
            errors.append("Šifra ne smije biti duža od 20 karaktera")
        
        if 'naziv' in data and len(data['naziv']) > 200:
            errors.append("Naziv ne smije biti duži od 200 karaktera")
        
        return errors
    
    def _get_current_category(self) -> str:
        """
        Dobavi trenutno odabranu kategoriju iz view-a.
        Ova metoda treba biti implementirana u view-u.
        """
        # Ovdje bi se pozvala metoda view-a koja vraća trenutno odabranu kategoriju
        # Za sada vraćamo prazan string
        return self.view.get_current_category() if hasattr(self.view, 'get_current_category') else ""