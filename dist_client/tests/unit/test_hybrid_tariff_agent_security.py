from unittest.mock import MagicMock, patch


def test_ai_decision_koristi_centralni_provider():
    provider = MagicMock()
    provider.active_provider.return_value = "groq"
    provider.complete.return_value = "1"

    with patch(
        "gui.tabs.agent.widgets.llm_provider.LLMProvider",
        return_value=provider,
    ):
        from services.agent.tariff.hybrid_tariff_agent import AIDecisionService

        result = AIDecisionService().decide_tariff(
            "test proizvod",
            [{"tarifni_broj": "08052190", "naziv_robe": "test", "confidence": 0.9}],
        )

    provider.complete.assert_called_once()
    assert result["tarifni_broj"] == "08052190"


def test_ai_ne_generise_tarifu_bez_lokalnog_kandidata():
    provider = MagicMock()
    provider.active_provider.return_value = "groq"

    with patch(
        "gui.tabs.agent.widgets.llm_provider.LLMProvider",
        return_value=provider,
    ):
        from services.agent.tariff.hybrid_tariff_agent import AIDecisionService

        result = AIDecisionService().decide_tariff("nepoznat proizvod", [])

    provider.complete.assert_not_called()
    assert result["tarifni_broj"] == ""
    assert result["source"] == "none"
