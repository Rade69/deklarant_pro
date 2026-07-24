from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportApplyResult:
    success: bool
    applied_invoice_keys: list[str] = field(default_factory=list)
    applied_invoice_numbers: list[str] = field(default_factory=list)
    added_invoices: int = 0
    replaced_invoices: int = 0
    skipped_invoices: int = 0
    added_items: int = 0
    replaced_items: int = 0
    skipped_items: int = 0
    total_items: int = 0
    total_bruto_kg: float = 0.0
    total_neto_kg: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        if not self.success:
            detail = "\n".join(self.errors[:3]) if self.errors else "Nepoznata greška."
            return f"Import nije primijenjen.\n{detail}"

        parts = [
            "Import primijenjen.",
            f"Faktura dodano: {self.added_invoices}",
            f"Faktura zamijenjeno: {self.replaced_invoices}",
            f"Faktura preskočeno: {self.skipped_invoices}",
            f"Stavki ukupno: {self.total_items}",
        ]
        if self.total_bruto_kg or self.total_neto_kg:
            parts.append(f"Bruto: {self.total_bruto_kg:g} kg")
            parts.append(f"Neto: {self.total_neto_kg:g} kg")
        if self.warnings:
            parts.append(f"Upozorenja: {len(self.warnings)}")
        return "\n".join(parts)
