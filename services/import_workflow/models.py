"""
Neutralni modeli za jedinstveni import workflow.

Ovi modeli su nezavisni od Qt widgeta — koriste ih i ručni i agent uvoz
da proizvedu isti poslovni rezultat iz istih fajlova.

Vidi docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md §6.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.draft.draft import InvoiceLine, Party


@dataclass
class ImportCandidate:
    """Neutralan zapis jednog importovanog fajla/rezultata.

    Nezavisan od Qt widgeta — i ImportResult (ručni uvoz) i FileItem
    (agent uvoz) se konvertuju u ovaj model prije zajedničke obrade.
    """

    # ── Izvor ──────────────────────────────────────────────────────
    source_path: str
    normalized_path: str
    file_type: str = ""           # 'PDF', 'Excel', 'XML'
    parser: str = ""              # koji parser je korišten

    # ── Stavke ─────────────────────────────────────────────────────
    invoice_lines: list[InvoiceLine] = field(default_factory=list)

    # ── Identitet fakture ──────────────────────────────────────────
    # Broj koji je parser eksplicitno pronašao (pouzdan).
    # Prazan string = parser nije uspio izvući broj.
    explicit_invoice_number: str = ""
    # Prikazni naziv (može biti stem fajla) — NE postaje invoice_number.
    display_name: str = ""

    # ── Težine ─────────────────────────────────────────────────────
    bruto_kg: float = 0.0
    neto_kg: float = 0.0

    # ── Partneri i valuta (za zaglavlje) ──────────────────────────
    exporter: Optional[Party] = None
    importer: Optional[Party] = None
    currency: str = ""

    # ── Porijeklo i povlastice ─────────────────────────────────────
    has_origin_statement: bool = False
    eur1_suggested: bool = False
    is_authorized_exporter: bool = False
    origin_statements: Optional[list] = None

    # ── Kombinovani import ─────────────────────────────────────────
    is_combined: bool = False
    consumed_paths: list[str] = field(default_factory=list)

    # ── Upozorenja i greške parsera ────────────────────────────────
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_items(self) -> bool:
        """Da li kandidat ima stavke (neprazna lista)."""
        return bool(self.invoice_lines)

    @property
    def item_count(self) -> int:
        return len(self.invoice_lines)

    @property
    def has_explicit_invoice_number(self) -> bool:
        """Da li je parser pouzdano izvukao broj fakture."""
        return bool(self.explicit_invoice_number and self.explicit_invoice_number.strip())


def _normalize_path(path: str | Path) -> str:
    """Normalizuj putanju na apsolutnu, case-insensitive (Windows)."""
    import os
    return os.path.normcase(str(Path(path).resolve()))


def _detect_file_type(path: str | Path) -> str:
    """Detektuj tip fajla na osnovu ekstenzije."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return "PDF"
    if ext in (".xlsx", ".xls"):
        return "Excel"
    if ext == ".xml":
        return "XML"
    return "Unknown"
