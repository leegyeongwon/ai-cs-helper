"""규정 문서를 임베딩해 Supabase documents 테이블에 적재한다.

app/rag/regulations.py의 REGULATIONS를 임베딩해서 저장한다.
실행: python -m app.rag.ingest
"""

import sys
import urllib.request
from typing import Any

from dotenv import load_dotenv

from app.clients.embedding import embed
from app.clients.http import post_json, read_json
from app.clients.supabase import (
    documents_table,
    supabase_headers,
    supabase_url,
    vector_literal,
)
from app.rag.regulations import REGULATIONS


def build_regulation_rows() -> list[dict[str, Any]]:
    """REGULATIONS를 임베딩해 저장용 row 목록으로 만든다."""
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
    """documents 테이블을 전부 비운다."""
    request = urllib.request.Request(
        supabase_url(documents_table(), {"id": "not.is.null"}),
        headers=supabase_headers({"Prefer": "return=minimal"}),
        method="DELETE",
    )
    read_json(request)


def add_regulations() -> None:
    """기존 문서를 지우고 규정 전체를 새로 임베딩해 적재한다."""
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
    try:
        add_regulations()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
