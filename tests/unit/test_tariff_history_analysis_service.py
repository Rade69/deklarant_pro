from services.agent.chat.tariff_history_analysis_service import (
    TariffCandidate,
    TariffLineContext,
    _PgData,
    _assess,
)


def test_assess_ok_when_mapping_supports_current_code():
    ctx = TariffLineContext(
        ordinal="1",
        current_code="63079099",
        description="BORT ortopedsko pomagalo",
    )
    pg = _PgData(
        candidates={
            "1": [
                TariffCandidate(
                    code="63079099",
                    description="BORT ortopedsko pomagalo",
                    usage_count=12,
                    score=82,
                )
            ]
        },
        current_counts={"63079099": 12},
        official={"63079099": "Ostali gotovi proizvodi"},
    )

    result = _assess(ctx, 20, pg)

    assert result.status == "OK"
    assert result.best_candidate.code == "63079099"


def test_assess_risk_when_strong_candidate_disagrees():
    ctx = TariffLineContext(
        ordinal="18",
        current_code="63079099",
        description="BORT ortopedsko pomagalo",
    )
    pg = _PgData(
        candidates={
            "18": [
                TariffCandidate(
                    code="90219090",
                    description="BORT ortopedsko pomagalo",
                    usage_count=41,
                    score=88,
                )
            ]
        },
        current_counts={"63079099": 1},
        official={"63079099": "Ostali gotovi proizvodi"},
    )

    result = _assess(ctx, 1, pg)

    assert result.status == "RIZIK"
    assert "90219090" in result.reason


def test_assess_feedback_accepts_current_code():
    ctx = TariffLineContext(
        ordinal="2",
        current_code="17049081",
        description="DIXI dekstroza",
    )
    pg = _PgData(
        candidates={
            "2": [
                TariffCandidate(
                    code="17049081",
                    description="DIXI dekstroza",
                    usage_count=3,
                    score=91,
                    source="feedback",
                    action_type="accept",
                )
            ]
        },
        current_counts={"17049081": 3},
        official={"17049081": "Proizvodi od secera"},
    )

    result = _assess(ctx, 0, pg)

    assert result.status == "OK"
    assert "Ranije prihvaceno" in result.reason


def test_assess_feedback_reject_keeps_current_code():
    ctx = TariffLineContext(
        ordinal="3",
        current_code="63079099",
        description="BORT palac lev XL",
    )
    pg = _PgData(
        candidates={
            "3": [
                TariffCandidate(
                    code="63079099",
                    description="BORT palac lev XL",
                    usage_count=1,
                    score=61,
                    source="feedback",
                    action_type="reject",
                )
            ]
        },
        current_counts={"63079099": 1},
    )

    result = _assess(ctx, 0, pg)

    assert result.status == "OK"
    assert "Ranije odbijen" in result.reason
