"""
Neutralni result modeli za Naimenovanja 3-layer refaktor.

Faza 1 prema Codex planu §5.5. Ovi modeli nemaju Qt zavisnosti.
Koriste se za komunikaciju Service → Controller → View.
"""

from dataclasses import dataclass, field


@dataclass
class NavigationState:
    current_index: int
    total_count: int
    is_first: bool
    is_last: bool


@dataclass
class TariffLookupResult:
    tariff_code: str
    full_description: str = ""
    short_description: str = ""
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class TariffMutationResult:
    tariff_code: str
    affected_invoice_lines: int = 0
    kb_updated: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class SupplementaryUnitResult:
    code: str = ""
    qty: float = 0.0


@dataclass
class DocumentMergeResult:
    documents: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class XmlImportResult:
    items_count: int = 0
    global_documents: list[dict] = field(default_factory=list)
    header_fields: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class NaimenovanjeRenderContext:
    """Kontekst za renderovanje aktivnog naimenovanja u View."""
    item_index: int
    tariff_code: str = ""
    tariff_description1: str = ""
    tariff_description2: str = ""
    goods_trade_name: str = ""
    origin_country_code: str = ""
    preference_code: str = ""
    gross_mass_kg: float = 0.0
    net_mass_kg: float = 0.0
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0
    package_code: str = ""
    package_name: str = ""
    package_qty: float = 0.0
    package_marks: str = ""
    procedure_code: str = ""
    procedure_prev_code: str = ""
    quota_code: str = ""
    item_value: float = 0.0
    statistical_value: float = 0.0
    pd_codes: str = ""
    attached_documents: list = field(default_factory=list)
    tariff_warning: str = ""
    warnings: list[str] = field(default_factory=list)
