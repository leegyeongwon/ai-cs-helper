import math

import pytest

import RAG_operations as rag


def test_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_VAR", raising=False)

    with pytest.raises(RuntimeError):
        rag.env("SOME_MISSING_VAR")


def test_env_returns_stripped_value(monkeypatch):
    monkeypatch.setenv("SOME_VAR", "  hello  ")

    assert rag.env("SOME_VAR") == "hello"


def test_vector_literal_formats_as_pg_vector():
    assert rag.vector_literal([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]"


def test_parse_embedding_accepts_list():
    assert rag.parse_embedding([1, 2, 3]) == [1.0, 2.0, 3.0]


def test_parse_embedding_accepts_json_string():
    assert rag.parse_embedding("[1, 2, 3]") == [1.0, 2.0, 3.0]


def test_cosine_similarity_identical_vectors_is_one():
    vector = [1.0, 2.0, 3.0]
    assert math.isclose(rag.cosine_similarity(vector, vector), 1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert rag.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_zero_vector_returns_zero():
    assert rag.cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_documents_table_default(monkeypatch):
    monkeypatch.delenv("SUPABASE_DOCUMENTS_TABLE", raising=False)

    assert rag.documents_table() == "documents"


def test_documents_table_override(monkeypatch):
    monkeypatch.setenv("SUPABASE_DOCUMENTS_TABLE", "custom_docs")

    assert rag.documents_table() == "custom_docs"


def test_supabase_headers_includes_auth(monkeypatch):
    monkeypatch.setenv("SUPABASE_KEY", "secret-key")

    headers = rag.supabase_headers()

    assert headers["apikey"] == "secret-key"
    assert headers["Authorization"] == "Bearer secret-key"


def test_supabase_url_builds_query_string(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")

    url = rag.supabase_url("documents", {"select": "id,content"})

    assert url == "https://example.supabase.co/rest/v1/documents?select=id%2Ccontent"


def test_embed_calls_post_json_with_expected_payload(monkeypatch):
    monkeypatch.setenv("UPSTAGE_BASE_URL", "https://upstage.example")
    monkeypatch.setenv("UPSTAGE_API_KEY", "api-key")
    monkeypatch.setenv("UPSTAGE_EMBEDDING_QUERY_MODEL", "query-model")

    captured = {}

    def fake_post_json(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(rag, "post_json", fake_post_json)

    result = rag.embed("환불 정책이 궁금해요", "query")

    assert result == [0.1, 0.2, 0.3]
    assert captured["url"] == "https://upstage.example/embeddings"
    assert captured["payload"] == {"model": "query-model", "input": "환불 정책이 궁금해요"}
    assert captured["headers"]["Authorization"] == "Bearer api-key"
