"""
RAGAS로 완료된 문의(inquiries)의 AI 답변 품질을 평가하는 스크립트.

기존 앱의 클라이언트 코드를 그대로 재사용한다:
- app.clients.supabase  -> inquiries 테이블 REST 조회
- app.clients.llm       -> LiteLLM 프록시 (평가용 LLM으로 재사용)
- app.clients.http      -> env(), read_json() 등 공통 유틸

전제
- final_answer가 존재하는(=사람이 승인/수정 완료한) 문의만 평가 대상으로 삼는다.
- final_answer를 정답(reference)으로, ai_answer를 평가 대상(response)으로 사용한다.
  -> "AI가 처음 낸 답이 사람이 최종 승인한 답과 얼마나 가까운가"를 측정하는 구조.
- retrieved_docs(jsonb, documents 테이블 검색 결과)를 RAGAS의 retrieved_contexts로 사용한다.

이 파일은 app 패키지 루트에서 실행하는 것을 가정한다 (예: project_root/scripts/evaluate_ragas.py).
필요하면 import 경로(app.clients.*)를 실제 패키지 구조에 맞게 조정하세요.

설치 필요 패키지
    pip install ragas langchain-openai pandas --break-system-packages

필요 환경변수 (기존 앱과 동일)
    SUPABASE_URL, SUPABASE_KEY
    LITELLM_BASE_URL, LITELLM_MASTER_KEY, LITELLM_CHAT_MODEL   (평가용 LLM)
    UPSTAGE_BASE_URL, UPSTAGE_API_KEY, UPSTAGE_EMBEDDING_QUERY_MODEL  (평가용 임베딩)

사용 예시
    python evaluate_ragas.py --sample-per-category 30
    python evaluate_ragas.py --limit 100
    python evaluate_ragas.py --category 긴급 --output urgent_result.csv
"""

import argparse
import json
import logging
import sys
import types
import urllib.request
from pathlib import Path
from typing import Any, Optional


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    print(
        "경고: python-dotenv가 설치되어 있지 않아 .env를 자동으로 로드하지 못했습니다. "
        "`uv add python-dotenv` 실행 후 다시 시도하거나, 환경변수를 직접 export 하세요.",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# ragas 내부에서 (실제로 쓰지도 않는) langchain_community.chat_models.vertexai를
# import하는데, 최신 langchain-community에서는 그 경로가 삭제되어
# ModuleNotFoundError가 발생한다 (ragas의 알려진 버그).
# 우리는 Vertex AI를 전혀 쓰지 않으므로, 아래처럼 더미 모듈을 미리 등록해서
# ragas의 import 시도를 통과시킨다. langchain-community 버전을 낮출 필요가 없다.
# ---------------------------------------------------------------------------
try:
    import langchain_community.chat_models.vertexai  # noqa: F401
except ModuleNotFoundError:
    _vertexai_stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # 실제로 호출되지 않는 더미 클래스
        def __init__(self, *args, **kwargs):
            raise NotImplementedError(
                "ChatVertexAI는 더미 스텁입니다. 이 프로젝트는 Vertex AI를 사용하지 않습니다."
            )

    _vertexai_stub.ChatVertexAI = ChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _vertexai_stub

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_correctness,
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from app.clients.http import env, read_json
from app.clients.llm import litellm_base_url
from app.clients.supabase import inquiries_table, supabase_headers, supabase_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Supabase REST로 완료된 문의 가져오기
# ---------------------------------------------------------------------------
def fetch_completed_inquiries(
    limit: Optional[int] = None,
    category: Optional[str] = None,
    status: Optional[str] = "답변 완료",
) -> list[dict[str, Any]]:
    """
    final_answer가 있는(완료된) 문의를 Supabase REST로 가져온다.

    - limit: 최신순 N건만
    - category: 특정 카테고리만
    - status: 완료 상태값. update_final_answer()의 기본값인 "답변 완료"를 기본으로 쓴다.
              None을 주면 상태값 상관없이 final_answer 존재 여부만으로 필터링한다.
    """
    query: dict[str, str] = {
        "select": "*",
        "final_answer": "not.is.null",
        "order": "created_at.desc",
    }
    if status:
        query["status"] = f"eq.{status}"
    if category:
        query["categories"] = f"eq.{category}"
    if limit:
        query["limit"] = str(limit)

    request = urllib.request.Request(
        supabase_url(inquiries_table(), query),
        headers=supabase_headers(),
        method="GET",
    )
    rows = read_json(request) or []
    logger.info("완료된 문의 조회: %d건", len(rows))
    return rows


def sample_per_category(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """
    카테고리별로 최신 n건씩 층화 샘플링한다.
    rows는 fetch_completed_inquiries()가 이미 created_at desc로 정렬해 반환한 상태를 가정.
    """
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get("categories"), []).append(row)

    sampled: list[dict[str, Any]] = []
    for _, items in grouped.items():
        sampled.extend(items[:n])
    return sampled


# ---------------------------------------------------------------------------
# 2. retrieved_docs -> RAGAS context 리스트로 변환
# ---------------------------------------------------------------------------
def parse_contexts(retrieved_docs: Any) -> list[str]:
    """
    retrieved_docs는 documents 테이블 검색 결과(content, metadata 등을 담은 dict의 리스트)로 저장된
    것으로 보인다. 실제 구조가 다르면 이 함수만 맞춰 수정하면 된다.
    """
    if retrieved_docs is None:
        return []
    if isinstance(retrieved_docs, str):
        try:
            retrieved_docs = json.loads(retrieved_docs)
        except json.JSONDecodeError:
            return [retrieved_docs]

    contexts: list[str] = []
    if isinstance(retrieved_docs, list):
        for item in retrieved_docs:
            if isinstance(item, dict):
                text = item.get("content") or item.get("text") or item.get("page_content")
                contexts.append(text if text else json.dumps(item, ensure_ascii=False))
            elif isinstance(item, str):
                contexts.append(item)
    elif isinstance(retrieved_docs, dict):
        text = retrieved_docs.get("content") or retrieved_docs.get("text")
        contexts.append(text if text else json.dumps(retrieved_docs, ensure_ascii=False))
    return contexts


# ---------------------------------------------------------------------------
# 3. RAGAS 데이터셋 구성
# ---------------------------------------------------------------------------
def build_ragas_dataset(
    rows: list[dict[str, Any]],
) -> tuple[EvaluationDataset, list[dict[str, Any]]]:
    """
    ai_answer -> response, final_answer -> reference로 매핑.
    context가 없거나 ai_answer/final_answer가 비어있는 건은 평가에서 제외하고,
    실제로 채택된 원본 행들을 함께 반환해서 이후 결과와 매칭할 수 있게 한다.
    """
    samples = []
    kept_rows = []

    for row in rows:
        contexts = parse_contexts(row.get("retrieved_docs"))
        ai_answer = row.get("ai_answer")
        final_answer = row.get("final_answer")
        if not contexts or not ai_answer or not final_answer:
            continue

        samples.append(
            SingleTurnSample(
                user_input=row.get("question") or "",
                response=ai_answer,
                retrieved_contexts=contexts,
                reference=final_answer,
            )
        )
        kept_rows.append(row)

    return EvaluationDataset(samples=samples), kept_rows


# ---------------------------------------------------------------------------
# 4. 평가용 LLM / 임베딩 (기존 인프라 재사용)
# ---------------------------------------------------------------------------
def build_ragas_llm() -> LangchainLLMWrapper:
    """LiteLLM 프록시를 RAGAS 평가용 LLM으로 재사용한다."""
    llm = ChatOpenAI(
        model=env("LITELLM_CHAT_MODEL"),
        base_url=litellm_base_url(),
        api_key=env("LITELLM_MASTER_KEY"),
        temperature=0,
    )
    return LangchainLLMWrapper(llm)


def build_ragas_embeddings() -> LangchainEmbeddingsWrapper:
    """
    Upstage 임베딩 API는 OpenAI 호환 스펙(response["data"][0]["embedding"])이라
    OpenAIEmbeddings에 base_url/api_key만 Upstage 것으로 바꿔서 그대로 사용한다.
    """
    embeddings = OpenAIEmbeddings(
        model=env("UPSTAGE_EMBEDDING_QUERY_MODEL"),
        base_url=env("UPSTAGE_BASE_URL").rstrip("/"),
        api_key=env("UPSTAGE_API_KEY"),
    )
    return LangchainEmbeddingsWrapper(embeddings)


def run_evaluation(dataset: EvaluationDataset):
    metrics = [
        faithfulness,        # 답변이 검색된 문서에 근거하는지 (환각 여부)
        answer_relevancy,    # 답변이 질문과 얼마나 관련 있는지
        context_precision,   # 검색된 문서 중 실제 정답 생성에 유용했던 비율
        context_recall,      # 정답 생성에 필요한 정보를 검색이 충분히 커버했는지
        answer_correctness,  # ai_answer가 final_answer와 얼마나 일치하는지 (핵심 지표)
    ]
    return evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=build_ragas_llm(),
        embeddings=build_ragas_embeddings(),
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="완료된 문의에 대해 RAGAS 평가 실행")
    parser.add_argument("--limit", type=int, default=None, help="최신순 N건만 평가")
    parser.add_argument("--category", type=str, default=None, help="특정 카테고리만 평가")
    parser.add_argument(
        "--sample-per-category",
        type=int,
        default=None,
        help="카테고리별 층화 샘플링 건수 (예: 30 -> 카테고리마다 최신 30건)",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="답변 완료",
        help="완료 상태값 (기본: '답변 완료'). 상태 무관하게 보려면 빈 문자열('') 지정",
    )
    parser.add_argument("--output", type=str, default="ragas_result.csv")
    args = parser.parse_args()

    rows = fetch_completed_inquiries(
        limit=args.limit,
        category=args.category,
        status=args.status or None,
    )
    if args.sample_per_category:
        rows = sample_per_category(rows, args.sample_per_category)

    print(f"평가 대상 문의 수: {len(rows)}건")

    dataset, kept_rows = build_ragas_dataset(rows)
    print(f"context 존재하여 실제 평가 가능한 건수: {len(dataset)}건")

    if len(dataset) == 0:
        print("평가할 데이터가 없습니다. retrieved_docs 형식을 확인해주세요.")
        return

    result = run_evaluation(dataset)
    result_df = result.to_pandas()

    result_df["inquiry_id"] = [r.get("inquiry_id") for r in kept_rows]
    result_df["categories"] = [r.get("categories") for r in kept_rows]
    result_df["created_at"] = [r.get("created_at") for r in kept_rows]
    result_df["reviewer_type"] = [r.get("reviewer_type") for r in kept_rows]

    result_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: {args.output}")

    metric_cols = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    ]
    print("\n=== 전체 평균 ===")
    print(result_df[metric_cols].mean())
    print("\n=== 카테고리별 평균 ===")
    print(result_df.groupby("categories")[metric_cols].mean())


if __name__ == "__main__":
    main()