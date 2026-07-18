"""
Kanonski model odluke deklaracije — jedan izvor istine za odluke.

Definise DecisionField, DecisionStatus, DecisionCandidate, FieldDecision
i LineDecisionState — neutralni modeli u core sloju, nezavisni od services.agent.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.decision.evidence import Evidence


class DecisionField(Enum):
    TARIFF = "tariff"
    ORIGIN_COUNTRY = "origin_country"
    PREFERENCE = "preference"


class DecisionStatus(Enum):
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class DecisionCandidate:
    """
    Jedan kandidat za polje odluke.

    candidate_id je deterministicki (MD5 od field+value+source),
    stabilan tokom jedne sesije — UI ne moze potvrditi drugi
    kandidat nakon refresh-a.
    """
    candidate_id: str
    value: str
    evidence: "Evidence | None" = None

    @classmethod
    def make(cls, field: DecisionField, value: str, evidence: "Evidence | None" = None) -> "DecisionCandidate":
        raw = f"{field.value}:{value}:{evidence.source.value if evidence else 'none'}"
        cid = hashlib.md5(raw.encode()).hexdigest()[:12]
        return cls(candidate_id=cid, value=value, evidence=evidence)


@dataclass
class FieldDecision:
    """
    Stanje odluke za jedno polje (tarifa / zemlja / povlastica).

    applied_value je vrijednost koja se STVARNO primjenjuje u deklaraciji.
    Kandidati su svi pronadjeni prijedlozi.
    Samo CONFIRMED status dozvoljava upis applied_value u InvoiceLine.
    """
    field: DecisionField
    status: DecisionStatus = DecisionStatus.UNKNOWN
    applied_value: str = ""
    candidates: list[DecisionCandidate] = field(default_factory=list)
    selected_candidate_id: str = ""
    confirmed_by: str = ""
    confirmed_at: str = ""
    rejection_reason: str = ""

    @property
    def is_confirmed(self) -> bool:
        return self.status == DecisionStatus.CONFIRMED

    @property
    def is_pending(self) -> bool:
        return self.status in (DecisionStatus.CANDIDATE, DecisionStatus.UNKNOWN)

    @property
    def has_conflict(self) -> bool:
        return self.status == DecisionStatus.CONFLICT

    @property
    def is_rejected(self) -> bool:
        return self.status == DecisionStatus.REJECTED

    def add_candidate(self, candidate: DecisionCandidate) -> None:
        for existing in self.candidates:
            if existing.candidate_id == candidate.candidate_id:
                return
        self.candidates.append(candidate)
        if self.status == DecisionStatus.UNKNOWN:
            self.status = DecisionStatus.CANDIDATE

    def to_dict(self) -> dict:
        return {
            "field": self.field.value,
            "status": self.status.value,
            "applied_value": self.applied_value,
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "value": c.value,
                    "evidence": c.evidence.to_dict() if c.evidence else None,
                }
                for c in self.candidates
            ],
            "selected_candidate_id": self.selected_candidate_id,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FieldDecision":
        from core.decision.evidence import Evidence, DecisionSource, DecisionConfidence

        fd = cls(
            field=DecisionField(data.get("field", "tariff")),
            status=DecisionStatus(data.get("status", "unknown")),
            applied_value=data.get("applied_value", ""),
            selected_candidate_id=data.get("selected_candidate_id", ""),
            confirmed_by=data.get("confirmed_by", ""),
            confirmed_at=data.get("confirmed_at", ""),
            rejection_reason=data.get("rejection_reason", ""),
        )
        for c_data in data.get("candidates", []):
            ev_data = c_data.get("evidence")
            ev = None
            if ev_data:
                ev = Evidence(
                    source=DecisionSource(ev_data.get("source", "parser")),
                    confidence=DecisionConfidence(ev_data.get("confidence", "unknown")),
                    reason=ev_data.get("reason", ""),
                    data=ev_data.get("data", {}),
                    requires_confirmation=ev_data.get("requires_confirmation", True),
                    score=ev_data.get("score", 0),
                )
            fd.candidates.append(
                DecisionCandidate(
                    candidate_id=c_data.get("candidate_id", ""),
                    value=c_data.get("value", ""),
                    evidence=ev,
                )
            )
        return fd


@dataclass
class LineDecisionState:
    """
    Stanje svih odluka za jednu fakturnu stavku (InvoiceLine).

    Sadrzi po jedan FieldDecision za tarifu, zemlju porijekla i povlasticu.
    """
    tariff: FieldDecision = field(default_factory=lambda: FieldDecision(field=DecisionField.TARIFF))
    origin_country: FieldDecision = field(default_factory=lambda: FieldDecision(field=DecisionField.ORIGIN_COUNTRY))
    preference: FieldDecision = field(default_factory=lambda: FieldDecision(field=DecisionField.PREFERENCE))

    def get(self, field: DecisionField) -> FieldDecision:
        if field == DecisionField.TARIFF:
            return self.tariff
        if field == DecisionField.ORIGIN_COUNTRY:
            return self.origin_country
        return self.preference

    @property
    def all_confirmed(self) -> bool:
        return (
            self.tariff.is_confirmed
            and self.origin_country.is_confirmed
            and self.preference.status
            in (DecisionStatus.CONFIRMED, DecisionStatus.REJECTED, DecisionStatus.UNKNOWN)
        )

    def to_dict(self) -> dict:
        return {
            "tariff": self.tariff.to_dict(),
            "origin_country": self.origin_country.to_dict(),
            "preference": self.preference.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "LineDecisionState":
        if not data:
            return cls()
        return cls(
            tariff=FieldDecision.from_dict(data.get("tariff", {})),
            origin_country=FieldDecision.from_dict(data.get("origin_country", {})),
            preference=FieldDecision.from_dict(data.get("preference", {})),
        )