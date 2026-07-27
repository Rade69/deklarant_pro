from types import SimpleNamespace

from services.agent.tariff import tariff_suggestion_service as svc_module
from services.agent.tariff.tariff_suggestion_service import EnhancedTariffSuggestionService


class _Similarity:
    @staticmethod
    def _calculate_similarity(_left, _right):
        return 0.9


def test_historical_suggestions_drop_tariff_missing_from_official_tariff(monkeypatch):
    svc = EnhancedTariffSuggestionService.__new__(EnhancedTariffSuggestionService)
    svc.hybrid_matching = _Similarity()
    svc.profiling_service = SimpleNamespace(
        get_complete_profile=lambda _supplier: SimpleNamespace(
            product_profiles={
                "bad": SimpleNamespace(
                    product_name="GW GEL STITNIK CUKLJEVA MALI PRST",
                    tariff_code="40199090",
                    confidence=0.95,
                    usage_count=10,
                ),
                "good": SimpleNamespace(
                    product_name="GW STITNIK MALI PRST",
                    tariff_code="40149000",
                    confidence=0.80,
                    usage_count=8,
                ),
            }
        )
    )
    monkeypatch.setattr(
        svc_module,
        "_is_known_tariff_code",
        lambda code: code != "40199090",
    )

    suggestions = svc._get_historical_suggestions(
        "GW GEL STITNIK CUKLJEVA MALI PRST",
        "MEDIKO",
        "DE",
    )

    assert [s["tariff_code"] for s in suggestions] == ["40149000"]


def test_contextual_suggestions_drop_tariff_missing_from_official_tariff(monkeypatch):
    svc = EnhancedTariffSuggestionService.__new__(EnhancedTariffSuggestionService)
    svc.hybrid_matching = _Similarity()
    monkeypatch.setattr(svc_module, "_is_known_tariff_code", lambda _code: False)

    suggestions = svc._get_contextual_suggestions(
        "GW GEL STITNIK CUKLJEVA MALI PRST",
        "",
        [
            {
                "naziv_robe": "GW GEL STITNIK CUKLJEVA MALI PRST G 102693500",
                "tarifni_broj": "40199090",
            }
        ],
    )

    assert suggestions == []
