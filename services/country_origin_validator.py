# Proxy modul za CountryOriginValidator
# Definisanje klase CountryOriginValidator ovde da izbjegnemo circular import

from services.tariff.country_origin_validator import (
    ConfidenceLevel,
    CountryValidationResult,
    derive_preference,
    validate_preference,
    merge_country_origin,
    get_confidence_color,
    get_confidence_tooltip
)

# Definisanje klase CountryOriginValidator
class CountryOriginValidator:
    """Validator za zemlju porijekla."""
    
    ConfidenceLevel = ConfidenceLevel
    CountryValidationResult = CountryValidationResult
    
    @staticmethod
    def derive_preference(zemlja: str) -> str:
        return derive_preference(zemlja)
    
    @staticmethod
    def validate_preference(zemlja: str, povlastica: str) -> str:
        return validate_preference(zemlja, povlastica)
    
    @staticmethod
    def merge_country_origin(zemlja_pdf: str, zemlja_baza: str, povlastica_baza: str = "", 
                            has_origin_statement: bool = False) -> CountryValidationResult:
        return merge_country_origin(zemlja_pdf, zemlja_baza, povlastica_baza, has_origin_statement)
    
    @staticmethod
    def get_confidence_color(confidence: ConfidenceLevel) -> str:
        return get_confidence_color(confidence)
    
    @staticmethod
    def get_confidence_tooltip(confidence: ConfidenceLevel, source: str, conflict_details: str = None) -> str:
        return get_confidence_tooltip(confidence, source, conflict_details)


__all__ = [
    "CountryOriginValidator",
    "ConfidenceLevel",
    "CountryValidationResult",
    "derive_preference",
    "validate_preference",
    "merge_country_origin",
    "get_confidence_color",
    "get_confidence_tooltip",
]
