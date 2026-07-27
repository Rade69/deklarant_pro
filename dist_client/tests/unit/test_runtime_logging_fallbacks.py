import logging

from database import db
from services import carinski_dokumenti_service
from services.knowledge_base.kb_service import KBResult, KnowledgeBaseService


def test_document_search_logs_connection_error_and_returns_empty(
    caplog,
    monkeypatch,
):
    def _raise_connection_error():
        raise RuntimeError("test konekcija")

    monkeypatch.setattr(db, "get_db_connection", _raise_connection_error)

    with caplog.at_level(
        logging.WARNING,
        logger="deklarant_pro.carinski_dokumenti",
    ):
        result = carinski_dokumenti_service.pretrazi_dokumente("tarifa")

    assert result == []
    assert "test konekcija" in caplog.text


def test_kb_search_logs_rerank_error_and_keeps_bm25_fallback(
    caplog,
    monkeypatch,
):
    service = KnowledgeBaseService()
    service._index_data = [{"chunk_text": "test"}]
    candidates = [
        KBResult("Dokument 1", "jedan.pdf", 1, "Prvi", 2.0),
        KBResult("Dokument 2", "dva.pdf", 2, "Drugi", 1.0),
    ]
    monkeypatch.setattr(service, "_ensure_index", lambda: None)
    monkeypatch.setattr(
        service,
        "_bm25_search",
        lambda _query, top_n: candidates,
    )

    def _raise_rerank_error(_query, _candidates, _top_k):
        raise RuntimeError("test reranking")

    monkeypatch.setattr(service, "_groq_rerank", _raise_rerank_error)

    with caplog.at_level(
        logging.WARNING,
        logger="deklarant_pro.knowledge_base",
    ):
        result = service.search("tarifa", top_k=1, use_reranking=True)

    assert result == candidates[:1]
    assert "test reranking" in caplog.text
