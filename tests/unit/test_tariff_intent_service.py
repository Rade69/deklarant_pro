import re

from services.agent.chat.tariff_intent_service import TariffIntentService, TariffProposal
from services.agent.validation.evidence_model import badge_colors_for_score


def _make_service():
    svc = TariffIntentService(draft=None)
    messages = []
    svc.on_agent_message = messages.append
    return svc, messages


def test_show_proposals_colors_pouzdanost_badge_per_score():
    """Faza 6: prijedlozi tarifa u chatu vizuelno razlikuju jak (90%) od slabog (60%) prijedloga."""
    svc, messages = _make_service()

    proposals = [
        TariffProposal(
            line_index=0,
            naziv_robe="Jak prijedlog",
            product_code="A1",
            proposed_tariff="85168080",
            confidence=0.90,
            source="istorija",
            source_detail="PIP FOOD GROUP DOO, korišteno 6x",
        ),
        TariffProposal(
            line_index=1,
            naziv_robe="Slab prijedlog",
            product_code="B2",
            proposed_tariff="39269097",
            confidence=0.60,
            source="rag",
        ),
    ]

    svc._show_proposals(proposals, [], ukupno_bez=2)

    assert len(messages) == 1
    html = messages[0]

    matches = re.findall(r"background:(#[0-9a-fA-F]+); color:(#[0-9a-fA-F]+)[^>]*>(\d+)%</span>", html)
    by_pct = {pct: (bg, color) for bg, color, pct in matches}

    assert by_pct["90"] == tuple(reversed(badge_colors_for_score(90)))
    assert by_pct["60"] == tuple(reversed(badge_colors_for_score(60)))
    assert by_pct["90"] != by_pct["60"]

    # Izvor mora ostati naveden uz svaki prijedlog
    assert "PIP FOOD GROUP DOO" in html
    assert "istorija" in html
    assert "🤖 AI" in html
