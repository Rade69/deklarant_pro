# services/base_service.py

"""
Base Service Class za Business Logic Services

Sadrži common funkcionalnost za sve business logic services.
Osigurava konzistentan interfejs za validaciju, logging i error handling.

Primjer korišćenja:
    class ZaglavljeService(BaseTabService):
        def validate(self, data: Dict[str, Any]) -> bool:
            if not data.get('broj_deklaracije'):
                raise ValidationError("Broj deklaracije je obavezan")
            return True
        
        def save_zaglavlje(self, data: Dict[str, Any]) -> bool:
            self.validate(data)
            # DB operations...
            self._log_operation("save_zaglavlje", success=True)
            return True
"""

import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


# ============================================================
# VALIDATION EXCEPTION
# ============================================================

class ValidationError(Exception):
    """
    Exception za validacione greške.
    
    Atributi:
        message: Opis greške
        field: Naziv polja koje nije validno (opciono)
        value: Vrijednost koja nije validna (opciono)
    
    Primjer:
        >>> raise ValidationError("Polje je obavezno", field="broj_deklaracije")
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None
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
# BASE SERVICE CLASS
# ============================================================

class BaseTabService(ABC):
    """
    Bazna klasa za tab services.
    
    Odgovornosti:
    - Business logika
    - Validacija podataka
    - Database operacije
    - XML/JSON import/export
    - Data transformacije
    
    NEMA:
    - Qt zavisnosti (bez QWidget, Signal, itd.)
    - UI logike
    - GUI event handling-a
    
    Potpuno je nezavisan od GUI-a i može se koristiti iz:
    - GUI controller-a
    - CLI skripti
    - API endpoint-a
    - Background worker-a
    
    Primjer:
        class ZaglavljeService(BaseTabService):
            def __init__(self):
                super().__init__()
            
            def validate(self, data):
                if not data.get('broj_deklaracije'):
                    raise ValidationError("Broj je obavezan")
                return True
            
            def save(self, data):
                self.validate(data)
                # DB operations...
                return True
    """
    
    # ============================================================
    # INIT
    # ============================================================
    
    def __init__(self):
        """
        Inicijalizuj base service.
        
        Postavlja logger sa nazivom klase.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
    
    # ============================================================
    # ABSTRACT METHODS (Subclass must implement)
    # ============================================================
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validiraj podatke.
        
        Args:
            data: Podaci za validaciju
        
        Returns:
            True ako su podaci validni
        
        Raises:
            ValidationError: Ako validacija ne prođe
        
        Primjer:
            >>> service.validate({'broj': '123'})
            True
            >>> service.validate({'broj': ''})
            ValidationError: Broj je obavezan
        """
        raise NotImplementedError("Subclass must implement validate()")
    
    # ============================================================
    # LOGGING HELPERS
    # ============================================================
    
    def _log_operation(
        self,
        operation: str,
        success: bool = True,
        details: Optional[str] = None
    ) -> None:
        """
        Loguj operaciju.
        
        Args:
            operation: Naziv operacije
            success: Da li je operacija uspješna
            details: Optional dodatni detalji
        
        Primjer:
            >>> self._log_operation("save_zaglavlje", success=True)
            >>> self._log_operation("import_xml", success=False, details="Invalid format")
        """
        if success:
            self.logger.info(f"✅ {operation} - uspješno")
            if details:
                self.logger.debug(f"   Details: {details}")
        else:
            self.logger.error(f"❌ {operation} - neuspješno")
            if details:
                self.logger.error(f"   Details: {details}")
    
    def _log_debug(self, message: str) -> None:
        """
        Loguj debug poruku.
        
        Args:
            message: Poruka za logovanje
        
        Primjer:
            >>> self._log_debug(f"Processing {len(items)} items")
        """
        self.logger.debug(message)
    
    def _log_info(self, message: str) -> None:
        """
        Loguj info poruku.
        
        Args:
            message: Poruka za logovanje
        
        Primjer:
            >>> self._log_info(f"Starting import from {filepath}")
        """
        self.logger.info(message)
    
    def _log_warning(self, message: str) -> None:
        """
        Loguj warning poruku.
        
        Args:
            message: Poruka za logovanje
        
        Primjer:
            >>> self._log_warning(f"Field '{field}' is empty, using default")
        """
        self.logger.warning(message)
    
    def _log_error(self, message: str, exc: Optional[Exception] = None) -> None:
        """
        Loguj error poruku.
        
        Args:
            message: Poruka za logovanje
            exc: Optional exception za stack trace
        
        Primjer:
            >>> self._log_error("Database connection failed", exc=e)
        """
        if exc:
            self.logger.error(f"{message}: {exc}", exc_info=True)
        else:
            self.logger.error(message)
    
    # ============================================================
    # VALIDATION HELPERS
    # ============================================================
    
    def _validate_required(
        self,
        data: Dict[str, Any],
        fields: List[str]
    ) -> None:
        """
        Validiraj obavezna polja.
        
        Args:
            data: Podaci za validaciju
            fields: Lista naziva obaveznih polja
        
        Raises:
            ValidationError: Ako neko obavezno polje nedostaje
        
        Primjer:
            >>> self._validate_required(data, ['broj', 'datum'])
        """
        for field in fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValidationError(f"Polje '{field}' je obavezno", field=field)
    
    def _validate_type(
        self,
        value: Any,
        expected_type: type,
        field_name: str
    ) -> None:
        """
        Validiraj tip podatka.
        
        Args:
            value: Vrijednost za validaciju
            expected_type: Očekivani tip
            field_name: Naziv polja
        
        Raises:
            ValidationError: Ako tip nije očekivani
        
        Primjer:
            >>> self._validate_type(broj, int, "broj_stavki")
        """
        if not isinstance(value, expected_type):
            raise ValidationError(
                f"Polje '{field_name}' mora biti tipa {expected_type.__name__}",
                field=field_name,
                value=value
            )
    
    def _validate_length(
        self,
        value: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        field_name: str = "value"
    ) -> None:
        """
        Validiraj dužinu stringa.
        
        Args:
            value: String za validaciju
            min_length: Minimalna dozvoljena dužina
            max_length: Maksimalna dozvoljena dužina
            field_name: Naziv polja
        
        Raises:
            ValidationError: Ako dužina nije u dozvoljenim granicama
        
        Primjer:
            >>> self._validate_length(broj, min_length=5, max_length=20, field_name="broj_deklaracije")
        """
        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                f"Polje '{field_name}' mora imati najmanje {min_length} karaktera",
                field=field_name,
                value=value
            )
        
        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"Polje '{field_name}' mora imati najviše {max_length} karaktera",
                field=field_name,
                value=value
            )
    
    # ============================================================
    # DATA TRANSFORMATION HELPERS
    # ============================================================
    
    def _normalize_string(self, value: str) -> str:
        """
        Normalizuj string (trim, uppercase/lowercase).
        
        Args:
            value: String za normalizaciju
        
        Returns:
            Normalizovani string
        
        Primjer:
            >>> self._normalize_string("  ABC  ")
            'abc'
        """
        if not value:
            return ""
        return value.strip().lower()
    
    def _parse_date(self, value: Any) -> Optional[Any]:
        """
        Parsiraj datum iz različitih formata.
        
        Args:
            value: Vrijednost za parsiranje (string, datetime, itd.)
        
        Returns:
            datetime objekat ili None
        
        Primjer:
            >>> self._parse_date("2024-01-01")
            datetime(2024, 1, 1)
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            from datetime import datetime
            # Try common formats
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValidationError(f"Nevalidan format datuma: {value}")
        
        return value
