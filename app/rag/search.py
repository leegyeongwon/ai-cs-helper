"""
RAG 검색 로직.

질문 문자열을 임베딩한 뒤, Supabase에 저장된 문서와 코사인 유사도로 비교해 상위 문서를 반환한다.
"""

import math
from typing import Any

from app.clients.embedding import embed
from app.clients.supabase import fetch_documents, parse_embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터의 코사인 유사도 계산."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(query_text: str, top_k: int = 3) -> list[tuple[float, dict[str, Any]]]:
    """
    질의와 유사한 문서를 (score, doc) 리스트로 반환.

    점수 내림차순 정렬. 저장된 문서가 없으면 빈 리스트.
    """
    query_embedding = embed(query_text, "query")
    docs = fetch_documents()
    scored = [
        (cosine_similarity(query_embedding, parse_embedding(doc["embedding"])), doc)
        for doc in docs
        if doc.get("embedding") is not None
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]
