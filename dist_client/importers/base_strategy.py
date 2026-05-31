# importers/base_strategy.py

"""
Base Strategy Interface for Import System

Ovaj modul definiše apstraktni interfejs za sve import strategije.
Svaka strategija mora implementirati ove metode da bi bila kompatibilna
sa centralizovanim import sistemom.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Union, List
from pathlib import Path

from core.draft.draft import InvoiceLine


class ImportStrategy(ABC):
    """
    Apstraktna baza za sve import strategije.
    
    Svaka konkretna strategija (Excel, PDF, XML, itd.) treba naslijediti
    ovu klasu i implementirati sve apstraktne metode.
    
    Primjer:
        class ExcelImportStrategy(ImportStrategy):
            
            @property
            def strategy_name(self) -> str:
                return "Excel Importer"
            
            def can_handle(self, filepath: Path) -> bool:
                return filepath.suffix.lower() in ['.xlsx', '.xls']
            
            def import_file(self, filepath: Path, progress_callback=None):
                # Implementacija Excel import logike
                pass
    """
    
    @abstractmethod
    def can_handle(self, filepath: Path) -> bool:
        """
        Provjeri da li ova strategija može procesirati dati fajl.
        
        Args:
            filepath: Putanja do fajla koji se provjerava
            
        Returns:
            True ako strategija može procesirati fajl, False inače
            
        Primjer:
            >>> strategy = ExcelImportStrategy()
            >>> strategy.can_handle(Path("faktura.xlsx"))
            True
            >>> strategy.can_handle(Path("faktura.pdf"))
            False
        """
        pass
    
    @abstractmethod
    def import_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[List[InvoiceLine], 'ImportResult']:
        """
        Importuj fajl i vrati normalizovane podatke.
        
        Ova metoda treba:
        1. Validirati fajl (format, struktura, podaci)
        2. Ekstrahovati podatke iz fajla
        3. Normalizovati podatke u InvoiceLine objekte
        4. Opciono javljati progress kroz callback
        
        Args:
            filepath: Putanja do fajla za import
            progress_callback: Opcioni callback za progress (0-100).
                               Poziva se sa vrijednostima od 0 do 100.
        
        Returns:
            Lista InvoiceLine objekata ili ImportResult objekat koji
            sadrži podatke i metainformacije o importu.
        
        Raises:
            ImportError: Ako import ne uspije iz bilo kog razloga
                         (nevalidan format, greška pri čitanju, itd.)
        
        Primjer:
            >>> strategy = ExcelImportStrategy()
            >>> lines = strategy.import_file(
            ...     Path("faktura.xlsx"),
            ...     progress_callback=lambda p: print(f"Progress: {p}%")
            ... )
            >>> len(lines)
            15
        """
        pass
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """
        Ime strategije (za logging, debugging i UI prikaz).
        
        Treba biti kratko i deskriptivno.
        
        Primjeri:
            - "Excel Importer"
            - "PDF Blagić Importer"
            - "XML ASYCUDA Importer"
        """
        pass
    
    @property
    def priority(self) -> int:
        """
        Prioritet strategije (veći broj = viši prioritet).
        
        Koristi se kada više strategija može procesirati isti fajl.
        Strategija sa najvišim prioritetom će biti odabrana prva.
        
        Default je 0. Specijalizovane strategije treba da imaju
        veći prioritet od opštih.
        
        Primjeri:
            - Opšti Excel importer: priority = 0
            - Specifični Blagić Excel importer: priority = 10
            - Opšti PDF importer: priority = 0
            - Specifični Attos PDF importer: priority = 10
        
        Returns:
            int: Prioritet strategije (default: 0)
        """
        return 0
    
    def __str__(self) -> str:
        """String reprezentacija strategije."""
        return f"{self.strategy_name} (priority: {self.priority})"
    
    def __repr__(self) -> str:
        """Debug reprezentacija strategije."""
        return f"<{self.__class__.__name__}: {self.strategy_name}>"
