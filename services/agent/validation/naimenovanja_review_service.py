"""
Naimenovanja Review Service — pregled i validacija naimenovanja.

Business logika za:
- Validaciju popunjenosti svih rubrika (Rb.31–46)
- Detaljan pregled konkretnog naimenovanja
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RubrikaStatus:
    """Status jedne rubrike u naimenovanju."""
    rubrika: str          # npr. "Rb.33"
    field_name: str       # npr. "tariff_code"
    value: Any            # stvarna vrijednost
    is_empty: bool        # da li je prazna
    is_optional: bool     # da li je opcionalna


@dataclass
class NaimenovanjeValidation:
    """Rezultat validacije za jedno naimenovanje."""
    ordinal_no: int
    tariff_code: str
    prazne_obavezne: List[str] = field(default_factory=list)   # ["Rb.33 (tariff_code)", ...]
    prazne_opcione: List[str] = field(default_factory=list)


@dataclass
class NaimenovanjePregled:
    """Kompletan pregled jednog naimenovanja."""
    ordinal_no: int
    # Rub.31
    package_marks: str = ""
    package_code: str = ""
    package_name: str = ""
    package_qty: float = 0.0
    container_number1: str = ""
    container_number2: str = ""
    goods_description: str = ""
    goods_trade_name: str = ""
    tariff_description1: str = ""
    tariff_description2: str = ""
    tariff_description3: str = ""
    # Rub.33
    tariff_code: str = ""
    tariff_suffix: str = ""
    # Rub.34
    origin_country_code: str = ""
    origin_country_name: str = ""
    # Rub.36
    preference_code: str = ""
    preference_name: str = ""
    # Rub.35/38
    gross_mass_kg: float = 0.0
    net_mass_kg: float = 0.0
    # Rub.37
    procedure_code: str = ""
    procedure_prev_code: str = ""
    # Rub.39
    quota_code: str = ""
    # Rub.40
    previous_document: str = ""
    previous_document2: str = ""
    previous_document3: str = ""
    # Rub.41
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0
    # Rub.42
    item_value: float = 0.0
    currency: str = "EUR"
    # Rub.44
    attached_document1: str = ""
    attached_document2: str = ""
    attached_document3: str = ""
    attached_document4: str = ""
    attached_document5: str = ""
    # Rub.46
    statistical_value: float = 0.0
    # Ostalo
    notes: str = ""
    source_invoice_refs: List[str] = field(default_factory=list)

    def has_value(self, field_name: str) -> bool:
        """Provjeri da li polje ima vrijednost."""
        val = getattr(self, field_name, None)
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, list):
            return len(val) > 0
        return True


# ─────────────────────────────────────────────────────────────────────
# Konfiguracija rubrika
# ─────────────────────────────────────────────────────────────────────

_RUBRIKE_CONFIG: Dict[str, Dict[str, Any]] = {
    'Rb.31': {
        'fields': ['goods_description', 'package_code', 'package_qty'],
        'label': 'Pakovanje i opis robe',
        'optional': ['package_marks', 'container_number1', 'container_number2',
                     'goods_trade_name', 'tariff_description1', 'tariff_description2',
                     'tariff_description3', 'package_name']
    },
    'Rb.33': {
        'fields': ['tariff_code'],
        'label': 'Tarifni broj',
        'optional': ['tariff_suffix']
    },
    'Rb.34': {
        'fields': ['origin_country_code'],
        'label': 'Zemlja porijekla',
        'optional': ['origin_country_name']
    },
    'Rb.36': {
        'fields': [],
        'label': 'Povlastica',
        'optional': ['preference_code', 'preference_name']
    },
    'Rb.35/38': {
        'fields': ['gross_mass_kg', 'net_mass_kg'],
        'label': 'Mase',
        'optional': []
    },
    'Rb.37': {
        'fields': ['procedure_code'],
        'label': 'Postupak',
        'optional': ['procedure_prev_code']
    },
    'Rb.39': {
        'fields': [],
        'label': 'Kvota',
        'optional': ['quota_code']
    },
    'Rb.40': {
        'fields': [],
        'label': 'Prethodni dokumenti',
        'optional': ['previous_document', 'previous_document2', 'previous_document3']
    },
    'Rb.41': {
        'fields': [],
        'label': 'Dopunske jedinice',
        'optional': ['supplementary_unit_code', 'supplementary_unit_qty']
    },
    'Rb.42': {
        'fields': ['item_value', 'currency'],
        'label': 'Vrijednost',
        'optional': []
    },
    'Rb.44': {
        'fields': [],
        'label': 'Priložene isprave',
        'optional': ['attached_document1', 'attached_document2', 'attached_document3',
                     'attached_document4', 'attached_document5']
    },
    'Rb.46': {
        'fields': ['statistical_value'],
        'label': 'Statistička vrijednost',
        'optional': []
    },
}


class NaimenovanjaReviewService:
    """
    Service za pregled i validaciju naimenovanja.
    """

    @staticmethod
    def provjeri_naimenovanja(naim_items: list) -> Dict[str, Any]:
        """
        Validacija popunjenosti svih rubrika za sva naimenovanja.

        Returns:
            {
                'total_naim': int,
                'total_praznih_obaveznih': int,
                'total_praznih_opcionih': int,
                'problemi': List[NaimenovanjeValidation],
                'is_complete': bool,
            }
        """
        problemi = []
        total_praznih_obaveznih = 0
        total_praznih_opcionih = 0

        for item in naim_items:
            rb = getattr(item, 'ordinal_no', 0) or 0
            prazne_obavezne: List[str] = []
            prazne_opcione: List[str] = []

            for rubrika, info in _RUBRIKE_CONFIG.items():
                for fld in info['fields']:
                    val = getattr(item, fld, None)
                    if val is None or val == '' or val == 0:
                        prazne_obavezne.append(f"{rubrika} ({fld})")

                for fld in info['optional']:
                    val = getattr(item, fld, None)
                    if val is None or val == '' or val == 0:
                        prazne_opcione.append(f"{rubrika} ({fld})")

            total_praznih_obaveznih += len(prazne_obavezne)
            total_praznih_opcionih += len(prazne_opcione)

            if prazne_obavezne or prazne_opcione:
                problemi.append(NaimenovanjeValidation(
                    ordinal_no=rb,
                    tariff_code=getattr(item, 'tariff_code', '?') or '?',
                    prazne_obavezne=prazne_obavezne,
                    prazne_opcione=prazne_opcione,
                ))

        return {
            'total_naim': len(naim_items),
            'total_praznih_obaveznih': total_praznih_obaveznih,
            'total_praznih_opcionih': total_praznih_opcionih,
            'problemi': problemi,
            'is_complete': total_praznih_obaveznih == 0 and total_praznih_opcionih == 0,
        }

    @staticmethod
    def pregledaj_naimenovanje(item) -> NaimenovanjePregled:
        """
        Detaljan pregled jednog naimenovanja — sva polja.
        """
        pregled = NaimenovanjePregled(ordinal_no=getattr(item, 'ordinal_no', 0) or 0)

        # Kopiraj sva polja iz draft item-a
        for fld_name in NaimenovanjePregled.__dataclass_fields__:
            if fld_name == 'ordinal_no':
                continue
            pregled.__dict__[fld_name] = getattr(item, fld_name, '') or ''

        return pregled

    @staticmethod
    def pregledaj_sva(naim_items: list) -> List[NaimenovanjePregled]:
        """
        Detaljan pregled svih naimenovanja.
        """
        return [NaimenovanjaReviewService.pregledaj_naimenovanje(it) for it in naim_items]
