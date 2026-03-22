# services/validation_service.py

from enum import Enum
from typing import List, Dict
from dataclasses import dataclass, field

# Import za kompatibilnost
from core.draft.draft import InvoiceLine as FakturaItem
from core.draft.naimenovanje import Naimenovanje as NaimenovanjeItem


class ValidationLevel(Enum):
    """Tri nivoa validacije"""

    WARNING = "warning"  # Može nastaviti, ali upozorenje
    ERROR = "error"  # Mora ispraviti prije nastavka
    CRITICAL = "critical"  # Blokira save/export kompletno


@dataclass
class ValidationError:
    """Pojedinačna greška"""

    level: ValidationLevel
    field: str  # Koje polje ima problem
    message: str  # Šta je problem
    suggestion: str = ""  # Kako ispraviti (opciono)


@dataclass
class ValidationResult:
    """Rezultat validacije cijelog objekta"""

    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    field_errors: Dict[str, str] = field(default_factory=dict)

    def has_blocking_errors(self) -> bool:
        """Da li ima grešaka koje blokiraju nastavak?"""
        return any(
            e.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
            for e in self.errors
        )


class FakturaItemValidator:
    """Validacija stavke fakture"""

    def validate(self, item) -> ValidationResult:
        """Validira jednu stavku (InvoiceLine from core.draft.draft)"""
        result = ValidationResult(valid=True, errors=[], warnings=[], field_errors={})

        # 1. OBAVEZNA POLJA (CRITICAL)
        if not item.naziv_robe or len(item.naziv_robe.strip()) == 0:
            result.valid = False
            result.errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    field="naziv_robe",
                    message="Naziv robe je obavezan",
                    suggestion="Unesite opis robe",
                )
            )

        if not item.tarifni_broj:
            result.valid = False
            result.errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    field="tarifni_broj",
                    message="Tarifni broj je obavezan",
                    suggestion="Unesite tarifni broj (8 ili 10 cifara)",
                )
            )

        # 2. FORMAT VALIDACIJA (ERROR)
        if item.tarifni_broj:
            if not self._is_valid_tariff_format(item.tarifni_broj):
                result.valid = False
                result.errors.append(
                    ValidationError(
                        level=ValidationLevel.ERROR,
                        field="tarifni_broj",
                        message=f"Tarifni broj '{item.tarifni_broj}' nije validan format",
                        suggestion="Format: 8 cifara (npr. 84818090) ili 10 cifara (npr. 8481809000)",
                    )
                )

        # 3. BUSINESS RULES (ERROR)
        if item.bruto_kg and item.neto_kg:
            if item.bruto_kg < item.neto_kg:
                result.valid = False
                result.errors.append(
                    ValidationError(
                        level=ValidationLevel.ERROR,
                        field="bruto",
                        message=f"Bruto masa ({item.bruto_kg} kg) ne može biti manja od neto ({item.neto_kg} kg)",
                        suggestion="Provjerite mase ili kliknite '🧮 Izračunaj'",
                    )
                )

        # 4. DATA QUALITY (WARNING)
        if item.cijena_jed and item.cijena_jed <= 0:
            result.warnings.append(
                ValidationError(
                    level=ValidationLevel.WARNING,
                    field="cijena",
                    message="Cijena je 0 ili negativna",
                    suggestion="Provjerite da li je ovo tačno",
                )
            )

        if item.bruto_kg and item.bruto_kg > 10000:
            result.warnings.append(
                ValidationError(
                    level=ValidationLevel.WARNING,
                    field="bruto",
                    message=f"Bruto masa ({item.bruto_kg} kg) je neobično velika",
                    suggestion="Provjerite jedinicu mjere (kg vs. tone?)",
                )
            )

        # 5. CROSS-REFERENCE VALIDATION (ERROR)
        # (zahtijeva DB pristup - poziva se odvojeno)

        # Generiši field_errors mapping
        for error in result.errors:
            if error.field not in result.field_errors:
                result.field_errors[error.field] = error.message

        return result

    def _is_valid_tariff_format(self, tariff: str) -> bool:
        """Provjera da li je tarifni broj validan format"""
        # 8 ili 10 cifara, bez razmaka
        return tariff.isdigit() and (len(tariff) == 8 or len(tariff) == 10)


class NaimenovanjeValidator:
    """Validacija kompletnog naimenovanja (ASYCUDA struktura)"""

    def validate(self, naimenovanje: NaimenovanjeItem) -> ValidationResult:
        """Validira naimenovanje prije XML export-a"""
        # Ovo je stroža validacija - sve što XML zahtijeva
        # Plus business rules specifične za carinski proces
        # TODO: Implementirati validaciju
        return ValidationResult(valid=True)


# Validation orchestrator
class ValidationService:
    """Centralni validation service"""

    def __init__(self, db_service):
        self.db = db_service
        self.faktura_validator = FakturaItemValidator()
        self.naimenovanje_validator = NaimenovanjeValidator()

    def validate_faktura_items(
        self, items: List[FakturaItem]
    ) -> Dict[int, ValidationResult]:
        """
        Validira sve stavke fakture.
        Returns: mapping index → ValidationResult
        """
        results = {}

        for i, item in enumerate(items):
            # Basic validation
            result = self.faktura_validator.validate(item)

            # Cross-reference validation (DB lookup)
            if item.tarifni_broj:
                if not self.db.tariff_exists(item.tarifni_broj):
                    result.valid = False
                    result.errors.append(
                        ValidationError(
                            level=ValidationLevel.ERROR,
                            field="tarifni_broj",
                            message=f"Tarifni broj {item.tarifni_broj} ne postoji u bazi",
                            suggestion="Provjerite broj ili dodajte novi",
                        )
                    )

            results[i] = result

        return results

    def can_create_naimenovanja(
        self, validation_results: Dict[int, ValidationResult]
    ) -> bool:
        """
        Da li se može nastaviti sa kreiranjem naimenovanja?
        (provjerava da li ima blokirajućih grešaka)
        """
        return not any(
            result.has_blocking_errors() for result in validation_results.values()
        )

    def get_validation_summary(
        self, validation_results: Dict[int, ValidationResult]
    ) -> str:
        """Generiše tekstualni sažetak validacije"""
        total_items = len(validation_results)
        valid_items = sum(1 for r in validation_results.values() if r.valid)

        total_errors = sum(len(r.errors) for r in validation_results.values())

        total_warnings = sum(len(r.warnings) for r in validation_results.values())

        summary = f"""
VALIDACIJA ZAVRŠENA:
- Ukupno stavki: {total_items}
- Validne stavki: {valid_items}
- Greške: {total_errors}
- Upozorenja: {total_warnings}
"""

        if total_errors > 0:
            summary += (
                "\n⚠️ NEKE STAVKE IMAJU GREŠKE - mora se ispraviti prije nastavka!"
            )
        elif total_warnings > 0:
            summary += (
                "\n⚠️ Neke stavke imaju upozorenja - možete nastaviti ali provjerite."
            )
        else:
            summary += "\n✅ Sve stavke su validne - možete nastaviti!"

        return summary
