"""
Neutralni result modeli za Faktura 3-layer refaktor.

Faza 1 prema Codex planu §5.5.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ImportFinishedResult:
    items_count: int = 0
    bruto_kg: float = 0.0
    neto_kg: float = 0.0
    invoice_name: str = ""
    is_combined: bool = False
    replaced: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class MassCalculationResult:
    bruto_kg: float = 0.0
    neto_kg: float = 0.0
    per_line_masses: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class CalculateMassesRequest:
    bruto_total: float = 0.0
    neto_total: float = 0.0
    allow_suspicious_fallback: bool = False
    suspicious_fallback: bool = False
    no_invoice_count: int = 0


@dataclass
class CalculateMassesResult:
    success: bool = False
    updated_count: int = 0
    skipped_count: int = 0
    fallback_skipped: int = 0
    no_weight_invoices: list[str] = field(default_factory=list)
    mass_mismatches: list[dict] = field(default_factory=list)
    suspicious_fallback: bool = False
    no_invoice_count: int = 0
    reason: str = ""
    invoice_labels: dict = field(default_factory=dict)


@dataclass
class ValidationPassResult:
    validated_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    color_map: dict = field(default_factory=dict)  # row_index → (color, tooltip)


@dataclass
class TariffAutoFillResult:
    filled_count: int = 0
    unfilled_count: int = 0
    proposals: list = field(default_factory=list)


@dataclass
class AutoFillWorkflowRequest:
    target_lines: list = field(default_factory=list)
    supplier_name: str = ""
    auto: bool = False
    confirmed_proposals: list | None = None
    min_similarity: float = 0.92
    basic_filled_count: int | None = None


@dataclass
class AutoFillWorkflowResult:
    mapping_result: object | None = None
    basic_filled_count: int = 0
    supplier_name: str = ""
    skipped_details: list[tuple[int, str, str]] = field(default_factory=list)
    error: Exception | None = None


@dataclass
class NaimenovanjaCreationResult:
    created_count: int = 0
    split_count: int = 0
    overflow: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class PartnerConsistencyResult:
    consistent: bool = True
    exporter_match: bool = True
    importer_match: bool = True
    warnings: list[str] = field(default_factory=list)
