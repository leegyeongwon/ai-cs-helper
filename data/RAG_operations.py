"""
임베딩 검증용 데모

supabase에 문서를 저장하고, 검색어를 입력하면 유사도가 높은 문서를 찾아서 출력한다.
"""

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from dotenv import load_dotenv

from regulations import REGULATIONS


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def read_json(request: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def post_json(url: str, headers: dict[str, str], payload: Any) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return read_json(request)


def embedding_config(kind: str) -> tuple[str, str, str]:
    # 로컬 콘솔에서 Docker Compose 내부 주소(http://litellm:4000)는 안 잡히므로
    # 이 데모는 Upstage OpenAI-compatible endpoint를 직접 호출한다.
    model_env = (
        "UPSTAGE_EMBEDDING_QUERY_MODEL"
        if kind == "query"
        else "UPSTAGE_EMBEDDING_PASSAGE_MODEL"
    )
    return env("UPSTAGE_BASE_URL").rstrip("/"), env("UPSTAGE_API_KEY"), env(model_env)


def embed(text: str, kind: str) -> list[float]:
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


def supabase_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
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
    base_url = env("SUPABASE_URL").rstrip("/")
    query_string = urllib.parse.urlencode(query or {})
    suffix = f"?{query_string}" if query_string else ""
    return f"{base_url}/rest/v1/{path}{suffix}"


def documents_table() -> str:
    return os.getenv("SUPABASE_DOCUMENTS_TABLE", "documents").strip() or "documents"


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def parse_embedding(value: Any) -> list[float]:
    if isinstance(value, str):
        value = json.loads(value)
    return [float(item) for item in value]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def add_document() -> None:
    text = input("저장할 문장> ").strip()
    if not text:
        print("입력된 문장이 없습니다.")
        return

    row = {
        "content": text,
        "metadata": {"source": "console"},
        "embedding": vector_literal(embed(text, "passage")),
    }
    post_json(
        supabase_url(documents_table()),
        supabase_headers({"Prefer": "return=minimal"}),
        row,
    )
    print("저장 완료")


def fetch_documents() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        supabase_url(documents_table(), {"select": "id,content,metadata,embedding"}),
        headers=supabase_headers(),
        method="GET",
    )
    return read_json(request) or []


def search_documents() -> None:
    text = input("검색할 문장> ").strip()
    if not text:
        print("입력된 문장이 없습니다.")
        return

    query_embedding = embed(text, "query")
    docs = fetch_documents()
    scored = [
        (cosine_similarity(query_embedding, parse_embedding(doc["embedding"])), doc)
        for doc in docs
        if doc.get("embedding") is not None
    ]

    for rank, (score, doc) in enumerate(
        sorted(scored, key=lambda item: item[0], reverse=True)[:3],
        start=1,
    ):
        print(f"\n#{rank} score={score:.4f} id={doc['id']}")
        print(doc["content"])

    if not scored:
        print("검색할 문서가 없습니다.")


def build_regulation_rows() -> list[dict[str, Any]]:
    rows = []
    for regulation_id, text in REGULATIONS.items():
        text = text.strip()
        if not text:
            continue
        print(f"  - 제{regulation_id}조 임베딩 중...")
        rows.append(
            {
                "content": text,
                "metadata": {"source": "regulation", "regulation_id": regulation_id},
                "embedding": vector_literal(embed(text, "passage")),
            }
        )
    return rows


def delete_all_documents() -> None:
    # PostgREST는 필터 없는 DELETE를 막기 때문에, PK인 id가 null이 아니라는
    # 항상 true인 조건을 필터로 줘서 테이블 전체를 지운다.
    request = urllib.request.Request(
        supabase_url(documents_table(), {"id": "not.is.null"}),
        headers=supabase_headers({"Prefer": "return=minimal"}),
        method="DELETE",
    )
    read_json(request)


def add_regulations() -> None:
    print(f"총 {len(REGULATIONS)}개의 규정을 임베딩합니다.")
    rows = build_regulation_rows()

    print("기존에 저장된 문서를 전부 삭제합니다...")
    delete_all_documents()

    print("새로 임베딩한 규정 문서를 저장합니다...")
    post_json(
        supabase_url(documents_table()),
        supabase_headers({"Prefer": "return=minimal"}),
        rows,
    )
    print(f"저장 완료: {len(rows)}건")


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Console embedding demo")
    parser.add_argument(
        "command",
        nargs="?",
        default="regulations",
        choices=["add", "search", "regulations"],
        help="add / search / regulations (기본값: regulations)",
    )
    args = parser.parse_args()

    try:
        if args.command == "add":
            add_document()
        elif args.command == "search":
            search_documents()
        else:
            add_regulations()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())