"""
Modeli za rezultat pripreme (Faza 3).

Plan §6:
  - PreparedInvoice — jedna logička faktura nakon deduplikacije
  - ImportPlan — kompletan plan prije izmjene drafta
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.draft.draft import InvoiceLine, Party
from services.import_workflow.models import ImportCandidate


class DraftOperation(str, Enum):
    """Šta uraditi sa postojećim draft-om za ovu fakturu."""
    ADD = "ADD"        # Dodaj na kraj (nova faktura)
    REPLACE = "REPLACE"  # Zamijeni postojeću fakturu (isti invoice, ponovni uvoz)
    SKIP = "SKIP"      # Preskoči (duplikat već u draftu)


class OriginDialogType(str, Enum):
    """Tip dijaloga za porijeklo robe (PE2/PE3/EUR1)."""
    PE2 = "pe2"
    PE3 = "pe3"
    EUR1 = "eur1"
    NONE = "none"


@dataclass
class PartnerConflict:
    """Konflikt partnera između faktura u batchu ili sa postojećim draft-om."""
    field_name: str  # 'exporter' ili 'importer'
    expected: str
    actual: str


@dataclass
class PreparedInvoice:
    """Jedna logička faktura nakon deduplikacije i grupisanja."""

    # ── Stabilni interni ključ (za grupisanje, ne poslovni broj) ────
    internal_key: str

    # ── Poslovni identitet ──────────────────────────────────────────
    # Pouzdani broj fakture (iz parsera) — prazan ako nije utvrđen.
    invoice_number: str = ""
    # Prikazni naziv (može biti stem fajla) — NE postaje invoice_number.
    display_name: str = ""

    # ── Stavke (objedinjene iz svih fizičkih fajlova fakture) ──────
    invoice_lines: list[InvoiceLine] = field(default_factory=list)

    # ── Težine ─────────────────────────────────────────────────────
    bruto_kg: float = 0.0
    neto_kg: float = 0.0

    # ── Partneri i valuta ──────────────────────────────────────────
    exporter: Optional[Party] = None
    importer: Optional[Party] = None
    currency: str = ""

    # ── Porijeklo ──────────────────────────────────────────────────
    has_origin_statement: bool = False
    eur1_suggested: bool = False
    is_authorized_exporter: bool = False
    origin_statements: Optional[list] = None

    # ── Izvorni fajlovi (koji fizički fajlovi čine ovu fakturu) ────
    source_paths: list[str] = field(default_factory=list)

    # ── Pripremljene odluke ────────────────────────────────────────
    origin_dialog: OriginDialogType = OriginDialogType.NONE
    draft_operation: DraftOperation = DraftOperation.ADD

    # ── Upozorenja specifična za ovu fakturu ───────────────────────
    warnings: list[str] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.invoice_lines)

    @property
    def has_reliable_invoice_number(self) -> bool:
        """Da li je poslovni broj fakture pouzdano utvrđen."""
        return bool(self.invoice_number and self.invoice_number.strip())


@dataclass
class SkippedFile:
    """Fajl koji je preskočen u pripremi (duplikat ili potrošen)."""
    source_path: str
    reason: str  # 'consumed', 'duplicate_path', 'duplicate_invoice'


@dataclass
class FailedFile:
    """Fajl koji nije uspio u pripremi (greška parsera)."""
    source_path: str
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportPlan:
    """Kompletan plan prije izmjene drafta.

    Servis pripreme vraća ovaj objekat — draft se ne mijenja dok god
    korisnik ne potvrdi odluke (Faza 4) i servis primjene (Faza 5) ne izvrši.
    """

    # ── Prihvaćene fakture (spremne za primjenu) ───────────────────
    invoices: list[PreparedInvoice] = field(default_factory=list)

    # ── Preskočeni duplikati ───────────────────────────────────────
    skipped: list[SkippedFile] = field(default_factory=list)

    # ── Neuspjeli fajlovi ──────────────────────────────────────────
    failed: list[FailedFile] = field(default_factory=list)

    # ── Konflikti partnera/valute (zahtijevaju korisničku odluku) ──
    partner_conflicts: list[PartnerConflict] = field(default_factory=list)
    currency_conflict: Optional[tuple[str, str]] = None  # (očekivana, stvarna)

    # ── Sve potrebne PE2/PE3/EUR1 odluke ──────────────────────────
    # (jedna po logičkoj fakturi, ne po fizičkom fajlu)
    origin_dialogs_needed: list[tuple[str, OriginDialogType]] = field(default_factory=list)

    # ── Očekivani rezultat (brojevi za završnu poruku) ────────────
    expected_add_count: int = 0
    expected_replace_count: int = 0
    expected_skip_count: int = 0
    expected_total_items: int = 0
    expected_total_bruto: float = 0.0
    expected_total_neto: float = 0.0

    # ── Sva upozorenja koja korisnik mora vidjeti ──────────────────
    warnings: list[str] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Da li plan ima konflikte koji zahtijevaju korisničku odluku."""
        return bool(self.partner_conflicts) or self.currency_conflict is not None

    @property
    def has_origin_dialogs(self) -> bool:
        """Da li plan ima PE2/PE3/EUR1 dijaloge koje treba prikazati."""
        return any(dt != OriginDialogType.NONE for _, dt in self.origin_dialogs_needed)

    @property
    def is_empty(self) -> bool:
        """Da li plan nema nijedne prihvaćene fakture."""
        return not self.invoices
