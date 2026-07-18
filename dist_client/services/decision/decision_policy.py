"""
Decision Policy — rangiranje kandidata po polju.

Definise redosled izvora za svako polje odluke (tarifa, zemlja, povlastica)
i odlucuje koji kandidati se smiju automatski primijeniti.

Faza 3 ce uvesti pune politike; Faza 2 uvodi minimalni skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.decision.decision_model import DecisionCandidate, FieldDecision


@dataclass
class PolicyContext:
    """Kontekst za evaluaciju politike."""
    normalized_exporter: str = ""
    invoice_number: str = ""
    document_refs: list[str] = field(default_factory=list)
    action_type: str = "preview"  # preview / auto_fill_clicked / dialog_confirmed / manual_edit / draft_restore
    user_identity: str = ""


def rank_tariff_candidates(candidates: list["DecisionCandidate"], context: PolicyContext) -> list["DecisionCandidate"]:
    """
    Rangiraj kandidate za tarifni broj po prioritetu:

    1. Rucno potvrdjena vrijednost (USER source)
    2. Tarifa iz drafta (vec ucitana iz Deklarant Pro nacrta)
    3. Tacan product_code istog izvoznika
    4. Prefix product_code istog izvoznika
    5. Istorija istog izvoznika
    6. Lokalni mapping / fuzzy kandidat
    7. Unknown

    Pravila:
    - Istorija drugog izvoznika je zabranjena
    - Fuzzy threshold >= 0.92
    - Slab kandidat se prikazuje ali se ne primjenjuje
    """
    def _rank(c: "DecisionCandidate") -> tuple[int, float]:
        ev = c.evidence
        if ev is None:
            return (7, 0.0)

        source = ev.source.value
        score = float(ev.score)

        if source == "user":
            return (1, 100.0)
        if source == "document":
            return (2, score)
        if source == "exporter_history":
            return (3, score)
        if source == "tariff_database":
            return (5, score)
        if source == "similarity":
            return (6, score)
        return (7, score)

    return sorted(candidates, key=_rank)


def can_auto_apply_tariff(candidate: "DecisionCandidate", context: PolicyContext) -> bool:
    """Da li se kandidat za tarifu smije automatski primijeniti?"""
    if candidate.evidence is None:
        return False

    # Samo kroz eksplicitnu autorizaciju (Auto-popuni klik)
    if context.action_type not in ("auto_fill_clicked", "dialog_confirmed"):
        return False

    ev = candidate.evidence
    # Mora biti jak dokaz: score >= 85 i potvrdjen izvor
    if ev.score < 85:
        return False
    if ev.requires_confirmation and context.action_type != "dialog_confirmed":
        return False

    return True


def rank_origin_candidates(candidates: list["DecisionCandidate"], context: PolicyContext) -> list["DecisionCandidate"]:
    """
    Rangiraj kandidate za zemlju porijekla:

    1. Rucna potvrda korisnika
    2. Eksplicitna zemlja iz dokumenta (packing lista / faktura / XML)
    3. Parser kandidat iz identifikovanog dokumenta
    4. Mapping/istorija — samo informativno
    5. Unknown

    Pravila:
    - Baza i istorija ne smiju prepisati dokument
    - Konflikt se cuva kao CONFLICT
    - Nepoznata zemlja ostaje prazna
    """
    def _rank(c: "DecisionCandidate") -> tuple[int, float]:
        ev = c.evidence
        if ev is None:
            return (5, 0.0)

        source = ev.source.value
        score = float(ev.score)

        if source == "user":
            return (1, 100.0)
        if source == "document":
            return (2, score)
        if source == "parser":
            return (3, score)
        # mapping i istorija su samo informativni
        return (4, score)

    return sorted(candidates, key=_rank)


def can_auto_apply_origin(candidate: "DecisionCandidate", context: PolicyContext) -> bool:
    """Zemlja porijekla se smije automatski primijeniti samo iz dokumenta."""
    if candidate.evidence is None:
        return False
    if context.action_type not in ("auto_fill_clicked", "dialog_confirmed", "draft_restore"):
        return False
    ev = candidate.evidence
    return ev.source.value in ("document", "parser") and ev.score >= 85


def rank_preference_candidates(candidates: list["DecisionCandidate"], context: PolicyContext) -> list["DecisionCandidate"]:
    """
    Rangiraj kandidate za povlasticu.

    Stroga politika:
    - Samo eksplicitni dokument dokazi (PE1/PE2/PE3)
    - Zemlja porijekla NIJE dokaz povlastice
    - Mapping baza NIJE dokaz povlastice
    - Istorija NIJE dokaz povlastice
    - Parser samo detektuje kandidat
    - Deklarant eksplicitno potvrdjuje ili odbija
    """
    def _rank(c: "DecisionCandidate") -> tuple[int, float]:
        ev = c.evidence
        if ev is None:
            return (5, 0.0)

        source = ev.source.value
        score = float(ev.score)

        if source == "user":
            return (1, 100.0)
        if source == "document":
            doc_code = ev.data.get("doc_code", "")
            if doc_code in ("PE1", "PE2", "PE3"):
                return (2, score)
            return (3, score)
        if source == "parser":
            return (4, score)
        # similarity, tariff_database — ne rangiraju se za povlasticu
        return (5, 0.0)

    return sorted(candidates, key=_rank)


def can_auto_apply_preference(candidate: "DecisionCandidate", context: PolicyContext) -> bool:
    """
    Povlastica se NIKAD ne primjenjuje automatski.
    Cak i PE1/PE2/PE3 zahtijevaju eksplicitnu potvrdu deklaranta.
    """
    if candidate.evidence is None:
        return False
    # Samo kroz eksplicitni dijalog (dialog_confirmed)
    if context.action_type != "dialog_confirmed":
        return False
    ev = candidate.evidence
    doc_code = ev.data.get("doc_code", "")
    return doc_code in ("PE1", "PE2", "PE3") and ev.source.value == "document"