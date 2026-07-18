"""
Evidence model — compatibility re-export.

Sav kod je premjesten u core/decision/evidence.py.
Ovaj modul ostaje zbog backward compatibility-ja za postojece importe.
"""

# Re-export svega iz neutralnog core sloja
from core.decision.evidence import (  # noqa: F401
    DecisionSource,
    DecisionConfidence,
    DecisionScoreCategory,
    Evidence,
    build_evidence,
    evidence_from_tariff_decision,
    evidence_from_preference,
    tariff_confidence_label,
    evidence_badge_colors,
    badge_colors_for_score,
    evidence_score_category,
)
