"""
Declaration Decision Service — jedini servis za procjenu i primjenu odluka.

Centralizuje svu logiku odlucivanja o tarifi, zemlji porijekla i povlastici.
Ovo je JEDINO mjesto koje smije upisati izvedene vrijednosti u InvoiceLine.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from core.decision.decision_model import (
    DecisionCandidate,
    DecisionField,
    DecisionStatus,
    FieldDecision,
    LineDecisionState,
)
from core.decision.evidence import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
)

if TYPE_CHECKING:
    from core.draft.draft import InvoiceLine, DeclarationDraft
    from services.decision.decision_policy import PolicyContext

logger = logging.getLogger("deklarant_pro.decision_service")


@dataclass
class DecisionEvaluationReport:
    """Izvjestaj evaluacije draft-a ili linije."""
    lines_evaluated: int = 0
    fields_total: int = 0
    confirmed: int = 0
    candidate: int = 0
    unknown: int = 0
    conflict: int = 0
    rejected: int = 0
    line_reports: dict[int, LineDecisionState] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return self.unknown > 0 or self.conflict > 0


@dataclass
class Authorization:
    """Autorizacija za primjenu odluke."""
    action_type: str = "preview"  # preview / auto_fill_clicked / dialog_confirmed / manual_edit
    user_identity: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DeclarationDecisionService:
    """
    Jedini servis koji donosi i primjenjuje odluke o tarifi, zemlji i povlastici.

    Javni API:
    - evaluate_line() → LineDecisionState
    - evaluate_draft() → DecisionEvaluationReport
    - apply_candidate() → FieldDecision
    - confirm_manual_value() → FieldDecision
    - reject_candidate() → FieldDecision
    """

    def __init__(self):
        self._last_report: DecisionEvaluationReport | None = None

    # ── EVALUATE (read-only) ──────────────────────────────────────────

    def evaluate_line(
        self,
        line: "InvoiceLine",
        context: "PolicyContext | None" = None,
        fields: list[DecisionField] | None = None,
    ) -> LineDecisionState:
        """
        Evaluacija jedne fakturne stavke. READ-ONLY — ne mijenja InvoiceLine
        niti njegov decision_state.

        Ako line vec ima decision_state, evaluacija se radi na kopiji tako da
        originalni state ostane nepromijenjen.

        Args:
            line: Fakturna stavka
            context: PolicyContext sa izvoznikom, brojem fakture, tipom akcije
            fields: Koja polja evaluirati (None = sva tri)

        Returns:
            Novi LineDecisionState sa kandidatima i statusima
        """
        import copy

        from services.decision.evidence_adapters import (
            adapt_tariff_evidence,
            adapt_origin_evidence,
            adapt_preference_evidence,
        )
        from services.decision.decision_policy import (
            PolicyContext,
            rank_tariff_candidates,
            rank_origin_candidates,
            rank_preference_candidates,
        )

        ctx = context or PolicyContext()
        target_fields = fields or [DecisionField.TARIFF, DecisionField.ORIGIN_COUNTRY, DecisionField.PREFERENCE]

        # Radi na kopiji postojeceg state-a — ne mutiraj original
        existing = line.decision_state
        if existing is not None:
            state = copy.deepcopy(existing)
        else:
            state = LineDecisionState()

        # Evaluacija tarife
        if DecisionField.TARIFF in target_fields:
            candidates = adapt_tariff_evidence(line, ctx)
            ranked = rank_tariff_candidates(candidates, ctx)
            fd = self._build_field_decision(DecisionField.TARIFF, ranked, state.tariff)
            state.tariff = fd

        # Evaluacija zemlje porijekla
        if DecisionField.ORIGIN_COUNTRY in target_fields:
            candidates = adapt_origin_evidence(line, ctx)
            ranked = rank_origin_candidates(candidates, ctx)
            fd = self._build_field_decision(DecisionField.ORIGIN_COUNTRY, ranked, state.origin_country)
            state.origin_country = fd

        # Evaluacija povlastice
        if DecisionField.PREFERENCE in target_fields:
            candidates = adapt_preference_evidence(line, ctx)
            ranked = rank_preference_candidates(candidates, ctx)
            fd = self._build_field_decision(DecisionField.PREFERENCE, ranked, state.preference)
            state.preference = fd

        return state

    def evaluate_draft(
        self,
        draft: "DeclarationDraft",
        context: "PolicyContext | None" = None,
        fields: list[DecisionField] | None = None,
    ) -> DecisionEvaluationReport:
        """
        Evaluacija cijelog draft-a. READ-ONLY — ne mijenja draft.

        Returns:
            DecisionEvaluationReport sa statistikom
        """
        report = DecisionEvaluationReport()

        for idx, line in enumerate(draft.invoice_lines):
            state = self.evaluate_line(line, context, fields)
            report.line_reports[idx] = state

            for fd in [state.tariff, state.origin_country, state.preference]:
                report.fields_total += 1
                if fd.status == DecisionStatus.CONFIRMED:
                    report.confirmed += 1
                elif fd.status == DecisionStatus.CANDIDATE:
                    report.candidate += 1
                elif fd.status == DecisionStatus.UNKNOWN:
                    report.unknown += 1
                elif fd.status == DecisionStatus.CONFLICT:
                    report.conflict += 1
                elif fd.status == DecisionStatus.REJECTED:
                    report.rejected += 1

        report.lines_evaluated = len(draft.invoice_lines)
        self._last_report = report
        return report

    # ── APPLY (write) ──────────────────────────────────────────────────

    def apply_candidate(
        self,
        line: "InvoiceLine",
        field: DecisionField,
        candidate_id: str,
        authorization: Authorization,
    ) -> FieldDecision:
        """
        Primijeni odabranog kandidata na InvoiceLine.

        Ovo je JEDINA metoda koja smije upisati izvedenu vrijednost.
        """
        state = line.decision_state
        if state is None:
            state = LineDecisionState()
            line.decision_state = state

        fd = state.get(field)
        if fd.status == DecisionStatus.CONFIRMED:
            return fd  # Vec potvrdjeno

        # Pronadji kandidata
        target = None
        for c in fd.candidates:
            if c.candidate_id == candidate_id:
                target = c
                break

        if target is None:
            raise ValueError(f"Kandidat {candidate_id} nije pronadjen za {field.value}")

        fd.status = DecisionStatus.CONFIRMED
        fd.applied_value = target.value
        fd.selected_candidate_id = candidate_id
        fd.confirmed_by = authorization.user_identity or "deklarant"
        fd.confirmed_at = authorization.timestamp

        # Upisi primijenjenu vrijednost u direktno polje InvoiceLine
        self._write_applied_value(line, field, target.value)

        return fd

    def confirm_manual_value(
        self,
        line: "InvoiceLine",
        field: DecisionField,
        value: str,
        authorization: Authorization,
    ) -> FieldDecision:
        """
        Potvrdi rucno unesenu vrijednost (zaobilazi kandidate).
        """
        state = line.decision_state
        if state is None:
            state = LineDecisionState()
            line.decision_state = state

        fd = state.get(field)

        user_ev = build_evidence(
            DecisionSource.USER,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            f"Rucno potvrdjeno: {value}",
            {"manual_value": value},
            requires_confirmation=False,
            score=100,
        )
        candidate = DecisionCandidate.make(field, value, user_ev)
        fd.add_candidate(candidate)

        fd.status = DecisionStatus.CONFIRMED
        fd.applied_value = value
        fd.selected_candidate_id = candidate.candidate_id
        fd.confirmed_by = authorization.user_identity or "deklarant"
        fd.confirmed_at = authorization.timestamp

        self._write_applied_value(line, field, value)

        return fd

    def reject_candidate(
        self,
        line: "InvoiceLine",
        field: DecisionField,
        candidate_id: str,
        authorization: Authorization,
        reason: str = "",
    ) -> FieldDecision:
        """
        Odbij kandidata. Pamti se tokom sesije.
        """
        state = line.decision_state
        if state is None:
            state = LineDecisionState()
            line.decision_state = state

        fd = state.get(field)
        fd.status = DecisionStatus.REJECTED
        fd.rejection_reason = reason or "Odbijeno od strane deklaranta"
        fd.applied_value = ""
        fd.confirmed_by = authorization.user_identity or "deklarant"
        fd.confirmed_at = authorization.timestamp

        # Ocisti direktno polje
        self._clear_applied_value(line, field)

        return fd

    # ── INTERNAL ────────────────────────────────────────────────────────

    def _build_field_decision(
        self,
        field: DecisionField,
        ranked: list[DecisionCandidate],
        existing: FieldDecision | None = None,
    ) -> FieldDecision:
        """Izgradi FieldDecision iz rangiranih kandidata, cuvajuci postojece potvrde."""
        # Ako vec postoji potvrdjeno stanje, zadrzi ga
        if existing is not None and existing.status in (
            DecisionStatus.CONFIRMED,
            DecisionStatus.REJECTED,
        ):
            fd = existing
            # Dodaj nove kandidate (ne dupliraj)
            for c in ranked:
                fd.add_candidate(c)
            return fd

        fd = FieldDecision(field=field)
        for c in ranked:
            fd.add_candidate(c)

        # Ako ima kandidate a nije potvrdjeno — ostaje CANDIDATE
        # Ako ima vise kandidata sa razlicitim izvorima — CONFLICT?
        if len(ranked) >= 2:
            sources = {c.evidence.source for c in ranked if c.evidence}
            if len(sources) >= 2 and field == DecisionField.ORIGIN_COUNTRY:
                fd.status = DecisionStatus.CONFLICT

        return fd

    def _write_applied_value(self, line: "InvoiceLine", field: DecisionField, value: str) -> None:
        """Upisi primijenjenu vrijednost u direktno polje InvoiceLine."""
        if field == DecisionField.TARIFF:
            line.tarifni_broj = value
        elif field == DecisionField.ORIGIN_COUNTRY:
            line.zemlja_porijekla = value
        elif field == DecisionField.PREFERENCE:
            line.povlastica = value

    def _clear_applied_value(self, line: "InvoiceLine", field: DecisionField) -> None:
        """Ocisti direktno polje InvoiceLine."""
        if field == DecisionField.TARIFF:
            line.tarifni_broj = ""
        elif field == DecisionField.ORIGIN_COUNTRY:
            line.zemlja_porijekla = ""
        elif field == DecisionField.PREFERENCE:
            line.povlastica = ""