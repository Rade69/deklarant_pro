import logging
logger = logging.getLogger(__name__)
# importers/exceptions.py

"""
Custom Exception Hierarchy for Import System

Ovaj modul definiše hijerarhiju custom exception-a za import sistem.
Omogućava precizno rukovanje različitim vrstama grešaka tokom import-a.

Primjer korišćenja:
    from importers.exceptions import (
        ImportError,
        FileNotSupportedError,
        ValidationError
    )
    
    try:
        result = strategy.import_file(filepath)
    except FileNotSupportedError as e:
        logger.debug(f"Fajl nije podržan: {e}")
    except ValidationError as e:
        logger.debug(f"Validacija nije prošla: {e}")
    except ImportError as e:
        logger.debug(f"Greška pri import-u: {e}")
"""


# ============================================================
# BAZNI EXCEPTION
# ============================================================

class ImportError(Exception):
    """
    Bazni exception za sve import greške.
    
    Svi custom exception-i za import sistem treba da naslijede
    ovu klasu radi lakšeg hvatanja i rukovanja greškama.
    
    Primjer:
        try:
            importer.import_file(path)
        except ImportError as e:
            logger.error(f"Import greška: {e}")
    """
    pass


# ============================================================
# FILE FORMAT EXCEPTIONS
# ============================================================

class FileNotSupportedError(ImportError):
    """
    Format fajla nije podržan.
    
    Podiže se kada pokušate importovati fajl čiji format
    nijedna registrovana strategija ne podržava.
    
    Primjer:
        >>> raise FileNotSupportedError("faktura.xyz")
        FileNotSupportedError: Format fajla nije podržan: faktura.xyz
    """
    pass


class ImportDetectionError(ImportError):
    """
    Nije moguće detektovati tip fajla.
    
    Podiže se kada sistem ne može utvrditi o kom tipu fajla
    se radi (npr. fajl nema ekstenziju ili je ekstenzija
    nejasna).
    
    Primjer:
        >>> raise ImportDetectionError("Nema ekstenzije")
        ImportDetectionError: Nije moguće detektovati tip fajla: Nema ekstenzije
    """
    pass


class UnsupportedInvoiceFormatError(ImportError):
    """
    Format fakture je prepoznat ali nije podržan.
    
    Podiže se kada je format fajla validan (npr. PDF, Excel)
    ali struktura ili šablon fakture unutar tog formata
    nije podržan od strane dostupnih strategija.
    
    Primjer:
        >>> raise UnsupportedInvoiceFormatError("Faktura bez JIB-a")
        UnsupportedInvoiceFormatError: Format fakture nije podržan: Faktura bez JIB-a
    """
    pass


# ============================================================
# PARSING & VALIDATION EXCEPTIONS
# ============================================================

class ParseError(ImportError):
    """
    Greška pri parsiranju sadržaja fajla.
    
    Podiže se kada dođe do greške tokom čitanja ili parsiranja
    podataka iz fajla (npr. nevalidan XML, pokvaren Excel,
    nečitak PDF).
    
    Primjer:
        >>> raise ParseError("Excel fajl je oštećen")
        ParseError: Greška pri parsiranju: Excel fajl je oštećen
    """
    pass


class ValidationError(ImportError):
    """
    Importovani podaci nisu prošli validaciju.
    
    Podiže se kada su podaci uspješno ekstrahovani iz fajla
    ali ne zadovoljavaju validaciona pravila (npr. nedostaju
    obavezna polja, nevalidan JIB, negativne vrijednosti).
    
    Atributi:
        field: Naziv polja koje nije validno (opciono)
        value: Vrijednost koja nije validna (opciono)
        message: Opis greške
    
    Primjer:
        >>> raise ValidationError("JIB je obavezan", field="jib", value=None)
        ValidationError: JIB je obavezan
    """
    
    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: object | None = None
    ):
        """
        Inicijalizuj ValidationError.
        
        Args:
            message: Opis greške
            field: Naziv polja koje nije validno (opciono)
            value: Vrijednost koja nije validna (opciono)
        """
        super().__init__(message)
        self.field = field
        self.value = value
        self.message = message
    
    def __str__(self) -> str:
        """String reprezentacija sa detaljima."""
        if self.field:
            return f"{self.message} (polje: {self.field})"
        return self.message


# ============================================================
# WARNINGS
# ============================================================

class PartialImportWarning(Warning):
    """
    Dio podataka je importovan ali sa upozorenjima.
    
    Ovo je Warning (ne Exception) - koristi se za situacije
    gdje je import djelimično uspio ali postoje problemi sa
    nekim podacima koji ne blokiraju cijeli proces.
    
    Atributi:
        imported_count: Broj uspješno importovanih stavki
        skipped_count: Broj preskočenih stavki
        warnings: Lista opisa upozorenja
    
    Primjer:
        >>> warnings.warn(
        ...     PartialImportWarning(
        ...         imported_count=10,
        ...         skipped_count=2,
        ...         warnings=["Stavka 3: nedostaje šifra"]
        ...     )
        ... )
    """
    
    def __init__(
        self,
        message: str = "Dio podataka je importovan sa upozorenjima",
        imported_count: int = 0,
        skipped_count: int = 0,
        warnings: list[str] | None = None
    ):
        """
        Inicijalizuj PartialImportWarning.
        
        Args:
            message: Opis upozorenja
            imported_count: Broj uspješno importovanih stavki
            skipped_count: Broj preskočenih stavki
            warnings: Lista detaljnih opisa upozorenja
        """
        super().__init__(message)
        self.imported_count = imported_count
        self.skipped_count = skipped_count
        self.warnings = warnings or []
    
    def __str__(self) -> str:
        """String reprezentacija sa statistikom."""
        parts = [
            self.args[0],
            f"Importovano: {self.imported_count}",
            f"Preskočeno: {self.skipped_count}"
        ]
        if self.warnings:
            parts.append(f"Upozorenja: {len(self.warnings)}")
        return " | ".join(parts)
