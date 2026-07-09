# insert_regulations.py
import os
import re
from dotenv import load_dotenv
from supabase import create_client, Client

from regulations import REGULATIONS

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clear_documents():
    """documents 테이블을 truncate로 완전히 초기화합니다."""
    supabase.rpc("truncate_documents", {}).execute()
    print("기존 데이터 초기화 완료 (truncate)\n")


def get_embedding(text: str) -> list[float]:
    """
    텍스트를 4096차원 벡터로 변환합니다.
    지금은 테스트용 0 벡터를 반환합니다.
    실제 임베딩 모델(OpenAI, Cohere, 로컬 모델 등)을 연결하면
    이 함수 내부만 교체하면 됩니다.
    """
    # TODO: 실제 임베딩 모델 API 호출로 교체
    return [0.0] * 4096


def extract_title(content: str) -> str:
    """
    '제1조 (환불 및 교환 기간) ...' 에서 괄호 안의 제목만 추출합니다.
    """
    match = re.search(r"\((.*?)\)", content)
    return match.group(1) if match else ""


def insert_regulations():
    inserted = []

    for article_no, content in REGULATIONS.items():
        title = extract_title(content)

        metadata = {
            "article_no": article_no,       # 조 번호 (1, 2, 3...)
            "title": title,                 # 조 제목
            "version": "1.0",
            "status": "active",
        }

        embedding = get_embedding(content)

        response = supabase.table("documents").insert({
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
        }).execute()

        inserted.append(response.data)
        print(f"[제{article_no}조] 삽입 완료 — {title}")

    print(f"\n총 {len(inserted)}개 규정 삽입 완료")


if __name__ == "__main__":
    clear_documents()
    insert_regulations()
