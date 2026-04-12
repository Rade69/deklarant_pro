# services/exceptions.py
"""
Custom exception klase za services
"""


# ============================================================
# VALIDATION EXCEPTIONS
# ============================================================

class ValidationError(Exception):
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
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.field:
            return f"{self.message} (polje: {self.field})"
        return self.message


# ============================================================
# IMPORT/PARSE ERRORS
# ============================================================


# Import/Parse errors
class PDFParseError(Exception):
    """Greška pri parsiranju PDF fajla"""

    pass


class XLSParseError(Exception):
    """Greška pri parsiranju Excel fajla"""

    pass


# Database errors
class DatabaseConnectionError(Exception):
    """Greška pri konekciji sa bazom"""

    pass


class DatabaseQueryError(Exception):
    """Greška pri izvršavanju SQL query-ja"""

    pass


# Transformation errors
class MissingRequiredFieldError(Exception):
    """Obavezno polje nedostaje"""

    def __init__(self, field_name: str):
        self.field_name = field_name
        super().__init__(f"Missing required field: {field_name}")


class InvalidDataFormatError(Exception):
    """Podatak nije u očekivanom formatu"""

    def __init__(self, field_name: str, value: str, expected_format: str):
        self.field_name = field_name
        self.value = value
        self.expected_format = expected_format
        super().__init__(
            f"Invalid format for {field_name}: '{value}', expected: {expected_format}"
        )


# XML Export errors
class XMLValidationError(Exception):
    """XML nije validan prema šemi"""

    def __init__(self, validation_errors: list):
        self.validation_errors = validation_errors
        super().__init__(f"XML validation failed: {validation_errors}")
