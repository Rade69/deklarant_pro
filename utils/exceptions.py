# utils/exceptions.py
"""
Konsolidovane exception klase za cijelu aplikaciju.
"""

# ============================================================
# BASE EXCEPTIONS
# ============================================================

class AsycudaError(Exception):
    """Bazna exception klasa za ASYCUDA aplikaciju."""
    
    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ============================================================
# VALIDATION EXCEPTIONS
# ============================================================

class ValidationError(AsycudaError):
    """
    Greška pri validaciji podataka.
    
    Atributi:
        message: Opis greške
        field: Naziv polja koje nije validno (opciono)
        value: Vrijednost koja nije validna (opciono)
    """
    
    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: object | None = None
    ):
        self.field = field
        self.value = value
        super().__init__(message, f"field={field}, value={value}")
    
    def __str__(self) -> str:
        if self.field:
            return f"ValidationError: {self.message} (polje: {self.field})"
        return f"ValidationError: {self.message}"


class MissingRequiredFieldError(ValidationError):
    """Obavezno polje nedostaje."""
    
    def __init__(self, field_name: str):
        super().__init__(f"Obavezno polje '{field_name}' nedostaje", field=field_name)


class InvalidDataFormatError(ValidationError):
    """Podatak nije u očekivanom formatu."""
    
    def __init__(self, field_name: str, value: str, expected_format: str):
        super().__init__(
            f"Nevalidan format za polje '{field_name}': '{value}', očekivano: {expected_format}",
            field=field_name,
            value=value
        )


# ============================================================
# DATABASE EXCEPTIONS
# ============================================================

class DatabaseError(AsycudaError):
    """Bazna exception za database greške."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Greška pri konekciji sa bazom."""
    pass


class DatabaseQueryError(DatabaseError):
    """Greška pri izvršavanju SQL query-ja."""
    pass


# ============================================================
# IMPORT/PARSE EXCEPTIONS
# ============================================================

class ImportError(AsycudaError):
    """Bazna exception za import greške."""
    pass


class FileNotSupportedError(ImportError):
    """Fajl format nije podržan."""
    pass


class PDFParseError(ImportError):
    """Greška pri parsiranju PDF fajla."""
    pass


class XLSParseError(ImportError):
    """Greška pri parsiranju Excel fajla."""
    pass


class XMLParseError(ImportError):
    """Greška pri parsiranju XML fajla."""
    pass


# ============================================================
# EXPORT EXCEPTIONS
# ============================================================

class ExportError(AsycudaError):
    """Bazna exception za export greške."""
    pass


class XMLValidationError(ExportError):
    """XML nije validan prema šemi."""
    
    def __init__(self, validation_errors: list):
        self.validation_errors = validation_errors
        super().__init__(
            f"XML validacija nije uspjela",
            f"errors={validation_errors}"
        )


# ============================================================
# BUSINESS LOGIC EXCEPTIONS
# ============================================================

class BusinessLogicError(AsycudaError):
    """Greška u business logici."""
    pass


class DraftNotFoundError(BusinessLogicError):
    """Draft nije pronađen."""
    pass


class TariffNotFoundError(BusinessLogicError):
    """Tarifni broj nije pronađen."""
    pass


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def wrap_exception(exception: Exception, context: str) -> AsycudaError:
    """
    Wrap-uj generic exception u AsycudaError sa kontekstom.
    
    Args:
        exception: Originalni exception
        context: Kontekst u kojem se exception desio
    
    Returns:
        AsycudaError sa dodanim kontekstom
    """
    if isinstance(exception, AsycudaError):
        return exception
    
    return AsycudaError(
        f"{context}: {str(exception)}",
        details=f"Original exception: {type(exception).__name__}"
    )