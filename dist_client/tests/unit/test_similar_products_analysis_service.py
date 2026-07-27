from services.agent.chat.similar_products_analysis_service import (
    analyze_similar_products,
    render_similar_products_html,
)
from services.agent.learning.product_similarity_embedding_service import SimilarProductMatch


class FakeSearchService:
    def __init__(self, matches):
        self.matches = matches

    def find_similar(self, query_text, supplier="", origin_country="", limit=30, min_similarity=0.0):
        return self.matches[:limit]


def _match(tariff, usage, name, similarity=0.9):
    return SimilarProductMatch(
        source_id=usage,
        supplier="",
        product_name=name,
        origin_country="",
        preference_code="",
        tariff_code=tariff,
        usage_count=usage,
        similarity=similarity,
        text_for_embedding=name,
    )


def test_analyze_similar_products_marks_conflict_for_multiple_tariffs():
    service = FakeSearchService(
        [
            _match("17049081", 10, "DIXI dekstroza"),
            _match("21069092", 8, "DIXI dekstroza 7vit"),
            _match("21069098", 4, "DIXI bombone"),
        ]
    )

    assessment = analyze_similar_products("DIXI dekstroza", search_service=service)

    assert assessment.status == "KONFLIKT"
    assert [group.tariff_code for group in assessment.groups] == ["17049081", "21069092", "21069098"]


def test_analyze_similar_products_orders_by_similarity_before_usage():
    service = FakeSearchService(
        [
            _match("17049071", 33, "generički bomboni", similarity=0.70),
            _match("17049081", 10, "DIXI dekstroza", similarity=0.95),
        ]
    )

    assessment = analyze_similar_products("DIXI dekstroza", search_service=service)

    assert assessment.groups[0].tariff_code == "17049081"


def test_analyze_similar_products_marks_dominant_tariff():
    service = FakeSearchService(
        [
            _match("17049081", 20, "DIXI dekstroza"),
            _match("17049081", 10, "DIXI bombone"),
            _match("21069092", 2, "DIXI stari zapis"),
        ]
    )

    assessment = analyze_similar_products("DIXI dekstroza", search_service=service)

    assert assessment.status == "ISTORIJSKI_DOMINANTNO"
    assert assessment.groups[0].tariff_code == "17049081"


def test_render_similar_products_html_contains_warning():
    service = FakeSearchService([_match("17049081", 10, "DIXI dekstroza")])
    assessment = analyze_similar_products("DIXI dekstroza", search_service=service)

    html = render_similar_products_html(assessment)

    assert "analitička pomoć" in html
    assert "17049081" in html


def test_render_similar_products_html_shows_query_context_in_examples():
    long_prefix = "prehrambeni proizvodi koji nisu spomenuti niti uključeni na drugom mjestu " * 2
    service = FakeSearchService([_match("21069092", 10, f"{long_prefix}DIXI dekstroza 7vit bomb a40")])
    assessment = analyze_similar_products("DIXI dekstroza", search_service=service)

    html = render_similar_products_html(assessment)

    assert "DIXI dekstroza 7vit bomb a40" in html
    assert "prehrambeni proizvodi koji nisu spomenuti niti uključeni" not in html
