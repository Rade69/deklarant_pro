# importers/strategies/excel_strategy.py

"""
Excel Import Strategy

Strategija za import Excel (.xlsx, .xls, .xlsm) faktura.
Koristi postojeći ExcelImporter sa automatskom detekcijom formata.
"""

from pathlib import Path
from typing import Optional, Callable, Union, List

from importers.base_strategy import ImportStrategy
from importers.import_result import ImportResult
from importers.exceptions import ParseError, FileNotSupportedError
from core.draft.draft import InvoiceLine


# Lazy import ExcelImporter (da se izbjegne dependency error)
def _get_excel_importer():
    """
    Lazy import ExcelImporter klase.
    
    Ovo omogućava da se strategija učita čak i ako postoje
    dependency problemi - greška će se desiti tek pri pokušaju
    stvarnog import-a Excel-a.
    """
    from importers.excel_importer import ExcelImporter
    return ExcelImporter()


class ExcelImportStrategy(ImportStrategy):
    """
    Strategija za import Excel fakura.
    
    Koristi postojeći ExcelImporter koji podržava:
    - Obične Excel fakture (.xlsx, .xls, .xlsm)
    - Specijalizovane formate (Blagić-Loren, itd.)
    - Auto-detekciju header-a i kolona
    
    Primjer:
        >>> strategy = ExcelImportStrategy()
        >>> result = strategy.import_file(
        ...     Path("faktura.xlsx"),
        ...     progress_callback=lambda p: print(f"{p}%")
        ... )
        >>> len(result.items)
        15
    """
    
    def __init__(self):
        """
        Inicijalizuj Excel strategiju.
        
        Napomena: ExcelImporter se kreira lazy (tek pri import_file).
        """
        self.__dict__['_importer'] = None
    
    def can_handle(self, filepath: Path) -> bool:
        """
        Provjeri da li je fajl Excel format.
        
        Args:
            filepath: Putanja do fajla za provjeru
        
        Returns:
            True ako fajl ima .xlsx, .xls, ili .xlsm ekstenziju
            (case-insensitive)
        
        Primjer:
            >>> strategy = ExcelImportStrategy()
            >>> strategy.can_handle(Path("faktura.xlsx"))
            True
            >>> strategy.can_handle(Path("faktura.XLS"))
            True
            >>> strategy.can_handle(Path("faktura.pdf"))
            False
        """
        suffix = filepath.suffix.lower()
        return suffix in [".xlsx", ".xls", ".xlsm"]
    
    @property
    def _importer(self):
        """Lazy initialization of ExcelImporter."""
        if self.__dict__.get('_importer') is None:
            self.__dict__['_importer'] = _get_excel_importer()
        return self.__dict__['_importer']
    
    def import_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[List[InvoiceLine], ImportResult]:
        """
        Importuj Excel fajl koristeći ExcelImporter.
        
        Ova metoda:
        1. Validira da fajl postoji
        2. Poziva ExcelImporter.import_excel()
        3. Opciono javlja progress (50% prije, 100% poslije)
        4. Vraća ImportResult ili List[InvoiceLine]
        
        Args:
            filepath: Putanja do Excel fajla za import
            progress_callback: Opcioni callback za progress (0-100).
                               Poziva se sa 50% prije parsiranja i
                               100% nakon uspješnog parsiranja.
        
        Returns:
            ImportResult ili List[InvoiceLine] zavisno od formata:
            - ImportResult: Za specijalizovane formate (Blagić-Loren)
            - List[InvoiceLine]: Za obične Excel fakture
        
        Raises:
            FileNotSupportedError: Ako fajl nije Excel format
            ParseError: Ako parsiranje ne uspije
        
        Primjer:
            >>> strategy = ExcelImportStrategy()
            >>> result = strategy.import_file(Path("faktura.xlsx"))
            >>> print(f"Importovano {len(result.items)} stavki")
            Importovano 15 stavki
        """
        # Validacija ekstenzije
        if not self.can_handle(filepath):
            raise FileNotSupportedError(
                f"Excel strategija ne može procesirati: {filepath.suffix}"
            )
        
        # Validacija da fajl postoji
        if not filepath.exists():
            raise ParseError(f"Fajl ne postoji: {filepath}")
        
        try:
            # Javi 50% progress prije parsiranja
            if progress_callback:
                progress_callback(50)
            
            # Pozovi Excel importer (lazy init)
            result = self._importer.import_excel(str(filepath), progress_callback)
            
            # Javi 100% progress nakon parsiranja
            if progress_callback:
                progress_callback(100)
            
            return result
            
        except FileNotSupportedError:
            # Re-raise FileNotSupportedError without wrapping
            raise
        except Exception as e:
            # Wrapuj sve ostale greške u ParseError
            raise ParseError(f"Excel import failed: {e}") from e
    
    @property
    def strategy_name(self) -> str:
        """
        Ime strategije za logging i UI prikaz.
        
        Returns:
            "Excel Import"
        """
        return "Excel Import"
    
    @property
    def priority(self) -> int:
        """
        Prioritet strategije.
        
        Excel strategija ima viši prioritet (10) od generic
        strategija (0) jer je specijalizovana za Excel formate.
        
        Returns:
            10 (viši prioritet)
        """
        return 10
    
    def __str__(self) -> str:
        """String reprezentacija strategije."""
        return f"{self.strategy_name} (priority: {self.priority})"
    
    def __repr__(self) -> str:
        """Debug reprezentacija strategije."""
        return f"<{self.__class__.__name__}: {self.strategy_name}>"
