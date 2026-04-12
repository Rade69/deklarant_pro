# services/error_handler.py

from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass
import logging
import traceback

from .exceptions import (
    PDFParseError,
    XLSParseError,
    DatabaseConnectionError,
    DatabaseQueryError,
    MissingRequiredFieldError,
    InvalidDataFormatError,
    XMLValidationError,
)

# Import InvoiceLine kao FakturaItem za kompatibilnost
from core.draft.draft import InvoiceLine as FakturaItem

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Tri nivoa težine greške"""

    RECOVERABLE = "recoverable"  # App nastavlja normalno
    USER_ACTION = "user_action"  # Korisnik mora odlučiti
    FATAL = "fatal"  # App se mora zatvoriti


@dataclass
class ErrorResponse:
    """Strukturirani odgovor na grešku"""

    severity: ErrorSeverity
    message: str  # User-friendly poruka
    technical_details: str  # Stack trace, debug info
    action: str = ""  # Šta korisnik može uraditi
    retry_callback: Optional[Callable] = None  # Funkcija za retry


class ErrorHandler:
    """Centralni error handling"""

    def handle_import_error(self, e: Exception, context: dict) -> ErrorResponse:
        """
        Rukovanje greškama pri import-u (PDF/XLS/XML)

        Args:
            e: Exception koja se desila
            context: Kontekst (filename, page number, etc.)

        Returns:
            ErrorResponse sa uputstvima kako dalje
        """

        # Log svaku grešku
        logger.error(f"Import error: {type(e).__name__} | Context: {context}", exc_info=True)

        # FileNotFoundError
        if isinstance(e, FileNotFoundError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=f"Fajl nije pronađen:\n{context.get('filename', 'Unknown')}",
                technical_details=str(e),
                action="Odaberite postojeći fajl",
            )

        # ParseError (PDF/XLS corrupt)
        if isinstance(e, (PDFParseError, XLSParseError)):
            return ErrorResponse(
                severity=ErrorSeverity.RECOVERABLE,
                message=(
                    f"Greška u parsiranju fajla na stranici {context.get('page', '?')}\n"
                    f"Fajl je možda oštećen ili neočekivanog formata."
                ),
                technical_details=traceback.format_exc(),
                action=(
                    "1. Preskočiti problematičnu stranicu?\n"
                    "2. Otkazati import?\n"
                    "3. Pokušati ponovo?"
                ),
                retry_callback=context.get("retry_func"),
            )

        # PermissionError
        if isinstance(e, PermissionError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=(
                    "Nemate dozvolu za pristup fajlu.\n"
                    "Fajl je možda otvoren u drugoj aplikaciji."
                ),
                technical_details=str(e),
                action="Zatvorite fajl u drugim aplikacijama i pokušajte ponovo",
            )

        # MemoryError (prevelik fajl)
        if isinstance(e, MemoryError):
            return ErrorResponse(
                severity=ErrorSeverity.FATAL,
                message=(
                    "Fajl je prevelik za obradu.\n" "Aplikaciji je ponestalo memorije."
                ),
                technical_details=str(e),
                action="Pokušajte sa manjim fajlom ili zatvorite druge aplikacije",
            )

        # Unknown error
        return ErrorResponse(
            severity=ErrorSeverity.FATAL,
            message=f"Neočekivana greška: {type(e).__name__}",
            technical_details=traceback.format_exc(),
            action="Kontaktirajte podršku sa logom greške",
        )

    def handle_database_error(self, e: Exception, operation: str) -> ErrorResponse:
        """
        Rukovanje greškama sa bazom podataka

        Args:
            e: Database exception
            operation: Šta se pokušavalo (query, insert, update)
        """

        logger.error(f"Database error during {operation}", exc_info=True)

        # Connection error
        if isinstance(e, DatabaseConnectionError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=(
                    "Nema konekcije sa bazom podataka.\n"
                    "Provjerite internet konekciju ili server status."
                ),
                technical_details=str(e),
                action=(
                    "1. Provjerite konekciju\n"
                    "2. Kontaktirajte IT\n"
                    "3. Nastaviti u offline modu?"
                ),
            )

        # Query error (bad SQL, constraints)
        if isinstance(e, DatabaseQueryError):
            return ErrorResponse(
                severity=ErrorSeverity.RECOVERABLE,
                message=f"Greška pri {operation}",
                technical_details=str(e),
                action="Pokušajte ponovo ili kontaktirajte podršku",
            )

        # Unknown DB error
        return ErrorResponse(
            severity=ErrorSeverity.FATAL,
            message=f"Kritična greška sa bazom: {type(e).__name__}",
            technical_details=traceback.format_exc(),
            action="Zatvorite aplikaciju i kontaktirajte podršku",
        )

    def handle_transformation_error(
        self, e: Exception, item_index: int, item: FakturaItem
    ) -> ErrorResponse:
        """
        Rukovanje greškama pri transformaciji Faktura → Naimenovanje

        Args:
            e: Exception
            item_index: Index problematične stavke
            item: Stavka koja je izazvala grešku
        """

        logger.error(
            f"Transformation error at item {item_index}",
            exc_info=True,
        )

        # Missing required field
        if isinstance(e, MissingRequiredFieldError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=(
                    f"Stavka #{item_index + 1} nema obavezno polje: {e.field_name}\n"
                    f"Opis: {item.naziv}"
                ),
                technical_details=str(e),
                action=(
                    "1. Popunite polje i pokušajte ponovo\n"
                    "2. Preskočite ovu stavku\n"
                    "3. Otkazati transformaciju"
                ),
            )

        # Invalid data format
        if isinstance(e, InvalidDataFormatError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=(
                    f"Stavka #{item_index + 1} ima nevažeće podatke: {e.field_name}\n"
                    f"Vrijednost: '{e.value}'\n"
                    f"Očekivani format: {e.expected_format}"
                ),
                technical_details=str(e),
                action="Ispravite podatke ili preskočite stavku",
            )

        # Unknown transformation error
        return ErrorResponse(
            severity=ErrorSeverity.RECOVERABLE,
            message=f"Greška pri obradi stavke #{item_index + 1}",
            technical_details=traceback.format_exc(),
            action="Preskočiti stavku ili otkazati?",
        )

    def handle_xml_export_error(self, e: Exception, draft) -> ErrorResponse:
        """Rukovanje greškama pri XML export-u"""

        logger.error("XML export error", exc_info=True)

        # Validation error
        if isinstance(e, XMLValidationError):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message=(
                    "XML nije validan prema ASYCUDA šemi.\n"
                    f"Greška: {e.validation_errors}"
                ),
                technical_details=str(e),
                action="Ispravite podatke i pokušajte ponovo",
            )

        # File write error
        if isinstance(e, (IOError, PermissionError)):
            return ErrorResponse(
                severity=ErrorSeverity.USER_ACTION,
                message="Ne mogu zapisati XML fajl",
                technical_details=str(e),
                action="Provjerite dozvole ili odaberite drugu lokaciju",
            )

        # Unknown export error
        return ErrorResponse(
            severity=ErrorSeverity.FATAL,
            message="Kritična greška pri XML export-u",
            technical_details=traceback.format_exc(),
            action="Sačuvajte draft i kontaktirajte podršku",
        )


# Global error handler instance
error_handler = ErrorHandler()
