"""
임베딩 관련 함수.
"""

from app.clients.http import env, post_json


def embedding_config(kind: str) -> tuple[str, str, str]:
    """(base_url, api_key, model)을 반환한다."""
    model_env = (
        "UPSTAGE_EMBEDDING_QUERY_MODEL"
        if kind == "query"
        else "UPSTAGE_EMBEDDING_PASSAGE_MODEL"
    )
    return env("UPSTAGE_BASE_URL").rstrip("/"), env("UPSTAGE_API_KEY"), env(model_env)


def embed(text: str, kind: str) -> list[float]:
    """텍스트를 임베딩한다. kind는 'query' 또는 'passage'."""
    base_url, api_key, model = embedding_config(kind)
    response = post_json(
        f"{base_url}/embeddings",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        {"model": model, "input": text},
    )
    return response["data"][0]["embedding"]
