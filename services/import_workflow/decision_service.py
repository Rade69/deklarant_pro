"""
Servis za korisničke odluke (Faza 4).

Plan §16 Faza 4:
  1. Controller dobija potrebne odluke iz plana
  2. View prikazuje postojeće dijaloge
  3. Odgovori se vraćaju kontroleru
  4. Servis validira da su sve obavezne odluke prisutne
  5. Odustajanje završava bez izmjene drafta

Izlaz: jedna poslovna politika uz dva dozvoljena kanala prikaza.

Ovaj servis je neutralan (bez Qt). View (ručni ili agent) koristi
collect_required_decisions() da zna šta da prikaže, prikupi odgovore
u UserDecisions, pa validira_decisions() provjerava kompletnost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from services.import_workflow.decision_models import (
    CurrencyConflictResponse,
    InvoiceDecision,
    OriginDialogResolution,
    OriginDialogResponse,
    PartnerConflictResolution,
    PartnerConflictResponse,
    UserDecisions,
)
from services.import_workflow.plan_models import (
    ImportPlan,
    OriginDialogType,
    PreparedInvoice,
)


@dataclass
class RequiredDecisions:
    """Lista odluka koje View mora prikupiti od korisnika.

    View prolazi kroz ovu listu i prikazuje odgovarajuće dijaloge.
    Ako je prazna — nema potrebnih odluka, plan se može odmah primijeniti.
    """
    # Konflikti partnera (svaki zahtiva Yes/No/Abort odgovor).
    partner_conflicts: list[tuple[str, str, str]] = field(default_factory=list)
    # (field_name, expected, actual)

    # Konflikt valute (zahtiva odgovor).
    currency_conflict: Optional[tuple[str, str]] = None
    # (expected, actual)

    # PE2/PE3/EUR1 dijalozi (jedan po logičkoj fakturi).
    origin_dialogs: list[tuple[str, OriginDialogType, str]] = field(default_factory=list)
    # (invoice_key, dialog_type, display_name)

    @property
    def is_empty(self) -> bool:
        """Da li ima ijedne odluke koju treba prikupiti."""
        return (
            not self.partner_conflicts
            and self.currency_conflict is None
            and not self.origin_dialogs
        )


def collect_required_decisions(plan: ImportPlan) -> RequiredDecisions:
    """Identifikuj koje odluke View mora prikupiti od korisnika.

    Plan §16 Faza 4 korak 1: Controller dobija potrebne odluke iz plana.
    """
    required = RequiredDecisions()

    # Partner konflikti — jedan po konfliktu
    for conflict in plan.partner_conflicts:
        required.partner_conflicts.append(
            (conflict.field_name, conflict.expected, conflict.actual)
        )

    # Valuta konflikt
    if plan.currency_conflict is not None:
        required.currency_conflict = plan.currency_conflict

    # Origin dijalozi — jedan po fakturi koja ima origin_dialog != NONE
    for invoice_key, dialog_type in plan.origin_dialogs_needed:
        # Nađi display_name za ovu fakturu
        display_name = ""
        for inv in plan.invoices:
            if inv.internal_key == invoice_key:
                display_name = inv.display_name
                break
        required.origin_dialogs.append((invoice_key, dialog_type, display_name))

    return required


def validate_decisions(plan: ImportPlan, decisions: UserDecisions) -> list[str]:
    """Provjeri da su sve obavezne odluke prisutne.

    Plan §16 Faza 4 korak 4: Servis validira da su sve obavezne odluke prisutne.

    Returns:
        Lista grešaka (prazna = sve validno). Ako korisnik nije odustao,
        svaka potrebna odluka mora biti prisutna u UserDecisions.
    """
    errors: list[str] = []

    # Ako je korisnik odustao — nema potrebe za validacijom (abort = sve preskočeno)
    if decisions.aborted:
        return errors

    required = collect_required_decisions(plan)

    # Provjeri da je svaki partner konflikt riješen
    for field_name, expected, actual in required.partner_conflicts:
        has_response = any(
            r.field_name == field_name and r.expected == expected and r.actual == actual
            for r in decisions.partner_conflict_responses
        )
        if not has_response:
            errors.append(
                f"Nedostaje odluka za konflikt partnera: {field_name} "
                f"(očekivano '{expected}', stvarno '{actual}')"
            )

    # Provjeri da je valuta konflikt riješen
    if required.currency_conflict is not None:
        if decisions.currency_conflict_response is None:
            expected, actual = required.currency_conflict
            errors.append(
                f"Nedostaje odluka za konflikt valute: "
                f"očekivano '{expected}', stvarno '{actual}'"
            )

    # Provjeri da je svaki origin dijalog riješen
    for invoice_key, dialog_type, display_name in required.origin_dialogs:
        dec = decisions.invoice_decisions.get(invoice_key)
        if dec is None or dec.origin_response is None:
            errors.append(
                f"Nedostaje odgovor za {dialog_type.value.upper()} dijalog "
                f"fakture '{display_name}'"
            )
        elif dec.origin_response.resolution not in (
            OriginDialogResolution.APPLIED,
            OriginDialogResolution.SKIPPED,
        ):
            errors.append(
                f"Nevalidan odgovor za {dialog_type.value.upper()} dijalog "
                f"fakture '{display_name}'"
            )

    return errors


def invoices_to_apply(plan: ImportPlan, decisions: UserDecisions) -> list[PreparedInvoice]:
    """Vrati fakture koje treba primijeniti na draft (nakon korisničkih odluka).

    Plan §16 Faza 4 korak 5: Odustajanje završava bez izmjene drafta.
    Fakture koje je korisnik preskočio (zbog konflikta) se ne primjenjuju.
    """
    if decisions.aborted:
        return []

    result: list[PreparedInvoice] = []
    for inv in plan.invoices:
        # Preskoči ako je korisnik eksplicitno odbio ovu fakturu
        if decisions.is_invoice_aborted(inv.internal_key):
            continue
        result.append(inv)
    return result


def make_aborted_decisions() -> UserDecisions:
    """Kreiraj UserDecisions koji označava odustajanje od cijelog batcha."""
    return UserDecisions(aborted=True)


def make_empty_decisions() -> UserDecisions:
    """Kreiraj prazne UserDecisions (nema odluka — koristi se kad nema konflikata/dijaloga)."""
    return UserDecisions(aborted=False)
