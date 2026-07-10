"""Supabase REST 접근 클라이언트.

documents 테이블에 임베딩 문서를 저장/조회.
"""

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from app.clients.http import env, read_json


def supabase_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Supabase REST 요청 헤더를 만든다."""
    key = env("SUPABASE_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def supabase_url(path: str, query: dict[str, str] | None = None) -> str:
    """Supabase REST URL을 만든다."""
    base_url = env("SUPABASE_URL").rstrip("/")
    query_string = urllib.parse.urlencode(query or {})
    suffix = f"?{query_string}" if query_string else ""
    return f"{base_url}/rest/v1/{path}{suffix}"


def documents_table() -> str:
    """문서 테이블 이름을 반환한다."""
    return os.getenv("SUPABASE_DOCUMENTS_TABLE", "documents").strip() or "documents"


def vector_literal(values: list[float]) -> str:
    """리스트를 리터럴 문자열로 변환한다."""
    return "[" + ",".join(str(value) for value in values) + "]"


def parse_embedding(value: Any) -> list[float]:
    """DB에서 읽은 embedding을 float 리스트로 변환한다."""
    if isinstance(value, str):
        value = json.loads(value)
    return [float(item) for item in value]


def fetch_documents() -> list[dict[str, Any]]:
    """documents 테이블의 전체 문서를 가져온다."""
    request = urllib.request.Request(
        supabase_url(documents_table(), {"select": "id,content,metadata,embedding"}),
        headers=supabase_headers(),
        method="GET",
    )
    return read_json(request) or []
