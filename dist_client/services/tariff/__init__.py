# services/tariff/__init__.py
# Import funkcija iz tarifa_service.py umesto klase TarifaService
from .tarifa_service import (
    pretrazi,
    trazi_po_kodu,
    trazi_poglavlje,
    naziv_poglavlja,
    validiraj_tarifni_broj,
    formatiraj_rezultate
)
from .tariff_mapping_service import TariffMappingService
from .tariff_tree_service import TariffTreeService
# Import funkcija iz country_origin_validator.py
from .country_origin_validator import (
    ConfidenceLevel,
    CountryValidationResult,
    derive_preference,
    validate_preference,
    merge_country_origin,
    get_confidence_color,
    get_confidence_tooltip
)
from .origin_statement_detector import OriginStatementDetector
from .product_master_list import ProductMasterList

# Alias za kompatibilnost sa postojećim kodom
TarifaService = type('TarifaService', (), {
    'pretrazi': staticmethod(pretrazi),
    'trazi_po_kodu': staticmethod(trazi_po_kodu),
    'trazi_poglavlje': staticmethod(trazi_poglavlje),
    'naziv_poglavlja': staticmethod(naziv_poglavlja),
    'validiraj_tarifni_broj': staticmethod(validiraj_tarifni_broj),
    'formatiraj_rezultate': staticmethod(formatiraj_rezultate)
})

# Alias za CountryOriginValidator
CountryOriginValidator = type('CountryOriginValidator', (), {
    'ConfidenceLevel': ConfidenceLevel,
    'CountryValidationResult': CountryValidationResult,
    'derive_preference': staticmethod(derive_preference),
    'validate_preference': staticmethod(validate_preference),
    'merge_country_origin': staticmethod(merge_country_origin),
    'get_confidence_color': staticmethod(get_confidence_color),
    'get_confidence_tooltip': staticmethod(get_confidence_tooltip)
})

__all__ = [
    "TarifaService",
    "TariffMappingService",
    "TariffTreeService",
    "CountryOriginValidator",
    "OriginStatementDetector",
    "ProductMasterList",
]
