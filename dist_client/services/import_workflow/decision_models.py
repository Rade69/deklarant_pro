"""
Modeli za korisničke odluke (Faza 4).

Plan §16 Faza 4:
  - Controller dobija potrebne odluke iz plana
  - View prikazuje postojeće dijaloge
  - Odgovori se vraćaju kontroleru
  - Servis validira da su sve obavezne odluke prisutne
  - Odustajanje završava bez izmjene drafta

Izlaz: jedna poslovna politika uz dva dozvoljena kanala prikaza.

Ovi modeli su neutralni (bez Qt) — i ručni i agent View ih koriste.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from services.import_workflow.plan_models import (
    ImportPlan,
    OriginDialogType,
    PreparedInvoice,
)


class PartnerConflictResolution(str, Enum):
    """Šta je korisnik odlučio za konflikt partnera."""
    CONTINUE = "continue"       # Nastavi svejedno (prihvati novog partnera)
    SKIP_INVOICE = "skip"       # Preskoči ovu fakturu
    ABORT = "abort"             # Odustani od cijelog batcha


class OriginDialogResolution(str, Enum):
    """Šta je korisnik odlučio za PE2/PE3/EUR1 dijalog."""
    APPLIED = "applied"    # Korisnik je primijenio povlasticu (PE2/PE3/EUR1 broj unešen)
    SKIPPED = "skipped"    # Korisnik je preskočio dijalog (bez povlastice)


@dataclass
class OriginDialogResponse:
    """Odgovor korisnika na jedan PE2/PE3/EUR1 dijalog."""
    invoice_key: str  # internal_key iz PreparedInvoice
    dialog_type: OriginDialogType
    resolution: OriginDialogResolution
    # Podaci iz dijaloga (ako je APPLIED) — PE2/PE3/EUR1 broj, zemlja, itd.
    # Tip dict jer se razlikuje po tipu dijaloga (PE2QuickDialog vs Eur1QuickDialog).
    dialog_data: dict = field(default_factory=dict)


@dataclass
class PartnerConflictResponse:
    """Odgovor korisnika na konflikt partnera."""
    invoice_key: str
    field_name: str  # 'exporter' ili 'importer'
    expected: str
    actual: str
    resolution: PartnerConflictResolution


@dataclass
class CurrencyConflictResponse:
    """Odgovor korisnika na konflikt valute."""
    invoice_key: str
    expected: str
    actual: str
    resolution: PartnerConflictResolution


@dataclass
class InvoiceDecision:
    """Konačna odluka za jednu fakturu (nakon korisničkih odgovora)."""
    invoice_key: str
    # Da li korisnik želi ovu fakturu u draft (True) ili je preskače (False).
    apply: bool = True
    # Origin dialog odgovor (None ako nije bio potreban).
    origin_response: Optional[OriginDialogResponse] = None


@dataclass
class UserDecisions:
    """Sve korisničke odluke za jedan ImportPlan.

    View prikupi odluke (prikazujući dijaloge) i vrati ovaj objekat
    kontroleru, koji ga proslijeđuje servisu primjene (Faza 5).
    """
    # Da li je korisnik odustao od cijelog batcha.
    aborted: bool = False

    # Odluke po fakturama (ključ = internal_key).
    invoice_decisions: dict[str, InvoiceDecision] = field(default_factory=dict)

    # Odgovori na konflikte partnera (ako ih je bilo).
    partner_conflict_responses: list[PartnerConflictResponse] = field(default_factory=list)

    # Odgovor na konflikt valute (ako ga je bilo).
    currency_conflict_response: Optional[CurrencyConflictResponse] = None
    currency_conflict_responses: list[CurrencyConflictResponse] = field(default_factory=list)

    def get_invoice_decision(self, invoice_key: str) -> InvoiceDecision:
        """Vrati odluku za fakturu (default: apply=True, bez origin response)."""
        return self.invoice_decisions.get(
            invoice_key, InvoiceDecision(invoice_key=invoice_key)
        )

    def is_invoice_aborted(self, invoice_key: str) -> bool:
        """Da li je korisnik preskočio/odustao od ove fakture."""
        if self.aborted:
            return True
        dec = self.invoice_decisions.get(invoice_key)
        return dec is not None and not dec.apply
