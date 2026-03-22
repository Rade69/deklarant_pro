"""
Validation Cache - Caching rezultata validacije
"""

from typing import Dict, Optional, List
from services.validation_service import ValidationResult


class ValidationCache:
    """Cache za rezultate validacije da se ne bi stalno ponavljali"""

    def __init__(self):
        self._cache: Dict[int, ValidationResult] = {}
        self._error_count: int = 0
        self._warning_count: int = 0
        self._valid_count: int = 0

    def set(self, row: int, result: ValidationResult) -> None:
        """Postavi rezultat validacije za red"""
        old_result = self._cache.get(row)

        # Ažuriraj countere
        if old_result:
            if old_result.has_blocking_errors():
                self._error_count -= 1
            elif len(old_result.warnings) > 0:
                self._warning_count -= 1
            elif old_result.valid:
                self._valid_count -= 1

        if result.has_blocking_errors():
            self._error_count += 1
        elif len(result.warnings) > 0:
            self._warning_count += 1
        elif result.valid:
            self._valid_count += 1

        self._cache[row] = result

    def get(self, row: int) -> Optional[ValidationResult]:
        """Dobij rezultat validacije za red"""
        return self._cache.get(row)

    def clear(self) -> None:
        """Očisti cache"""
        self._cache.clear()
        self._error_count = 0
        self._warning_count = 0
        self._valid_count = 0

    def get_error_count(self) -> int:
        """Dobij broj grešaka"""
        return self._error_count

    def get_warning_count(self) -> int:
        """Dobij broj upozorenja"""
        return self._warning_count

    def get_valid_count(self) -> int:
        """Dobij broj validnih stavki"""
        return self._valid_count

    def get_total_count(self) -> int:
        """Dobij ukupan broj stavki u cache-u"""
        return len(self._cache)

    def invalidate_row(self, row: int) -> None:
        """Invalidiraj jedan red (izbriši iz cache-a)"""
        if row in self._cache:
            result = self._cache[row]
            if result.has_blocking_errors():
                self._error_count -= 1
            elif len(result.warnings) > 0:
                self._warning_count -= 1
            elif result.valid:
                self._valid_count -= 1
            del self._cache[row]

    def invalidate_all(self) -> None:
        """Invalidiraj sve redove"""
        self._cache.clear()
        self._error_count = 0
        self._warning_count = 0
        self._valid_count = 0
