from services.agent.learning.product_similarity_memory_service import (
    ProductSimilaritySource,
    build_similarity_embedding_text,
    build_similarity_source_hash,
    normalize_similarity_text,
)


def _source(**overrides):
    data = {
        "source_table": "catalogs.product_tariff_mapping",
        "source_id": 1,
        "supplier": "  MEDIKO  FARM  ",
        "product_name": "DIXI   dekstroza",
        "origin_country": "DE",
        "preference_code": "EUPR",
        "tariff_code": "17049081",
        "usage_count": 10,
        "confidence": 0.92,
        "metadata": {"product_code": "ABC"},
    }
    data.update(overrides)
    return ProductSimilaritySource(**data)


def test_normalize_similarity_text_compacts_whitespace():
    assert normalize_similarity_text("  A   B\nC  ") == "A B C"


def test_build_similarity_embedding_text_uses_key_context():
    text = build_similarity_embedding_text(_source())

    assert "Naziv robe: DIXI dekstroza" in text
    assert "Dobavljac: MEDIKO FARM" in text
    assert "Zemlja porijekla: DE" in text
    assert "Tarifni broj: 17049081" in text


def test_source_hash_changes_when_tariff_changes():
    first = build_similarity_source_hash(_source(tariff_code="17049081"))
    second = build_similarity_source_hash(_source(tariff_code="21069098"))

    assert first != second
