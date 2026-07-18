"""
Evidence Adapters — omotaci oko postojecih izvora dokaza.

Svaki adapter poziva postojeci servis (TariffMappingService, itd.)
i vraca listu DecisionCandidate objekata za zadato polje i stavku.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.decision.decision_model import DecisionCandidate, DecisionField
from core.decision.evidence import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
    evidence_from_preference,
)

if TYPE_CHECKING:
    from core.draft.draft import InvoiceLine
    from services.decision.decision_policy import PolicyContext


def adapt_tariff_evidence(line: "InvoiceLine", context: "PolicyContext") -> list[DecisionCandidate]:
    """
    Prikupi kandidate za tarifni broj iz postojecih izvora:
    - Istorija izvoznika (TariffMappingService.find_mapping)
    - Lokalni mapping

    Ne poziva auto_populate_tariffs() — to pise u InvoiceLine.
    Samo prikuplja kandidate kao Evidence.
    """
    candidates: list[DecisionCandidate] = []

    # Ako vec ima tarifni_broj iz dokumenta — to je DOCUMENT kandidat
    if line.tarifni_broj:
        ev = build_evidence(
            DecisionSource.DOCUMENT,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            "Tarifni broj iz dokumenta.",
            {"tariff": line.tarifni_broj},
        )
        candidates.append(
            DecisionCandidate.make(DecisionField.TARIFF, line.tarifni_broj, ev)
        )

    # Ako ima product_code — trazi mapping
    if line.product_code:
        try:
            from services.tariff_mapping_service import TariffMappingService
            svc = TariffMappingService()
            mapping = svc.find_mapping(
                product_code=line.product_code,
                naziv_robe=line.naziv_robe,
                min_similarity=0.70,
                supplier=context.normalized_exporter,
            )
            if mapping:
                is_same_exporter = (
                    context.normalized_exporter
                    and context.normalized_exporter.upper()
                    in (mapping.naziv_robe or "").upper()
                )
                if is_same_exporter or mapping.usage_count >= 3:
                    conf = (
                        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY
                        if is_same_exporter and mapping.usage_count >= 5
                        else DecisionConfidence.SUGGESTED_BY_SIMILARITY
                    )
                    ev = build_evidence(
                        DecisionSource.EXPORTER_HISTORY if is_same_exporter else DecisionSource.SIMILARITY,
                        conf,
                        f"Mapiranje: {mapping.naziv_robe[:60]} (x{mapping.usage_count})",
                        {
                            "tariff": mapping.tarifni_broj,
                            "product_code": mapping.product_code,
                            "usage_count": mapping.usage_count,
                            "similarity": mapping.similarity,
                        },
                        score=min(95, 70 + mapping.usage_count * 2),
                    )
                    candidates.append(
                        DecisionCandidate.make(DecisionField.TARIFF, mapping.tarifni_broj, ev)
                    )
        except Exception:
            pass

    return candidates


def adapt_origin_evidence(line: "InvoiceLine", context: "PolicyContext") -> list[DecisionCandidate]:
    """
    Prikupi kandidate za zemlju porijekla:
    - Dokumentovana zemlja (iz fakture/PDF-a)
    - Mapping baza
    """
    candidates: list[DecisionCandidate] = []

    # Zemlja iz dokumenta
    if line.zemlja_porijekla:
        has_conflict = line.country_confidence == "CONFLICT"
        ev = build_evidence(
            DecisionSource.DOCUMENT,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            f"Zemlja porijekla iz dokumenta: {line.zemlja_porijekla}",
            {"country": line.zemlja_porijekla, "source": line.country_source},
            requires_confirmation=has_conflict,
            score=100 if not has_conflict else 70,
        )
        candidates.append(
            DecisionCandidate.make(DecisionField.ORIGIN_COUNTRY, line.zemlja_porijekla, ev)
        )

    # Ako postoji konflikt — dodaj i drugu stranu
    if line.country_conflict_details:
        # Parsiraj konflikt (npr. "Dokument: DE, Baza: CN")
        import re
        parts = line.country_conflict_details.split(",")
        for part in parts:
            match = re.search(r"Baza:\s*(\w{2})", part)
            if match:
                conflict_country = match.group(1)
                if conflict_country != line.zemlja_porijekla:
                    ev = build_evidence(
                        DecisionSource.TARIFF_DATABASE,
                        DecisionConfidence.WEAK_GUESS,
                        f"Baza predlaze: {conflict_country}",
                        {"country": conflict_country},
                        requires_confirmation=True,
                        score=50,
                    )
                    candidates.append(
                        DecisionCandidate.make(DecisionField.ORIGIN_COUNTRY, conflict_country, ev)
                    )

    return candidates


def adapt_preference_evidence(line: "InvoiceLine", context: "PolicyContext") -> list[DecisionCandidate]:
    """
    Prikupi kandidate za povlasticu:
    - PE1/PE2/PE3 dokazi iz dokumenta
    - Zemlja porijekla NIJE dokaz (samo informativno)

    Koristi evidence_from_preference() za detekciju.
    """
    candidates: list[DecisionCandidate] = []

    evidence = evidence_from_preference(line)

    if evidence.source == DecisionSource.DOCUMENT:
        # PE1, PE2 ili PE3 — dokument dokaz
        # U Fazi 1-3, ovo postaje CANDIDATE (ne auto_applicable)
        candidates.append(
            DecisionCandidate.make(
                DecisionField.PREFERENCE,
                line.povlastica or evidence.data.get("doc_code", ""),
                evidence,
            )
        )
    elif evidence.source == DecisionSource.SIMILARITY and evidence.score >= 50:
        # Samo informativno — zemlja sugerise povlasticu
        candidates.append(
            DecisionCandidate.make(
                DecisionField.PREFERENCE,
                line.povlastica or "",
                evidence,
            )
        )

    return candidates