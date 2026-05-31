# importers/strategies/xml_strategy.py

"""
XML Import Strategy

Strategija za import XML (ASYCUDA) deklaracija.
Koristi postojeći XMLImporter.
"""

from pathlib import Path
from typing import Optional, Callable, Union, List, Dict, Any

from importers.base_strategy import ImportStrategy
from importers.import_result import ImportResult
from importers.exceptions import ParseError, FileNotSupportedError
from core.draft.draft import InvoiceLine

class XMLImportStrategy(ImportStrategy):
    """
    Strategija za import XML (ASYCUDA) deklaracija.
    
    Koristi postojeći XMLImporter za parsiranje ASYCUDA XML formata.
    XML format se koristi za razmjenu podataka sa ASYCUDA sistemom.
    
    Primjer:
        >>> strategy = XMLImportStrategy()
        >>> result = strategy.import_file(
        ...     Path("deklaracija.xml"),
        ...     progress_callback=lambda p: print(f"{p}%")
        ... )
        >>> len(result.items)
        15
    """
    
    def __init__(self):
        """
        Inicijalizuj XML strategiju.

        Kreira instancu XMLImporter (lazy import da se izbjegne circular dependency).
        """
        from importers.xml_importer import XMLImporter
        self.importer = XMLImporter()
    
    def can_handle(self, filepath: Path) -> bool:
        """
        Provjeri da li je fajl XML.
        
        Args:
            filepath: Putanja do fajla za provjeru
        
        Returns:
            True ako fajl ima .xml ekstenziju (case-insensitive)
        
        Primjer:
            >>> strategy = XMLImportStrategy()
            >>> strategy.can_handle(Path("deklaracija.xml"))
            True
            >>> strategy.can_handle(Path("deklaracija.XML"))
            True
            >>> strategy.can_handle(Path("faktura.xlsx"))
            False
        """
        return filepath.suffix.lower() == ".xml"
    
    def import_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[List[InvoiceLine], ImportResult]:
        """
        Importuj XML fajl koristeći XMLImporter.
        
        Ova metoda:
        1. Validira da fajl postoji
        2. Poziva XMLImporter.import_file()
        3. Konvertuje rezultat u ImportResult
        4. Opciono javlja progress (50% prije, 100% poslije)
        
        Args:
            filepath: Putanja do XML fajla za import
            progress_callback: Opcioni callback za progress (0-100).
                               Poziva se sa 50% prije parsiranja i
                               100% nakon uspješnog parsiranja.
        
        Returns:
            ImportResult objekat koji sadrži:
            - items: Lista InvoiceLine objekata iz XML-a
            - header: Metapodaci deklaracije (broj, datum, itd.)
            - Ostala polja iz XML-a
        
        Raises:
            FileNotSupportedError: Ako fajl nije XML
            ParseError: Ako parsiranje ne uspije ili je XML nevalidan
        
        Primjer:
            >>> strategy = XMLImportStrategy()
            >>> result = strategy.import_file(Path("deklaracija.xml"))
            >>> print(f"Importovano {len(result.items)} stavki")
            Importovano 15 stavki
        """
        # Validacija ekstenzije
        if not self.can_handle(filepath):
            raise FileNotSupportedError(
                f"XML strategija ne može procesirati: {filepath.suffix}"
            )
        
        # Validacija da fajl postoji
        if not filepath.exists():
            raise ParseError(f"Fajl ne postoji: {filepath}")
        
        try:
            # Javi 50% progress prije parsiranja
            if progress_callback:
                progress_callback(50)

            # Univerzalni faktura XML parser (<Faktura>/<Stavke>)
            # Radi sa Pekabesko, Medicopharm, i bilo kojim drugim dobavljačem
            from importers.faktura_xml_parser import detect_faktura_xml, parse_faktura_xml
            if detect_faktura_xml(str(filepath)):
                result = parse_faktura_xml(str(filepath))
                if progress_callback:
                    progress_callback(100)
                return result

            # Standardni ASYCUDA XML format
            data = self.importer.import_file(filepath)

            # Javi 100% progress nakon parsiranja
            if progress_callback:
                progress_callback(100)

            # Konvertuj dictionary u ImportResult
            result = self._convert_to_import_result(data)

            return result
            
        except FileNotSupportedError:
            # Re-raise FileNotSupportedError without wrapping
            raise
        except Exception as e:
            # Wrapuj sve ostale greške u ParseError
            raise ParseError(f"XML import failed: {e}") from e
    
    def _convert_to_import_result(
        self,
        data: Dict[str, Any]
    ) -> ImportResult:
        """
        Konvertuj dictionary iz XML import-a u ImportResult.
        
        Args:
            data: Dictionary sa podacima iz XMLImporter
        
        Returns:
            ImportResult objekat sa parsiranim podacima
        """
        items = data.get('items', [])
        header = data.get('header', {})
        
        return ImportResult(
            items=items,
            bruto_kg=float(header.get('bruto_kg', 0) or 0),
            neto_kg=float(header.get('neto_kg', 0) or 0),
            invoice_name=header.get('broj_deklaracije', ''),
            currency=header.get('valuta', 'EUR'),
            import_type='xml',
            has_origin_statement=header.get('has_origin_statement', False)
        )
    
    @property
    def strategy_name(self) -> str:
        """
        Ime strategije za logging i UI prikaz.
        
        Returns:
            "XML Import"
        """
        return "XML Import"
    
    @property
    def priority(self) -> int:
        """
        Prioritet strategije.
        
        XML strategija ima srednji prioritet (5) jer je
        XML format rjeđi od PDF/Excel u svakodnevnom radu.
        
        Returns:
            5 (srednji prioritet)
        """
        return 5
    
    def __str__(self) -> str:
        """String reprezentacija strategije."""
        return f"{self.strategy_name} (priority: {self.priority})"
    
    def __repr__(self) -> str:
        """Debug reprezentacija strategije."""
        return f"<{self.__class__.__name__}: {self.strategy_name}>"
