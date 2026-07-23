"""
TariffHistoryAnalysisService - uporedi tarifne brojeve u aktivnom draftu
sa historijom proizvoda, korisnickim feedbackom i zvanicnom tarifom.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html import escape
from typing import Any

logger = logging.getLogger("deklarant_pro.agent.tariff_history_analysis")


def _resolve_db_path() -> str:
    """
    Pronađi deklarant_sistem.db: probaj više lokacija jer PyInstaller frozen
    build ima __file__ unutar _internal/ bundle-a dok stvarna (read-write)
    baza živi pored .exe-a. Vidi gui/tabs/sifarnici/tariff_hierarchy.py::
    _resolve_db_path() za isti obrazac/objašnjenje.
    """
    candidates = [
        os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "database", "deklarant_sistem.db"
        )),
    ]
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'database', 'deklarant_sistem.db'))
    candidates.append(os.path.join('database', 'deklarant_sistem.db'))

    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


_DB_PATH = _resolve_db_path()

_STOP_WORDS = {
    "the", "and", "for", "with", "without", "kom", "set", "pcs", "art", "type",
    "tip", "model", "sifra", "code", "broj", "robe", "proizvod", "ostalo",
}


@dataclass(slots=True)
class TariffLineContext:
    ordinal: str
    current_code: str
    description: str
    product_code: str = ""
    origin_country: str = ""
    supplier: str = ""


@dataclass(slots=True)
class TariffCandidate:
    code: str
    description: str
    product_code: str = ""
    origin_country: str = ""
    supplier: str = ""
    usage_count: int = 0
    score: int = 0
    source: str = "mapping"
    action_type: str = ""


@dataclass(slots=True)
class TariffAssessment:
    line: TariffLineContext
    official_description: str = ""
    sqlite_count: int = 0
    current_mapping_count: int = 0
    best_candidate: TariffCandidate | None = None
    feedback_candidate: TariffCandidate | None = None
    status: str = "PROVJERI"
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _PgData:
    candidates: dict[str, list[TariffCandidate]] = field(default_factory=dict)
    current_counts: dict[str, int] = field(default_factory=dict)
    official: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _norm_text(value: Any) -> str:
    text = re.sub(r"[^\w]+", " ", str(value or "").upper(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: str, limit: int = 5) -> list[str]:
    tokens = []
    for token in _norm_text(value).split():
        if len(token) < 3 or token.lower() in _STOP_WORDS:
            continue
        if token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _similarity(a: str, b: str) -> float:
    a_norm = _norm_text(a)
    b_norm = _norm_text(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _same_code(a: str, b: str) -> bool:
    a_digits = _digits(a)
    b_digits = _digits(b)
    return bool(a_digits and b_digits and a_digits[:8] == b_digits[:8])


def _supplier_from_draft(draft) -> str:
    for attr in ("izvoznik_naziv", "exporter_name", "supplier_name"):
        value = getattr(draft, attr, "") if draft else ""
        if value:
            return str(value).strip()
    return ""


def _line_supplier(line: Any, fallback: str) -> str:
    for attr in ("exporter", "supplier"):
        party = getattr(line, attr, None)
        if not party:
            continue
        name = getattr(party, "name", "") if not isinstance(party, str) else party
        if name:
            return str(name).strip()
    return fallback


def _collect_line_contexts(draft) -> list[TariffLineContext]:
    if not draft:
        return []

    fallback_supplier = _supplier_from_draft(draft)
    invoice_lines = list(getattr(draft, "invoice_lines", None) or [])
    contexts: list[TariffLineContext] = []

    if getattr(draft, "items", None):
        for item in draft.items:
            code = _digits(getattr(item, "tariff_code", "") or "")
            if not code:
                continue
            ordinal_no = getattr(item, "ordinal_no", "") or len(contexts) + 1
            assigned_lines = [
                line for line in invoice_lines
                if getattr(line, "assigned_naimenovanje_ordinal", 0) == ordinal_no
            ]
            names = [
                getattr(item, "goods_trade_name", "") or "",
                getattr(item, "goods_description", "") or "",
            ]
            names.extend(getattr(line, "naziv_robe", "") or "" for line in assigned_lines)
            product_code = next(
                (getattr(line, "product_code", "") or "" for line in assigned_lines
                 if getattr(line, "product_code", "") or ""),
                "",
            )
            supplier = next(
                (_line_supplier(line, fallback_supplier) for line in assigned_lines
                 if _line_supplier(line, fallback_supplier)),
                fallback_supplier,
            )
            description = _compact_descriptions(names)
            contexts.append(
                TariffLineContext(
                    ordinal=str(ordinal_no),
                    current_code=code,
                    description=description,
                    product_code=product_code,
                    origin_country=getattr(item, "origin_country_code", "") or "",
                    supplier=supplier,
                )
            )
        return contexts

    seen: set[tuple[str, str, str]] = set()
    for index, line in enumerate(invoice_lines, start=1):
        code = _digits(getattr(line, "tarifni_broj", "") or "")
        if not code:
            continue
        key = (
            code,
            _norm_text(getattr(line, "naziv_robe", "") or "")[:80],
            str(getattr(line, "zemlja_porijekla", "") or "").upper(),
        )
        if key in seen:
            continue
        seen.add(key)
        contexts.append(
            TariffLineContext(
                ordinal=str(getattr(line, "line_no", 0) or index),
                current_code=code,
                description=getattr(line, "naziv_robe", "") or "",
                product_code=getattr(line, "product_code", "") or "",
                origin_country=getattr(line, "zemlja_porijekla", "") or "",
                supplier=_line_supplier(line, fallback_supplier),
            )
        )
    return contexts


def _compact_descriptions(values: list[str]) -> str:
    parts = []
    for value in values:
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if value and value not in parts:
            parts.append(value)
    return "; ".join(parts)[:240]


def _sqlite_history(codes: list[str]) -> dict[str, int]:
    if not codes:
        return {}
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(codes))
        cur.execute(
            f"SELECT tariff_code, SUM(count) FROM tariff_doc_history "
            f"WHERE tariff_code IN ({placeholders}) GROUP BY tariff_code",
            codes,
        )
        result = {str(r[0]): int(r[1] or 0) for r in cur.fetchall()}
        conn.close()
        return result
    except Exception as exc:
        logger.warning("SQLite tariff_doc_history greska: %s", exc)
        return {}


def _pg_data(contexts: list[TariffLineContext]) -> _PgData:
    data = _PgData()
    if not contexts:
        return data

    codes = list(dict.fromkeys(ctx.current_code[:8] for ctx in contexts if ctx.current_code))
    try:
        from database.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                data.current_counts = _pg_current_counts(cur, codes)
                data.official = _pg_official_descriptions(cur, codes)
                for ctx in contexts:
                    data.candidates[ctx.ordinal] = _pg_candidates_for_line(cur, ctx)
                    feedback = _pg_feedback_for_line(cur, ctx)
                    if feedback:
                        data.candidates.setdefault(ctx.ordinal, []).extend(feedback)
    except Exception as exc:
        logger.warning("PG tariff intelligence greska: %s", exc)
        data.warnings.append("PostgreSQL historija nije dostupna; prikaz je parcijalan.")
    return data


def _pg_current_counts(cur, codes: list[str]) -> dict[str, int]:
    if not codes:
        return {}
    cur.execute(
        """
        SELECT LEFT(commodity_code, 8) AS code, SUM(usage_count) AS total
        FROM catalogs.product_tariff_mapping
        WHERE LEFT(commodity_code, 8) = ANY(%s)
        GROUP BY LEFT(commodity_code, 8)
        """,
        (codes,),
    )
    return {row["code"]: int(row["total"] or 0) for row in cur.fetchall()}


def _pg_official_descriptions(cur, codes: list[str]) -> dict[str, str]:
    if not codes:
        return {}
    cur.execute(
        """
        SELECT DISTINCT ON (LEFT(tarifni_kod, 8))
               LEFT(tarifni_kod, 8) AS code, opis
        FROM catalogs.zvanicna_tarifa
        WHERE LEFT(tarifni_kod, 8) = ANY(%s)
        ORDER BY LEFT(tarifni_kod, 8), LENGTH(tarifni_kod) DESC
        """,
        (codes,),
    )
    return {row["code"]: row["opis"] or "" for row in cur.fetchall()}


def _pg_candidates_for_line(cur, ctx: TariffLineContext) -> list[TariffCandidate]:
    clauses = []
    params: list[Any] = []

    if ctx.product_code:
        clauses.append("product_code ILIKE %s")
        params.append(ctx.product_code.strip())

    for token in _tokens(ctx.description, limit=4):
        clauses.append("naziv_robe ILIKE %s")
        params.append(f"%{token}%")

    if not clauses:
        return []

    cur.execute(
        f"""
        SELECT product_code, naziv_robe, commodity_code, zemlja_porijekla,
               povlastica, usage_count, supplier
        FROM catalogs.product_tariff_mapping
        WHERE {" OR ".join(clauses)}
        ORDER BY usage_count DESC NULLS LAST
        LIMIT 120
        """,
        tuple(params),
    )

    grouped: dict[str, TariffCandidate] = {}
    for row in cur.fetchall():
        candidate = _score_mapping_row(ctx, row)
        if candidate.score < 42:
            continue
        previous = grouped.get(candidate.code[:8])
        if not previous or candidate.score > previous.score:
            grouped[candidate.code[:8]] = candidate

    return sorted(grouped.values(), key=lambda c: c.score, reverse=True)[:5]


def _pg_feedback_for_line(cur, ctx: TariffLineContext) -> list[TariffCandidate]:
    tokens = _tokens(ctx.description, limit=3)
    params: list[Any] = [ctx.current_code[:8], ctx.current_code[:8]]
    clauses = [
        "LEFT(COALESCE(new_value, ''), 8) = %s",
        "LEFT(COALESCE(original_value, ''), 8) = %s",
    ]
    for token in tokens:
        clauses.append("context->>'naziv_robe_original' ILIKE %s")
        params.append(f"%{token}%")

    cur.execute(
        f"""
        SELECT action_type, original_value, new_value, confidence, context
        FROM catalogs.user_feedback
        WHERE item_type = 'tariff_validation'
          AND action_type IN ('accept', 'reject')
          AND ({" OR ".join(clauses)})
        ORDER BY created_at DESC
        LIMIT 40
        """,
        tuple(params),
    )

    candidates: dict[str, TariffCandidate] = {}
    for row in cur.fetchall():
        context = row["context"] or {}
        feedback_name = context.get("naziv_robe_original") or context.get("naziv_robe_historijski") or ""
        similarity = _similarity(ctx.description, feedback_name)
        if tokens and similarity < 0.45:
            continue
        code = _digits(row["new_value"] if row["action_type"] == "accept" else row["original_value"])
        if not code:
            continue
        score = 70 + int(similarity * 20)
        if row["action_type"] == "reject":
            score = 55 + int(similarity * 15)
        candidate = TariffCandidate(
            code=code[:8],
            description=feedback_name,
            usage_count=int(context.get("usage_count") or 0),
            score=min(score, 95),
            source="feedback",
            action_type=row["action_type"],
        )
        previous = candidates.get(candidate.code)
        if not previous or candidate.score > previous.score:
            candidates[candidate.code] = candidate
    return sorted(candidates.values(), key=lambda c: c.score, reverse=True)


def _score_mapping_row(ctx: TariffLineContext, row: dict[str, Any]) -> TariffCandidate:
    code = _digits(row["commodity_code"])[:8]
    name_similarity = _similarity(ctx.description, row["naziv_robe"] or "")
    product_match = bool(
        ctx.product_code
        and row["product_code"]
        and _norm_text(ctx.product_code) == _norm_text(row["product_code"])
    )
    country_match = bool(
        ctx.origin_country
        and row["zemlja_porijekla"]
        and ctx.origin_country.upper() == str(row["zemlja_porijekla"]).upper()
    )
    supplier_match = bool(
        ctx.supplier
        and row["supplier"]
        and (
            _norm_text(ctx.supplier) in _norm_text(row["supplier"])
            or _norm_text(row["supplier"]) in _norm_text(ctx.supplier)
        )
    )
    usage = int(row["usage_count"] or 0)

    score = int(name_similarity * 55)
    if product_match:
        score += 30
    if country_match:
        score += 8
    if supplier_match:
        score += 10
    score += min(usage, 50) // 5

    return TariffCandidate(
        code=code,
        description=row["naziv_robe"] or "",
        product_code=row["product_code"] or "",
        origin_country=row["zemlja_porijekla"] or "",
        supplier=row["supplier"] or "",
        usage_count=usage,
        score=min(score, 100),
        source="mapping",
    )


def _assess(ctx: TariffLineContext, sqlite_count: int, pg_data: _PgData) -> TariffAssessment:
    code8 = ctx.current_code[:8]
    candidates = pg_data.candidates.get(ctx.ordinal, [])
    best = candidates[0] if candidates else None
    feedback = next((c for c in candidates if c.source == "feedback"), None)

    assessment = TariffAssessment(
        line=ctx,
        official_description=pg_data.official.get(code8, ""),
        sqlite_count=sqlite_count,
        current_mapping_count=pg_data.current_counts.get(code8, 0),
        best_candidate=best,
        feedback_candidate=feedback,
        warnings=list(pg_data.warnings),
    )

    if feedback and feedback.action_type == "accept" and _same_code(ctx.current_code, feedback.code):
        assessment.status = "OK"
        assessment.best_candidate = feedback
        assessment.reason = "Ranije prihvaceno za slican naziv robe."
        return assessment

    if feedback and feedback.action_type == "reject" and _same_code(ctx.current_code, feedback.code):
        assessment.status = "OK"
        assessment.best_candidate = feedback
        assessment.reason = "Ranije odbijen drugi prijedlog; trenutni tarifni ostaje vjerovatniji."
        return assessment

    if best and not _same_code(ctx.current_code, best.code) and best.score >= 78:
        assessment.status = "RIZIK"
        assessment.reason = (
            f"Historija za slicnu robu jace vodi na {best.code} "
            f"(score {best.score})."
        )
        return assessment

    if best and not _same_code(ctx.current_code, best.code) and best.score >= 62:
        assessment.status = "PROVJERI"
        assessment.reason = (
            f"Postoji slican historijski kandidat {best.code} "
            f"(score {best.score})."
        )
        return assessment

    if best and _same_code(ctx.current_code, best.code) and best.score >= 58:
        assessment.status = "OK"
        assessment.reason = f"Naziv robe se poklapa sa historijom za isti tarifni broj (score {best.score})."
        return assessment

    if assessment.current_mapping_count or sqlite_count:
        assessment.status = "PROVJERI"
        assessment.reason = "Tarifni broj postoji u historiji, ali nema jakog poklapanja naziva robe."
        return assessment

    if assessment.official_description:
        assessment.status = "PROVJERI"
        assessment.reason = "Tarifni broj postoji u zvanicnoj tarifi, ali nije nadjen u praksi."
        return assessment

    assessment.status = "RIZIK"
    assessment.reason = "Tarifni broj nije nadjen ni u historiji ni u zvanicnoj tarifi."
    return assessment


def analiziraj_tarifne_historiju(draft) -> str:
    contexts = _collect_line_contexts(draft)
    if not contexts:
        return "Nema tarifnih brojeva u aktivnoj deklaraciji. Ucitaj fakturu i kreiraj naimenovanja."

    unique_codes = list(dict.fromkeys(ctx.current_code[:8] for ctx in contexts))
    sqlite_counts = _sqlite_history(unique_codes)
    pg_data = _pg_data(contexts)
    assessments = [
        _assess(ctx, sqlite_counts.get(ctx.current_code[:8], 0), pg_data)
        for ctx in contexts
    ]

    return _render_html(assessments)


def _render_html(assessments: list[TariffAssessment]) -> str:
    counts = {"OK": 0, "PROVJERI": 0, "RIZIK": 0}
    for item in assessments:
        counts[item.status] = counts.get(item.status, 0) + 1

    status_color = "#27ae60" if counts["RIZIK"] == 0 else "#c0392b"
    summary = (
        f"OK: {counts['OK']} | Provjeri: {counts['PROVJERI']} | Rizik: {counts['RIZIK']}"
    )

    rows = []
    for item in assessments:
        rows.append(_render_row(item))

    warnings = sorted({warning for item in assessments for warning in item.warnings})
    warning_html = ""
    if warnings:
        warning_html = (
            "<br><small style='color:#c0392b;'>"
            + "<br>".join(escape(warning) for warning in warnings)
            + "</small>"
        )

    return (
        "<b>Analiza tarifnih brojeva - inteligentna historijska provjera</b><br>"
        f"Naimenovanja/stavki: <b>{len(assessments)}</b><br>"
        f"<span style='color:{status_color};'>{escape(summary)}</span>"
        f"{warning_html}<br><br>"
        "<table style='border-collapse:collapse;width:100%;'>"
        "<tr style='background:#f0f0f0;'>"
        "<th style='padding:3px 8px;text-align:left;'>Rb.</th>"
        "<th style='padding:3px 8px;text-align:left;'>Tarifni</th>"
        "<th style='padding:3px 8px;text-align:left;'>Status</th>"
        "<th style='padding:3px 8px;text-align:left;'>Dokaz</th>"
        "</tr>"
        + "".join(rows)
        + "</table>"
    )


def _render_row(item: TariffAssessment) -> str:
    color = {
        "OK": "#27ae60",
        "PROVJERI": "#e67e22",
        "RIZIK": "#c0392b",
    }.get(item.status, "#555")
    candidate = item.best_candidate
    candidate_html = ""
    if candidate:
        relation = "isti" if _same_code(item.line.current_code, candidate.code) else f"predlog {candidate.code}"
        candidate_html = (
            f"<br><small>Najbolji kandidat: <b>{escape(relation)}</b>, "
            f"score {candidate.score}, {escape(candidate.source)}, "
            f"korisceno {candidate.usage_count}x"
            f"{' | ' + escape(candidate.description[:80]) if candidate.description else ''}</small>"
        )
    official = (
        f"<br><small style='color:#555;'>Tarifa: {escape(item.official_description[:100])}</small>"
        if item.official_description
        else ""
    )
    history = (
        f"<small>Mapping: {item.current_mapping_count}x | Dokumenti: {item.sqlite_count}x</small>"
    )
    description = escape((item.line.description or "")[:120])
    if len(item.line.description or "") > 120:
        description += "..."

    return (
        "<tr>"
        f"<td style='padding:3px 8px;'>{escape(item.line.ordinal)}</td>"
        f"<td style='padding:3px 8px;font-family:monospace;'>{escape(item.line.current_code[:8])}</td>"
        f"<td style='padding:3px 8px;color:{color};font-weight:bold;'>{escape(item.status)}</td>"
        f"<td style='padding:3px 8px;'>{escape(item.reason)}"
        f"<br><small style='color:#777;'>[{description}]</small>"
        f"<br>{history}{candidate_html}{official}</td>"
        "</tr>"
    )
