from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from config.settings import PROJECT_ROOT
from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.product_similarity_embeddings")

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_LOCAL_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSIONS = 1536
GENERIC_PRODUCT_TOKENS = {
    "artikl", "artikla", "artikal", "bombon", "bombona", "bombone",
    "bomboni", "bonbon", "bonbona", "bonbone", "bonboni", "broj",
    "code", "dijelovi", "dio",
    "fakt", "faktura", "kom", "komad", "komada", "model", "naziv",
    "ostali", "ostalo", "proizvod", "proizvodi", "robe", "set",
    "sifra", "slični", "slicni", "tarif", "tip",
}
GENERIC_PRODUCT_PREFIXES = ("bombon", "bonbon")


@dataclass(slots=True)
class EmbeddingConfig:
    provider: str
    api_key: str
    model: str = DEFAULT_LOCAL_EMBEDDING_MODEL
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    base_url: str = ""
    allow_external_data: bool = False


@dataclass(slots=True)
class EmbeddingBatchResult:
    scanned: int = 0
    embedded: int = 0
    skipped: int = 0
    error: str = ""


@dataclass(slots=True)
class SimilarProductMatch:
    source_id: int
    supplier: str
    product_name: str
    origin_country: str
    preference_code: str
    tariff_code: str
    usage_count: int
    similarity: float
    text_for_embedding: str


def load_embedding_config() -> EmbeddingConfig:
    env = _read_env_file()
    provider = (
        env.get("PRODUCT_SIMILARITY_EMBEDDING_PROVIDER")
        or os.getenv("PRODUCT_SIMILARITY_EMBEDDING_PROVIDER")
        or ""
    ).strip().lower()
    openai_key = env.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    gemini_key = env.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    if not provider:
        provider = "local"
    api_key = openai_key if provider == "openai" else gemini_key if provider == "gemini" else ""
    default_model = {
        "openai": DEFAULT_EMBEDDING_MODEL,
        "gemini": DEFAULT_GEMINI_EMBEDDING_MODEL,
        "local": DEFAULT_LOCAL_EMBEDDING_MODEL,
    }.get(provider, DEFAULT_LOCAL_EMBEDDING_MODEL)
    model = (
        env.get("PRODUCT_SIMILARITY_EMBEDDING_MODEL")
        or os.getenv("PRODUCT_SIMILARITY_EMBEDDING_MODEL")
        or default_model
    )
    dimensions_raw = (
        env.get("PRODUCT_SIMILARITY_EMBEDDING_DIMENSIONS")
        or os.getenv("PRODUCT_SIMILARITY_EMBEDDING_DIMENSIONS")
        or str(DEFAULT_EMBEDDING_DIMENSIONS)
    )
    base_url = env.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
    allow_external_data = (
        env.get("SEND_SENSITIVE_DATA") or os.getenv("SEND_SENSITIVE_DATA") or ""
    ).strip().lower() in {"1", "true", "yes", "da"}
    return EmbeddingConfig(
        provider=provider,
        api_key=api_key.strip(),
        model=model.strip(),
        dimensions=int(dimensions_raw),
        base_url=base_url.strip(),
        allow_external_data=allow_external_data,
    )


def vector_to_sql_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.10g}" for value in vector) + "]"


def build_simple_prefix_tsquery(value: str) -> str:
    tokens = extract_similarity_tokens(value)
    return " | ".join(f"{token}:*" for token in tokens)


def extract_similarity_tokens(value: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[\w]+", str(value or "").lower(), flags=re.UNICODE):
        if len(token) < 3:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def extract_required_similarity_tokens(value: str) -> list[str]:
    tokens = extract_similarity_tokens(value)
    required = [
        token for token in tokens
        if not is_generic_similarity_token(token) and len(token) >= 4
    ]
    return required[:3]


def is_generic_similarity_token(token: str) -> bool:
    normalized = str(token or "").lower()
    return (
        normalized in GENERIC_PRODUCT_TOKENS
        or any(normalized.startswith(prefix) for prefix in GENERIC_PRODUCT_PREFIXES)
    )


class ProductSimilarityEmbeddingService:
    def __init__(self, config: EmbeddingConfig | None = None, client: Any | None = None):
        self.config = config or load_embedding_config()
        self.client = client

    def embed_pending(self, batch_size: int = 100, max_batches: int | None = None) -> EmbeddingBatchResult:
        result = EmbeddingBatchResult()
        if self._uses_external_provider() and not self.config.allow_external_data:
            result.error = "SEND_SENSITIVE_DATA=false — embedding bi slao nazive robe eksternom provideru."
            return result
        if self._uses_external_provider() and not self.config.api_key and self.client is None:
            result.error = self._missing_key_message()
            return result

        batches_done = 0
        while True:
            if max_batches is not None and batches_done >= max_batches:
                return result

            rows = self._load_pending_rows(batch_size)
            if not rows:
                return result

            result.scanned += len(rows)
            texts = [row["text_for_embedding"] for row in rows if row.get("text_for_embedding")]
            if not texts:
                result.skipped += len(rows)
                return result

            try:
                vectors = self._create_embeddings(texts)
                self._store_embeddings(rows, vectors)
                result.embedded += len(vectors)
                batches_done += 1
            except Exception as exc:
                logger.exception("Embedding batch nije uspio")
                result.error = str(exc) or exc.__class__.__name__
                return result

    def find_similar(
        self,
        query_text: str,
        supplier: str = "",
        origin_country: str = "",
        limit: int = 10,
        min_similarity: float = 0.0,
    ) -> list[SimilarProductMatch]:
        query = str(query_text or "").strip()
        if not query:
            return []

        required_tokens = extract_required_similarity_tokens(query)
        matches: dict[int, SimilarProductMatch] = {}
        for match in self._find_lexical_matches(query, supplier, origin_country, limit * 2):
            if self._passes_required_tokens(match, required_tokens):
                matches[match.source_id] = match

        can_use_vector = not self._uses_external_provider() or self.config.allow_external_data
        if can_use_vector:
            if self._uses_external_provider() and not self.config.api_key and self.client is None:
                raise RuntimeError(self._missing_key_message())
            for match in self._find_vector_matches(
                query, supplier, origin_country, limit * 2, min_similarity
            ):
                if not self._passes_required_tokens(match, required_tokens):
                    continue
                current = matches.get(match.source_id)
                if current is None or match.similarity > current.similarity:
                    matches[match.source_id] = match

        return sorted(
            matches.values(),
            key=lambda item: (item.similarity, item.usage_count),
            reverse=True,
        )[:limit]

    def _find_vector_matches(
        self,
        query: str,
        supplier: str,
        origin_country: str,
        limit: int,
        min_similarity: float,
    ) -> list[SimilarProductMatch]:
        query_vector = self._create_embeddings([query])[0]
        vector_literal = vector_to_sql_literal(query_vector)
        filters = ["embedding IS NOT NULL"]
        filter_params: list[Any] = []

        if supplier.strip():
            filters.append("supplier ILIKE %s")
            filter_params.append(f"%{supplier.strip()}%")
        if origin_country.strip():
            filters.append("origin_country = %s")
            filter_params.append(origin_country.strip())

        sql = f"""
            SELECT source_id, supplier, product_name, origin_country, preference_code,
                   tariff_code, usage_count, text_for_embedding,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM catalogs.product_similarity_memory
            WHERE {" AND ".join(filters)}
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector, usage_count DESC
            LIMIT %s
        """
        params = [
            vector_literal,
            *filter_params,
            vector_literal,
            min_similarity,
            vector_literal,
            limit,
        ]

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return [self._match_from_row(row) for row in cursor.fetchall()]

    def _find_lexical_matches(
        self,
        query: str,
        supplier: str,
        origin_country: str,
        limit: int,
    ) -> list[SimilarProductMatch]:
        tsquery = build_simple_prefix_tsquery(query)
        if not tsquery:
            return []
        filters = [
            "to_tsvector('simple', product_name) @@ to_tsquery('simple', %s)"
        ]
        params: list[Any] = [tsquery]
        if supplier.strip():
            filters.append("supplier ILIKE %s")
            params.append(f"%{supplier.strip()}%")
        if origin_country.strip():
            filters.append("origin_country = %s")
            params.append(origin_country.strip())
        params.append(limit)

        sql = f"""
            SELECT source_id, supplier, product_name, origin_country, preference_code,
                   tariff_code, usage_count, text_for_embedding,
                   0.0 AS similarity
            FROM catalogs.product_similarity_memory
            WHERE {" AND ".join(filters)}
            ORDER BY usage_count DESC
            LIMIT %s
        """
        query_tokens = extract_similarity_tokens(query)
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return [self._lexical_match_from_row(row, query_tokens) for row in cursor.fetchall()]

    def _load_pending_rows(self, limit: int) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, text_for_embedding
                    FROM catalogs.product_similarity_memory
                    WHERE embedding IS NULL
                      AND COALESCE(text_for_embedding, '') <> ''
                    ORDER BY usage_count DESC NULLS LAST, id
                    LIMIT %s
                    """,
                    (limit,),
                )
                return list(cursor.fetchall())

    def _create_embeddings(self, texts: list[str]) -> list[list[float]]:
        if self.config.provider == "local":
            return self._create_local_embeddings(texts)
        if self.config.provider == "gemini":
            return self._create_gemini_embeddings(texts)
        return self._create_openai_embeddings(texts)

    def _create_local_embeddings(self, texts: list[str]) -> list[list[float]]:
        model = self._client()
        vectors = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [self._fit_dimensions(list(vector)) for vector in vectors]

    def _create_openai_embeddings(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "input": texts,
        }
        if self.config.model.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.config.dimensions
        response = client.embeddings.create(**kwargs)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    def _create_gemini_embeddings(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        from google.genai import types

        response = client.models.embed_content(
            model=self.config.model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=self.config.dimensions),
        )
        return [list(item.values) for item in response.embeddings]

    def _store_embeddings(self, rows: list[dict[str, Any]], vectors: list[list[float]]) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for row, vector in zip(rows, vectors, strict=True):
                    cursor.execute(
                        """
                        UPDATE catalogs.product_similarity_memory
                        SET embedding = %s::vector,
                            embedding_model = %s,
                            embedding_created_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (
                            vector_to_sql_literal(vector),
                            self.config.model,
                            row["id"],
                        ),
                    )

    def _client(self):
        if self.client is not None:
            return self.client
        if self.config.provider == "local":
            from sentence_transformers import SentenceTransformer

            self.client = SentenceTransformer(
                self.config.model,
                local_files_only=True,
                trust_remote_code=False,
            )
            return self.client
        if self.config.provider == "gemini":
            from google import genai

            self.client = genai.Client(api_key=self.config.api_key)
            return self.client
        kwargs: dict[str, Any] = {"api_key": self.config.api_key}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        self.client = OpenAI(**kwargs)
        return self.client

    def _fit_dimensions(self, vector: list[float]) -> list[float]:
        if len(vector) == self.config.dimensions:
            return [float(value) for value in vector]
        if len(vector) > self.config.dimensions:
            return [float(value) for value in vector[: self.config.dimensions]]
        return [float(value) for value in vector] + [0.0] * (self.config.dimensions - len(vector))

    def _uses_external_provider(self) -> bool:
        return self.config.provider in {"openai", "gemini"}

    def _missing_key_message(self) -> str:
        if self.config.provider == "gemini":
            return "GEMINI_API_KEY nije podešen."
        return "OPENAI_API_KEY nije podešen."

    def _match_from_row(self, row: dict[str, Any]) -> SimilarProductMatch:
        return SimilarProductMatch(
            source_id=int(row["source_id"]),
            supplier=row.get("supplier") or "",
            product_name=row.get("product_name") or "",
            origin_country=row.get("origin_country") or "",
            preference_code=row.get("preference_code") or "",
            tariff_code=row.get("tariff_code") or "",
            usage_count=int(row.get("usage_count") or 0),
            similarity=float(row.get("similarity") or 0),
            text_for_embedding=row.get("text_for_embedding") or "",
        )

    def _lexical_match_from_row(
        self,
        row: dict[str, Any],
        query_tokens: list[str],
    ) -> SimilarProductMatch:
        match = self._match_from_row(row)
        product = str(match.product_name or "").lower()
        if query_tokens:
            overlap = sum(1 for token in query_tokens if token in product)
            ratio = overlap / len(query_tokens)
        else:
            ratio = 0.0
        usage_bonus = min(match.usage_count, 20) / 1000
        match.similarity = min(0.99, 0.50 + ratio * 0.45 + usage_bonus)
        return match

    def _passes_required_tokens(
        self,
        match: SimilarProductMatch,
        required_tokens: list[str],
    ) -> bool:
        if not required_tokens:
            return True
        haystack = f"{match.product_name} {match.text_for_embedding}".lower()
        return all(token in haystack for token in required_tokens)


def _read_env_file() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result
