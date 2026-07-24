import logging
logger = logging.getLogger(__name__)
# services/preference_validator.py

"""
Preference Validator

Validacija povlastica:
- CEFTAP, EUP, TRP, PE1, PE2, PE3 zahtevaju EUR.1 obrazac ili izjavu o poreklu
- Bez povlastice → nema uslova
"""

from typing import List, Optional
from dataclasses import dataclass
from core.draft.draft import InvoiceLine


@dataclass
class ValidationResult:
    """Rezultat validacije jedne stavke."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    
    @classmethod
    def ok(cls) -> 'ValidationResult':
        return cls(valid=True, errors=[], warnings=[])
    
    @classmethod
    def error(cls, message: str) -> 'ValidationResult':
        return cls(valid=False, errors=[message], warnings=[])
    
    @classmethod
    def warning(cls, message: str) -> 'ValidationResult':
        return cls(valid=True, errors=[], warnings=[message])


class PreferenceValidator:
    """
    Validacija povlastica.
    
    Pravila:
    ┌──────────────┬────────────────────────────────────────────┐
    │ Povlastica   │ Uslov                                      │
    ├──────────────┼────────────────────────────────────────────┤
    │ CEFTAP       │ Mora imati EUR.1 (PE1) ILI izjavu          │
    │ EUP          │ Mora imati EUR.1 (PE1) ILI izjavu          │
    │ TRP          │ Mora imati EUR.1 (PE1) ILI izjavu          │
    │ PE1          │ Mora imati eur1_number                     │
    │ PE2          │ Mora imati izjavu o poreklu                │
    │ PE3          │ Mora imati izjavu ovlašćenog izvoznika     │
    │ (prazno)     │ Nema uslova                                │
    └──────────────┴────────────────────────────────────────────┘
    """
    
    # Povlastice koje zahtevaju EUR.1 ili izjavu
    PREFERENCE_CODES = {'CEFTAP', 'EUP', 'TRP', 'PE1', 'PE2', 'PE3'}
    
    # Povlastice koje zahtevaju IZJAVU (ne EUR.1)
    STATEMENT_ONLY_CODES = {'PE2', 'PE3'}
    
    # EUR.1 šifre
    EUR1_CODES = {'PE1'}
    
    def validate(self, item: InvoiceLine) -> ValidationResult:
        """
        Validiraj jednu stavku.
        
        Args:
            item: Stavka za validaciju
            
        Returns:
            ValidationResult sa greškama i upozorenjima
        """
        povlastica = (item.povlastica or "").strip().upper()
        eur1_number = (item.eur1_number or "").strip()
        has_statement = item.has_origin_statement
        
        # 1. Ako nema povlasticu → validno
        if not povlastica or povlastica == '-':
            return ValidationResult.ok()
        
        # 2. Ako povlastica nije u listi zahtevnih → validno
        if povlastica not in self.PREFERENCE_CODES:
            return ValidationResult.ok()
        
        # 3. Validacija za PE1 (EUR.1 obrazac)
        if povlastica in self.EUR1_CODES:
            if not eur1_number:
                return ValidationResult.error(
                    f"PE1 zahteva EUR.1 broj. Unesi broj EUR.1 obrasca."
                )
            return ValidationResult.ok()
        
        # 4. Validacija za PE2/PE3 (izjava)
        if povlastica in self.STATEMENT_ONLY_CODES:
            if not has_statement:
                return ValidationResult.error(
                    f"{povlastica} zahteva izjavu o poreklu na fakturi."
                )
            return ValidationResult.ok()
        
        # 5. Validacija za CEFTAP/EUP/TRP
        if povlastica in {'CEFTAP', 'EUP', 'TRP'}:
            # Mora imati EUR.1 (PE1) ILI izjavu
            if eur1_number:
                # Dodaj istorijsko warning ako je dostupno
                return self._add_historical_warning(item, povlastica, ValidationResult.ok())
            if has_statement:
                # Dodaj istorijsko warning ako je dostupno
                return self._add_historical_warning(item, povlastica, ValidationResult.ok())
            
            return ValidationResult.error(
                f"Povlastica {povlastica} zahteva EUR.1 obrazac (PE1) ili izjavu o poreklu."
            )
    
    def _add_historical_warning(self, item: InvoiceLine, current_preference: str, result: ValidationResult) -> ValidationResult:
        """
        Dodaj istorijsko warning ako je dostupno.
        
        Warning se dodaje ako:
        - Znamo exportera
        - Istorijski podaci postoje
        - Trenutna povlastica se ne slaže sa istorijom
        """
        try:
            # Pokušaj da dobiješ exporter name
            exporter_name = ""
            if hasattr(item, 'exporter') and item.exporter:
                exporter_name = item.exporter
            elif hasattr(item, 'invoice') and hasattr(item.invoice, 'exporter'):
                exporter_name = item.invoice.exporter
            
            if not exporter_name or not item.zemlja_porijekla:
                return result
            
            # Koristi HistoricalLearningServiceSafe
            from services.agent.learning.historical_learning_service_safe import enhance_preference_logic
            
            historical_pref = enhance_preference_logic(item.zemlja_porijekla, exporter_name)
            
            if historical_pref and historical_pref != current_preference:
                # Dodaj warning
                warning_msg = f"Istorijski podaci: {exporter_name} obično koristi {historical_pref} za {item.zemlja_porijekla}."
                result.warnings.append(warning_msg)
                
        except Exception as _e:
            logger.debug("Historijska preferencija fallback: %s", _e)
        
        return result
        
        return ValidationResult.ok()
    
    def validate_batch(self, items: List[InvoiceLine]) -> dict:
        """
        Validiraj više stavki odjednom.
        
        Args:
            items: Lista stavki za validaciju
            
        Returns:
            Dict sa statistikom:
            {
                'total': int,
                'valid': int,
                'invalid': int,
                'errors': List[Tuple[int, str]],  # (line_no, error_message)
                'warnings': List[Tuple[int, str]],
            }
        """
        results = []
        errors = []
        warnings = []
        valid_count = 0
        
        for item in items:
            result = self.validate(item)
            results.append(result)
            
            if result.valid:
                valid_count += 1
                if result.warnings:
                    for warning in result.warnings:
                        warnings.append((item.line_no, warning))
            else:
                for error in result.errors:
                    errors.append((item.line_no, error))
        
        return {
            'total': len(items),
            'valid': valid_count,
            'invalid': len(items) - valid_count,
            'errors': errors,
            'warnings': warnings,
        }
    
    def get_missing_eur1(self, items: List[InvoiceLine]) -> List[InvoiceLine]:
        """
        Vrati stavke koje imaju povlasticu ali nemaju EUR.1.
        
        Args:
            items: Lista stavki
            
        Returns:
            Lista stavki kojima nedostaje EUR.1
        """
        missing = []
        
        for item in items:
            povlastica = (item.povlastica or "").strip().upper()
            eur1_number = (item.eur1_number or "").strip()
            has_statement = item.has_origin_statement
            
            if povlastica in self.PREFERENCE_CODES:
                if not eur1_number and not has_statement:
                    missing.append(item)
        
        return missing
    
    def auto_fix_missing_eur1(self, items: List[InvoiceLine]) -> int:
        """
        DEPRECATED — koristiti DeclarationDecisionService.confirm_manual_value().

        Ovaj metod direktno pise item.povlastica = 'PE1' sto narusava
        read-only prirodu validatora. Zadrzan je zbog backward kompatibilnosti
        dok se svi pozivaoci ne migriraju na decision servis (Faza 6).
        """
        fixed_count = 0
        
        for item in items:
            povlastica = (item.povlastica or "").strip().upper()
            eur1_number = (item.eur1_number or "").strip()
            
            if povlastica in {'CEFTAP', 'EUP', 'TRP'} and not eur1_number:
                # Postavi PE1 umesto CEFTAP/EUP/TRP
                item.povlastica = 'PE1'
                fixed_count += 1
        
        return fixed_count


# ============================================================
# USAGE EXAMPLE / TEST
# ============================================================

if __name__ == "__main__":
    from core.draft.draft import InvoiceLine
    
    validator = PreferenceValidator()
    
    # Test cases
    test_items = [
        # Valid: EUR.1 sa PE1
        InvoiceLine(
            line_no=1,
            zemlja_porijekla="RS",
            povlastica="PE1",
            eur1_number="000456/2025"
        ),
        
        # Valid: CEFTAP sa EUR.1
        InvoiceLine(
            line_no=2,
            zemlja_porijekla="RS",
            povlastica="CEFTAP",
            eur1_number="000456/2025"
        ),
        
        # Invalid: CEFTAP bez EUR.1
        InvoiceLine(
            line_no=3,
            zemlja_porijekla="RS",
            povlastica="CEFTAP",
            eur1_number=""
        ),
        
        # Valid: Bez povlastice
        InvoiceLine(
            line_no=4,
            zemlja_porijekla="CN",
            povlastica="",
            eur1_number=""
        ),
        
        # Valid: EUP sa izjavom
        InvoiceLine(
            line_no=5,
            zemlja_porijekla="DE",
            povlastica="EUP",
            eur1_number="",
            has_origin_statement=True
        ),
    ]
    
    logger.debug("=" * 70)
    logger.debug("PREFERENCE VALIDATOR - TEST")
    logger.debug("=" * 70)
    
    for item in test_items:
        result = validator.validate(item)
        status = "✅" if result.valid else "❌"
        logger.debug(f"\n{status} Stavka {item.line_no}: {item.povlastica or '(bez)'}")
        
        if result.errors:
            for error in result.errors:
                logger.error(f"   ❌ Greška: {error}")
        
        if result.warnings:
            for warning in result.warnings:
                logger.warning(f"   ⚠️ Upozorenje: {warning}")
    
    # Batch validation
    logger.debug("\n" + "=" * 70)
    batch_result = validator.validate_batch(test_items)
    logger.debug(f"Batch validacija:")
    logger.debug(f"  Ukupno: {batch_result['total']}")
    logger.debug(f"  Validno: {batch_result['valid']}")
    logger.debug(f"  Nevalidno: {batch_result['invalid']}")
    
    if batch_result['errors']:
        logger.debug(f"\nGreške:")
        for line_no, error in batch_result['errors']:
            logger.debug(f"  Stavka {line_no}: {error}")
