from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from services.agent.learning.product_similarity_embedding_service import (
    ProductSimilarityEmbeddingService,
    SimilarProductMatch,
    extract_required_similarity_tokens,
)


@dataclass(slots=True)
class SimilarTariffGroup:
    tariff_code: str
    total_usage: int = 0
    max_similarity: float = 0.0
    examples: list[SimilarProductMatch] = field(default_factory=list)


@dataclass(slots=True)
class SimilarProductsAssessment:
    query: str
    groups: list[SimilarTariffGroup]
    status: str
    message: str


def analyze_similar_products(
    query: str,
    supplier: str = "",
    origin_country: str = "",
    limit: int = 30,
    search_service: ProductSimilarityEmbeddingService | None = None,
) -> SimilarProductsAssessment:
    text = str(query or "").strip()
    if not text:
        return SimilarProductsAssessment("", [], "NEMA_UPITA", "Nije naveden naziv robe.")

    service = search_service or ProductSimilarityEmbeddingService()
    matches = service.find_similar(
        text,
        supplier=supplier,
        origin_country=origin_country,
        limit=limit,
    )
    groups = _group_by_tariff(matches)
    status, message = _assess_groups(groups)
    return SimilarProductsAssessment(text, groups, status, message)


def render_similar_products_html(assessment: SimilarProductsAssessment) -> str:
    if not assessment.groups:
        return (
            "<b>Slični raniji proizvodi</b><br>"
            f"Upit: <b>{escape(assessment.query)}</b><br><br>"
            f"⚠️ {escape(assessment.message)}"
        )

    rows = []
    total_usage = sum(group.total_usage for group in assessment.groups) or 1
    focus_tokens = extract_required_similarity_tokens(assessment.query)
    for group in assessment.groups:
        share = round(group.total_usage * 100 / total_usage)
        examples = "<br>".join(
            f"• {escape(_format_example_name(example, focus_tokens))} "
            f"(<b>{example.usage_count}x</b>, sličnost {example.similarity:.2f})"
            for example in group.examples[:3]
        )
        rows.append(
            "<tr>"
            f"<td><b>{escape(group.tariff_code)}</b></td>"
            f"<td>{group.total_usage}x</td>"
            f"<td>{share}%</td>"
            f"<td>{group.max_similarity:.2f}</td>"
            f"<td>{examples}</td>"
            "</tr>"
        )

    return (
        "<b>Slični raniji proizvodi</b><br>"
        f"Upit: <b>{escape(assessment.query)}</b><br>"
        f"Status: <b>{escape(assessment.status)}</b> — {escape(assessment.message)}<br><br>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>Tarifa</th><th>Korišteno</th><th>Udio</th><th>Max sličnost</th><th>Primjeri</th></tr>"
        + "".join(rows)
        + "</table><br>"
        "<i>Napomena: ovo je analitička pomoć iz istorije, ne automatska odluka o tarifi.</i>"
    )


def _format_example_name(example: SimilarProductMatch, focus_tokens: list[str]) -> str:
    text = str(example.product_name or example.text_for_embedding or "").strip()
    if not text:
        return ""
    lower = text.lower()
    positions = [lower.find(token) for token in focus_tokens if token and lower.find(token) >= 0]
    if positions:
        start = max(0, min(positions) - 35)
        end = min(len(text), start + 120)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"
    return text[:120] + ("..." if len(text) > 120 else "")


def render_similar_products_for_query(
    query: str,
    supplier: str = "",
    origin_country: str = "",
    search_service: ProductSimilarityEmbeddingService | None = None,
) -> str:
    assessment = analyze_similar_products(
        query,
        supplier=supplier,
        origin_country=origin_country,
        search_service=search_service,
    )
    return render_similar_products_html(assessment)


def _group_by_tariff(matches: list[SimilarProductMatch]) -> list[SimilarTariffGroup]:
    grouped: dict[str, SimilarTariffGroup] = {}
    for match in matches:
        code = match.tariff_code or "NEPOZNATO"
        group = grouped.setdefault(code, SimilarTariffGroup(tariff_code=code))
        group.total_usage += max(1, match.usage_count)
        group.max_similarity = max(group.max_similarity, match.similarity)
        group.examples.append(match)

    for group in grouped.values():
        group.examples.sort(key=lambda item: (item.similarity, item.usage_count), reverse=True)

    return sorted(
        grouped.values(),
        key=lambda item: (item.max_similarity, item.total_usage),
        reverse=True,
    )


def _assess_groups(groups: list[SimilarTariffGroup]) -> tuple[str, str]:
    if not groups:
        return "NEMA_SIGNALA", "Nema dovoljno sličnih ranijih slučajeva."

    total_usage = sum(group.total_usage for group in groups) or 1
    top = groups[0]
    top_share = top.total_usage / total_usage
    strong_similarity = top.max_similarity >= 0.78

    if len(groups) == 1 and strong_similarity:
        return "ISTORIJSKI_JEDNOZNAČNO", "Istorija pokazuje jednu dominantnu tarifu."

    if top_share >= 0.70 and strong_similarity:
        return (
            "ISTORIJSKI_DOMINANTNO",
            f"Tarifa {top.tariff_code} dominira u sličnim ranijim slučajevima.",
        )

    if len(groups) > 1:
        return (
            "KONFLIKT",
            "Slični raniji proizvodi imaju više različitih tarifa; potrebna je ručna provjera.",
        )

    return "SLAB_SIGNAL", "Postoji sličan slučaj, ali pouzdanost nije dovoljna za zaključak."
