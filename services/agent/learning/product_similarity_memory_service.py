from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.product_similarity_memory")


@dataclass(slots=True)
class ProductSimilaritySource:
    source_table: str
    source_id: int
    supplier: str
    product_name: str
    origin_country: str
    preference_code: str
    tariff_code: str
    usage_count: int
    confidence: float | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class ProductSimilaritySyncResult:
    scanned: int = 0
    synced: int = 0
    skipped: int = 0
    table_ready: bool = False
    error: str = ""


def normalize_similarity_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text


def build_similarity_embedding_text(source: ProductSimilaritySource) -> str:
    parts = [
        ("Naziv robe", source.product_name),
        ("Dobavljac", source.supplier),
        ("Zemlja porijekla", source.origin_country),
        ("Povlastica", source.preference_code),
        ("Tarifni broj", source.tariff_code),
    ]
    return "\n".join(
        f"{label}: {normalize_similarity_text(value)}"
        for label, value in parts
        if normalize_similarity_text(value)
    )


def build_similarity_source_hash(source: ProductSimilaritySource) -> str:
    payload = "\x1f".join(
        [
            source.source_table,
            str(source.source_id),
            normalize_similarity_text(source.supplier).upper(),
            normalize_similarity_text(source.product_name).upper(),
            normalize_similarity_text(source.origin_country).upper(),
            normalize_similarity_text(source.preference_code).upper(),
            normalize_similarity_text(source.tariff_code),
            str(source.usage_count),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProductSimilarityMemoryService:
    source_table = "catalogs.product_tariff_mapping"

    def is_ready(self) -> bool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = 'catalogs'
                              AND table_name = 'product_similarity_memory'
                        ) AS table_exists
                        """
                    )
                    return bool(cursor.fetchone()["table_exists"])
        except Exception as exc:
            logger.debug("product_similarity_memory nije spremna: %s", exc)
            return False

    def sync_from_product_tariff_mapping(self, limit: int | None = None) -> ProductSimilaritySyncResult:
        result = ProductSimilaritySyncResult()
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if not self._target_table_exists(cursor):
                        result.error = "Tabela catalogs.product_similarity_memory ne postoji."
                        return result
                    result.table_ready = True

                    columns = self._columns(cursor, "catalogs", "product_tariff_mapping")
                    sources = self._load_sources(cursor, columns, limit)
                    result.scanned = len(sources)
                    for source in sources:
                        if not source.product_name or not source.tariff_code:
                            result.skipped += 1
                            continue
                        self._upsert_source(cursor, source)
                        result.synced += 1
            return result
        except Exception as exc:
            logger.exception("Sinhronizacija product_similarity_memory nije uspjela")
            result.error = str(exc)
            return result

    def _target_table_exists(self, cursor) -> bool:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'catalogs'
                  AND table_name = 'product_similarity_memory'
            ) AS table_exists
            """
        )
        return bool(cursor.fetchone()["table_exists"])

    def _columns(self, cursor, schema: str, table: str) -> set[str]:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema, table),
        )
        return {row["column_name"] for row in cursor.fetchall()}

    def _load_sources(self, cursor, columns: set[str], limit: int | None) -> list[ProductSimilaritySource]:
        select_parts = [
            "id",
            self._column_expr(columns, "supplier", "''", "supplier"),
            self._column_expr(columns, "source", "''", "source_name"),
            self._column_expr(columns, "product_code", "''", "product_code"),
            self._column_expr(columns, "naziv_robe", "''", "naziv_robe"),
            self._column_expr(columns, "commodity_code", self._column_fallback(columns, "tarifni_broj"), "commodity_code"),
            self._column_expr(columns, "precision_1", "''", "precision_1"),
            self._column_expr(columns, "zemlja_porijekla", "''", "zemlja_porijekla"),
            self._column_expr(columns, "povlastica", "''", "povlastica"),
            self._column_expr(columns, "usage_count", "0", "usage_count"),
            self._column_expr(columns, "confidence", "NULL", "confidence"),
            self._column_expr(columns, "last_used", "NULL", "last_used"),
        ]
        sql = f"""
            SELECT {", ".join(select_parts)}
            FROM catalogs.product_tariff_mapping
            WHERE COALESCE(naziv_robe, '') <> ''
            ORDER BY usage_count DESC NULLS LAST, id
        """
        params: tuple[Any, ...] = ()
        if limit and limit > 0:
            sql += " LIMIT %s"
            params = (limit,)
        cursor.execute(sql, params)
        return [self._source_from_row(row) for row in cursor.fetchall()]

    def _column_expr(self, columns: set[str], column: str, fallback: str, alias: str) -> str:
        if column in columns:
            return f"{column} AS {alias}"
        return f"{fallback} AS {alias}"

    def _column_fallback(self, columns: set[str], column: str) -> str:
        return column if column in columns else "''"

    def _source_from_row(self, row: dict[str, Any]) -> ProductSimilaritySource:
        tariff_code = normalize_similarity_text(row.get("commodity_code") or row.get("precision_1"))
        supplier = normalize_similarity_text(row.get("supplier") or row.get("source_name"))
        return ProductSimilaritySource(
            source_table=self.source_table,
            source_id=int(row["id"]),
            supplier=supplier,
            product_name=normalize_similarity_text(row.get("naziv_robe")),
            origin_country=normalize_similarity_text(row.get("zemlja_porijekla")),
            preference_code=normalize_similarity_text(row.get("povlastica")),
            tariff_code=tariff_code,
            usage_count=int(row.get("usage_count") or 0),
            confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
            metadata={
                "product_code": normalize_similarity_text(row.get("product_code")),
                "precision_1": normalize_similarity_text(row.get("precision_1")),
                "last_used": str(row.get("last_used") or ""),
            },
        )

    def _upsert_source(self, cursor, source: ProductSimilaritySource) -> None:
        text_for_embedding = build_similarity_embedding_text(source)
        source_hash = build_similarity_source_hash(source)
        cursor.execute(
            """
            INSERT INTO catalogs.product_similarity_memory (
                source_table, source_id, source_hash, supplier, product_name,
                origin_country, preference_code, tariff_code, usage_count,
                confidence, text_for_embedding, metadata, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (source_table, source_id) DO UPDATE SET
                source_hash = EXCLUDED.source_hash,
                supplier = EXCLUDED.supplier,
                product_name = EXCLUDED.product_name,
                origin_country = EXCLUDED.origin_country,
                preference_code = EXCLUDED.preference_code,
                tariff_code = EXCLUDED.tariff_code,
                usage_count = EXCLUDED.usage_count,
                confidence = EXCLUDED.confidence,
                text_for_embedding = EXCLUDED.text_for_embedding,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP,
                embedding = CASE
                    WHEN catalogs.product_similarity_memory.source_hash = EXCLUDED.source_hash
                    THEN catalogs.product_similarity_memory.embedding
                    ELSE NULL
                END,
                embedding_model = CASE
                    WHEN catalogs.product_similarity_memory.source_hash = EXCLUDED.source_hash
                    THEN catalogs.product_similarity_memory.embedding_model
                    ELSE NULL
                END,
                embedding_created_at = CASE
                    WHEN catalogs.product_similarity_memory.source_hash = EXCLUDED.source_hash
                    THEN catalogs.product_similarity_memory.embedding_created_at
                    ELSE NULL
                END
            """,
            (
                source.source_table,
                source.source_id,
                source_hash,
                source.supplier,
                source.product_name,
                source.origin_country,
                source.preference_code,
                source.tariff_code,
                source.usage_count,
                source.confidence,
                text_for_embedding,
                json.dumps(source.metadata, ensure_ascii=False),
            ),
        )


def sync_product_similarity_memory(limit: int | None = None) -> ProductSimilaritySyncResult:
    return ProductSimilarityMemoryService().sync_from_product_tariff_mapping(limit=limit)
