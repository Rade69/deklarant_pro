"""
Neutralni result modeli za Naimenovanja 3-layer refaktor.

Faza 1 prema Codex planu §5.5. Ovi modeli nemaju Qt zavisnosti.
Koriste se za komunikaciju Service → Controller → View.
"""

from dataclasses import dataclass, field


@dataclass
class TariffLookupResult:
    tariff_code: str
    full_description: str = ""
    short_description: str = ""
    supplementary_unit_code: str = ""
    supplementary_unit_qty: float = 0.0
    warnings: list[str] = field(default_factory=list)


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
