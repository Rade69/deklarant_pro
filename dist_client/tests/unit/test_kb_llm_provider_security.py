from unittest.mock import MagicMock, patch

from services.knowledge_base.kb_service import KBResult, KnowledgeBaseService


def test_kb_rerank_koristi_centralni_provider():
    provider = MagicMock()
    provider.active_provider.return_value = "groq"
    provider.complete.return_value = "2,1"
    candidates = [
        KBResult("A", "a.pdf", 1, "Prvi", 1.0),
        KBResult("B", "b.pdf", 2, "Drugi", 0.9),
    ]

    service = object.__new__(KnowledgeBaseService)
    with patch(
        "gui.tabs.agent.widgets.llm_provider.LLMProvider",
        return_value=provider,
    ):
        result = service._groq_rerank("pitanje", candidates, 2)

    provider.complete.assert_called_once()
    assert [item.filename for item in result] == ["b.pdf", "a.pdf"]


def test_kb_rerank_bez_providera_cuva_bm25_redoslijed():
    provider = MagicMock()
    provider.active_provider.return_value = "none"
    candidates = [KBResult("A", "a.pdf", 1, "Prvi", 1.0)]

    service = object.__new__(KnowledgeBaseService)
    with patch(
        "gui.tabs.agent.widgets.llm_provider.LLMProvider",
        return_value=provider,
    ):
        result = service._groq_rerank("pitanje", candidates, 1)

    provider.complete.assert_not_called()
    assert result == candidates
