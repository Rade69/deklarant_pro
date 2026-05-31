# importers/strategies/pdf_strategy.py

"""
PDF Import Strategy

Strategija za import PDF faktura koristeći Smart PDF Parser.
Ovo je wrapper oko postojećeg smart_pdf_importer modula.
"""

from pathlib import Path
from typing import Optional, Callable, Union, List

from importers.base_strategy import ImportStrategy
from importers.import_result import ImportResult
from importers.exceptions import ParseError, FileNotSupportedError
from core.draft.draft import InvoiceLine


# Lazy import parse_smart_pdf (da se izbjegne pdfplumber dependency error)
def _get_smart_pdf_parser():
    """
    Lazy import parse_smart_pdf funkcije.
    
    Ovo omogućava da se strategija učita čak i ako pdfplumber
    nije instaliran - greška će se desiti tek pri pokušaju
    stvarnog import-a PDF-a.
    """
    from importers.smart_pdf_importer import parse_smart_pdf
    return parse_smart_pdf


class PDFImportStrategy(ImportStrategy):
    """
    Strategija za import PDF faktura.
    
    Koristi postojeći SmartPDFImporter (parse_smart_pdf funkciju)
    za parsiranje PDF fakura. Automatski detektuje format fakture
    (Blagić, IMAMOGLU, Master Frigo, itd.) i koristi odgovarajući
    parser.
    
    Primjer:
        >>> strategy = PDFImportStrategy()
        >>> result = strategy.import_file(
        ...     Path("faktura.pdf"),
        ...     progress_callback=lambda p: print(f"{p}%")
        ... )
        >>> len(result.items)
        15
    """
    
    def __init__(self):
        """
        Inicijalizuj PDF strategiju.
        
        Kreira instancu internog parsera (nije potrebno - koristimo
        module-level funkciju parse_smart_pdf).
        """
        pass
    
    def can_handle(self, filepath: Path) -> bool:
        """
        Provjeri da li je fajl PDF.
        
        Args:
            filepath: Putanja do fajla za provjeru
        
        Returns:
            True ako fajl ima .pdf ekstenziju (case-insensitive)
        
        Primjer:
            >>> strategy = PDFImportStrategy()
            >>> strategy.can_handle(Path("faktura.pdf"))
            True
            >>> strategy.can_handle(Path("faktura.PDF"))
            True
            >>> strategy.can_handle(Path("faktura.xlsx"))
            False
        """
        return filepath.suffix.lower() == ".pdf"
    
    def import_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[List[InvoiceLine], ImportResult]:
        """
        Importuj PDF fajl koristeći Smart PDF Parser.
        
        Ova metoda:
        1. Validira da fajl postoji
        2. Poziva parse_smart_pdf funkciju
        3. Opciono javlja progress (50% prije, 100% poslije)
        4. Vraća ImportResult sa parsiranim stavkama
        
        Args:
            filepath: Putanja do PDF fajla za import
            progress_callback: Opcioni callback za progress (0-100).
                               Poziva se sa 50% prije parsiranja i
                               100% nakon uspješnog parsiranja.
        
        Returns:
            ImportResult objekat koji sadrži:
            - items: Lista InvoiceLine objekata
            - bruto_kg, neto_kg: Težine
            - invoice_name: Broj/ime fakture
            - currency: Valuta
            - has_origin_statement: Da li sadrži izjavu o poreklu
        
        Raises:
            FileNotSupportedError: Ako fajl nije PDF
            ParseError: Ako parsiranje ne uspije
        
        Primjer:
            >>> strategy = PDFImportStrategy()
            >>> result = strategy.import_file(Path("faktura.pdf"))
            >>> print(f"Importovano {len(result.items)} stavki")
            Importovano 15 stavki
        """
        # Validacija ekstenzije
        if not self.can_handle(filepath):
            raise FileNotSupportedError(
                f"PDF strategija ne može procesirati: {filepath.suffix}"
            )
        
        # Validacija da fajl postoji
        if not filepath.exists():
            raise ParseError(f"Fajl ne postoji: {filepath}")
        
        try:
            # Javi 50% progress prije parsiranja
            if progress_callback:
                progress_callback(50)
            
            # Lazy import parse_smart_pdf funkcije
            parse_smart_pdf = _get_smart_pdf_parser()
            
            # Pozovi smart PDF parser
            result = parse_smart_pdf(str(filepath))
            
            # Javi 100% progress nakon parsiranja
            if progress_callback:
                progress_callback(100)
            
            return result
            
        except FileNotSupportedError:
            # Re-raise FileNotSupportedError without wrapping
            raise
        except Exception as e:
            # Wrapuj sve ostale greške u ParseError
            raise ParseError(f"PDF import failed: {e}") from e
    
    @property
    def strategy_name(self) -> str:
        """
        Ime strategije za logging i UI prikaz.
        
        Returns:
            "PDF Import"
        """
        return "PDF Import"
    
    @property
    def priority(self) -> int:
        """
        Prioritet strategije.
        
        PDF strategija ima viši prioritet (10) od generic
        strategija (0) jer je specijalizovana za PDF format.
        
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
