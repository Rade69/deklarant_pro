from types import SimpleNamespace

from services.agent.learning.product_similarity_embedding_service import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_GEMINI_EMBEDDING_MODEL,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingConfig,
    ProductSimilarityEmbeddingService,
    build_simple_prefix_tsquery,
    extract_required_similarity_tokens,
    vector_to_sql_literal,
)


class FakeEmbeddings:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.3, 0.4]),
                SimpleNamespace(index=0, embedding=[0.1, 0.2]),
            ]
        )


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddings()


class FakeGeminiModels:
    def __init__(self):
        self.kwargs = None

    def embed_content(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[0.5, 0.6]),
                SimpleNamespace(values=[0.7, 0.8]),
            ]
        )


class FakeGeminiClient:
    def __init__(self):
        self.models = FakeGeminiModels()


class FakeLocalModel:
    def __init__(self):
        self.kwargs = None

    def encode(self, texts, **kwargs):
        self.kwargs = kwargs
        return [[0.1, 0.2], [0.3, 0.4]]


def test_vector_to_sql_literal_formats_pgvector_input():
    assert vector_to_sql_literal([0.1, -0.25, 1.0]) == "[0.1,-0.25,1]"


def test_build_simple_prefix_tsquery_uses_unique_search_tokens():
    assert build_simple_prefix_tsquery("DIXI dekstroza bomb bomb") == "dixi:* | dekstroza:* | bomb:*"


def test_extract_required_similarity_tokens_keeps_specific_terms():
    assert extract_required_similarity_tokens("DIXI bomboni slični proizvodi") == ["dixi"]
    assert extract_required_similarity_tokens("DIXI bonbonama") == ["dixi"]


def test_required_tokens_filter_out_generic_matches():
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(provider="local", api_key=""),
        client=FakeLocalModel(),
    )
    match = SimpleNamespace(
        product_name="BOMBONI PUNJENI ILI NEPUNJENI",
        text_for_embedding="BOMBONI PUNJENI ILI NEPUNJENI",
    )

    assert not service._passes_required_tokens(match, ["dixi"])


def test_create_local_embeddings_pads_to_pgvector_dimensions():
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(
            provider="local",
            api_key="",
            model=DEFAULT_LOCAL_EMBEDDING_MODEL,
            dimensions=5,
        ),
        client=FakeLocalModel(),
    )

    vectors = service._create_embeddings(["prvi", "drugi"])

    assert vectors == [[0.1, 0.2, 0.0, 0.0, 0.0], [0.3, 0.4, 0.0, 0.0, 0.0]]
    assert service.client.kwargs["normalize_embeddings"] is True


def test_create_openai_embeddings_orders_response_by_index_and_sets_dimensions():
    client = FakeClient()
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(
            provider="openai",
            api_key="test",
            model=DEFAULT_EMBEDDING_MODEL,
            dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
            allow_external_data=True,
        ),
        client=client,
    )

    vectors = service._create_embeddings(["prvi", "drugi"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert client.embeddings.kwargs["model"] == DEFAULT_EMBEDDING_MODEL
    assert client.embeddings.kwargs["input"] == ["prvi", "drugi"]
    assert client.embeddings.kwargs["dimensions"] == DEFAULT_EMBEDDING_DIMENSIONS


def test_create_gemini_embeddings_uses_existing_gemini_provider():
    client = FakeGeminiClient()
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(
            provider="gemini",
            api_key="test",
            model=DEFAULT_GEMINI_EMBEDDING_MODEL,
            dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
            allow_external_data=True,
        ),
        client=client,
    )

    vectors = service._create_embeddings(["prvi", "drugi"])

    assert vectors == [[0.5, 0.6], [0.7, 0.8]]
    assert client.models.kwargs["model"] == DEFAULT_GEMINI_EMBEDDING_MODEL
    assert client.models.kwargs["contents"] == ["prvi", "drugi"]


def test_embed_pending_stops_without_api_key():
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(provider="gemini", api_key="", allow_external_data=True),
        client=None,
    )

    result = service.embed_pending()

    assert result.error == "GEMINI_API_KEY nije podešen."


def test_embed_pending_respects_sensitive_data_guard():
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(provider="gemini", api_key="test", allow_external_data=False),
        client=FakeGeminiClient(),
    )

    result = service.embed_pending()

    assert result.error == "SEND_SENSITIVE_DATA=false — embedding bi slao nazive robe eksternom provideru."


def test_local_embed_pending_does_not_require_sensitive_data_flag(monkeypatch):
    service = ProductSimilarityEmbeddingService(
        config=EmbeddingConfig(
            provider="local",
            api_key="",
            dimensions=5,
            allow_external_data=False,
        ),
        client=FakeLocalModel(),
    )
    monkeypatch.setattr(service, "_load_pending_rows", lambda limit: [])

    result = service.embed_pending()

    assert result.error == ""
