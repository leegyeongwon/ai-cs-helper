"""
LangGraph 노드 함수 모음.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable

from app.clients import llm
from app.clients.inquiry_logs import append_inquiry_log
from app.clients.supabase import insert_inquiry, update_inquiry
from app.graph.state import InquiryState
from app.privacy.masking import mask_personal_info_with_details
from app.rag.search import search

logger = logging.getLogger(__name__)


MAX_RETRY = 3


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def log_node_errors(stage: str) -> Callable:
    """노드 예외를 DB에 요약 기록하고 원래 예외를 다시 발생시킨다."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: InquiryState):
            try:
                return func(state)
            except Exception as exc:
                append_inquiry_log(
                    state.get("inquiry_id"),
                    stage=stage,
                    event="failed",
                    title=f"{stage} 단계 처리 실패",
                    message=str(exc),
                    data={"error_type": type(exc).__name__, "error": str(exc)},
                )
                raise

        return wrapper

    return decorator


def _last_user_text(state: InquiryState) -> str:
    """messages에서 가장 마지막 메시지의 텍스트를 꺼낸다."""
    if not state["messages"]:
        return ""
    return state["messages"][-1].content


def _query_text(state: InquiryState) -> str:
    """외부 서비스에는 마스킹된 문의만 반환한다."""
    return state["masked_text"] or ""


def _parse_llm_json(raw: str) -> dict:
    """LLM 응답에서 JSON만 파싱한다. ```json 코드블록이 섞여 있어도 처리."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # LLM이 JSON이 아닌 응답을 준 경우 — 답변 생성 실패의 주요 원인. 원문을 남긴다.
        logger.error("LLM JSON 파싱 실패. 원문: %r", raw)
        raise


@log_node_errors("database")
def save_to_db_node(state: InquiryState) -> dict:
    """inquiry_id 유무로 최초 저장(INSERT)/이후 저장(UPDATE)을 분기한다."""
    if state["inquiry_id"] is None:
        started = time.perf_counter()
        new_id = insert_inquiry(state)
        duration = _duration_ms(started)
        logger.info("save_to_db: INSERT 완료 inquiry_id=%s", new_id)
        original = _last_user_text(state)
        append_inquiry_log(
            new_id,
            stage="pipeline",
            event="started",
            title="문의 처리 파이프라인 시작",
            message="새로운 문의 처리를 시작합니다.",
            data={
                "inquiry_id": new_id,
                "session_id": state["session_id"],
                "started_at": datetime.fromtimestamp(
                    state["pipeline_started_at"], timezone.utc
                ).isoformat(),
            },
        )
        append_inquiry_log(
            new_id,
            stage="inquiry",
            event="received",
            title="고객 문의 접수",
            message="고객 문의 원문을 접수했습니다.",
            data={"question": original, "question_length": len(original)},
        )
        append_inquiry_log(
            new_id,
            stage="database",
            event="insert_succeeded",
            title="문의 DB 저장 완료",
            message="inquiries 테이블에 문의를 저장했습니다.",
            duration_ms=duration,
            data={
                "operation": "INSERT",
                "table": "inquiries",
                "saved_fields": ["question", "status"],
                "status": state["status"],
            },
        )
        return {"inquiry_id": new_id}
    started = time.perf_counter()
    update_inquiry(state)
    duration = _duration_ms(started)
    logger.info(
        "save_to_db: UPDATE 완료 inquiry_id=%s status=%s", state["inquiry_id"], state["status"]
    )
    append_inquiry_log(
        state["inquiry_id"],
        stage="database",
        event="update_succeeded",
        title="AI 처리 결과 저장 완료",
        message="AI 처리 결과를 inquiries 테이블에 반영했습니다.",
        duration_ms=duration,
        data={
            "operation": "UPDATE",
            "table": "inquiries",
            "saved_fields": [
                "retrieved_docs",
                "categories",
                "ai_answer",
                "reviewer_type",
                "status",
            ],
            "categories": state["categories"],
            "status": state["status"],
            "ai_answer_exists": bool(state["ai_answer"]),
        },
    )
    append_inquiry_log(
        state["inquiry_id"],
        stage="pipeline",
        event="completed",
        title="AI 문의 처리 완료",
        message="상담원 검토 대기 상태로 전환되었습니다.",
        duration_ms=int((time.time() - state["pipeline_started_at"]) * 1000),
        data={
            "category": state["categories"],
            "intent": state["intent"],
            "review": state["answer_review"],
            "retry_count": state["retry_count"],
            "status": state["status"],
            "waiting_for_human": True,
        },
    )
    return {}


@log_node_errors("masking")
def mask_personal_info_node(state: InquiryState) -> dict[str, str]:
    """원문은 유지하고 외부 서비스용 문의에서 개인정보를 마스킹한다."""
    original = _last_user_text(state)
    started = time.perf_counter()
    result = mask_personal_info_with_details(original)
    masked = result["masked_text"]
    logger.info("personal_info_mask: 마스킹 적용=%s", original != masked)
    total_count = sum(result["counts"].values())
    append_inquiry_log(
        state["inquiry_id"],
        stage="masking",
        event="completed",
        title="개인정보 마스킹 완료",
        message=f"개인정보 {total_count}건을 마스킹했습니다.",
        duration_ms=_duration_ms(started),
        data={
            "original": original,
            "masked": masked,
            "total_count": total_count,
            "counts": result["counts"],
        },
    )
    return {"masked_text": masked}


@log_node_errors("rag")
def rag_search_node(state: InquiryState) -> dict:
    """문의 원문으로 규정 문서를 검색해 retrieved_docs를 채운다."""
    query_text = _query_text(state)
    started = time.perf_counter()
    results = search(query_text, top_k=5)
    docs = [
        {"content": doc["content"], "metadata": doc.get("metadata", {}), "score": score}
        for score, doc in results
    ]
    duration = _duration_ms(started)
    logger.info("rag_search: 문의=%r 검색결과=%d건", query_text[:80], len(docs))
    log_results = [
        {
            "rank": rank,
            "regulation_id": doc["metadata"].get("regulation_id"),
            "score": doc["score"],
            "content": doc["content"],
        }
        for rank, doc in enumerate(docs, start=1)
    ]
    append_inquiry_log(
        state["inquiry_id"],
        stage="rag",
        event="search_completed",
        title="관련 규정 검색 완료",
        message=f"관련 규정 {len(docs)}건을 검색했습니다.",
        duration_ms=duration,
        data={
            "query": query_text,
            "embedding_model": os.getenv("UPSTAGE_EMBEDDING_QUERY_MODEL", "embedding-query"),
            "top_k": 5,
            "results": log_results,
        },
    )
    return {"retrieved_docs": docs}


@log_node_errors("router")
def router_node(state: InquiryState) -> dict:
    """
    ROUTER: 답변 가능/불가능 판단 + (가능 시) 답변 동시 생성.

    intent가 None이면 최초 호출(판단+생성).
    intent가 이미 있으면 재시도 호출(답변만 재생성, review_feedback 참고).
    """
    query_text = _query_text(state)
    docs_text = "\n".join(f"- {d['content']}" for d in state["retrieved_docs"])

    if state["intent"] is None:
        prompt = f"""당신은 고객 문의를 분류하고 답변을 생성하는 AI입니다.

[문의 내용]
{query_text}

[관련 규정]
{docs_text}

대한항공과 무관한 경우 '대한항공과 관련이 없습니다'라는 명확한 안내만 제공해야 합니다.

아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요. 
{{
  "intent": "AI_generate 또는 to_human 중 하나. 관련 규정에 기반하여 답변 가능하면 AI_generate, 불가능하면 to_human을 선택하세요. AI가 답변할수 있도록 하되, 정말 적절한 규정이 없어 답변자체가 불가능할때 to_human을 선택하세요.",
  "categories": "고객 문의를 읽고 아래 카테고리 중 정확히 하나만 선택하세요.

카테고리:
- 긴급
- 예약_변경_취소
- 환불_수수료
- 항공권_결제
- 좌석
- 수하물
- 탑승_공항
- 운항정보
- 마일리지
- 스카이패스_회원
- 할인_쿠폰
- 특별서비스
- 기타

분류 우선순위:
1. 먼저 문의가 긴급 상황인지 판단합니다.
2. 긴급 상황이면 문의 주제와 관계없이 반드시 "긴급"을 반환합니다.
3. 긴급하지 않으면 문의의 핵심 목적에 가장 가까운 일반 카테고리를 반환합니다.
4. 여러 주제가 포함된 경우 고객이 최종적으로 해결하려는 가장 중요한 문제를 기준으로 선택합니다.
5. 단순히 "급하다", "빨리 답해 달라"는 표현만으로 긴급으로 분류하지 않습니다.
6. 정보가 부족해도 가장 가능성이 높은 카테고리 하나를 선택합니다.

긴급으로 분류하는 경우:
- 응급환자, 부상, 호흡곤란 등 의료 상황
- 폭발물, 화재, 위협 등 안전·보안 상황
- 현재 공항에서 체크인이나 탑승이 불가능한 상황
- 탑승 또는 체크인 마감이 임박한 상황
- 촉박한 환승으로 연결편을 놓칠 가능성이 높은 상황
- 당일 결항이나 운항 변경으로 여행이 불가능한 상황
- 필수 특별서비스가 공항에서 준비되지 않은 상황 등",
  "ai_answer": "intent가 AI_generate일 때 생성한 답변. to_human이면 null"
}}"""
    else:
        prompt = f"""당신은 고객 문의에 대한 답변을 재작성하는 AI입니다.

[문의 내용]
{query_text}

[관련 규정]
{docs_text}

[이전 답변]
{state["ai_answer"]}

[이전 답변이 반려된 사유]
{state["review_feedback"]}

위 반려 사유를 반영해서 답변을 다시 작성하세요.
아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요.
{{
  "intent": "AI_generate",
  "categories": "{state["categories"]}",
  "ai_answer": "재작성한 답변"
}}"""

    is_retry = state["intent"] is not None
    previous_answer = state["ai_answer"]
    mode = "최초" if not is_retry else f"재시도(retry_count={state['retry_count']})"
    logger.info("router: %s 호출", mode)
    started = time.perf_counter()
    raw = llm.ask(prompt)
    duration = _duration_ms(started)
    logger.debug("router: LLM 원문=%r", raw)
    parsed = _parse_llm_json(raw)

    intent = parsed["intent"]
    ai_answer = parsed.get("ai_answer")
    logger.info(
        "router: intent=%s categories=%s ai_answer=%s",
        intent,
        parsed.get("categories"),
        "생성됨(%d자)" % len(ai_answer) if ai_answer else "없음(null)",
    )
    if intent == "AI_generate" and not ai_answer:
        logger.warning("router: intent=AI_generate 인데 ai_answer가 비어 있음 — 답변 미생성 위험")

    attempt = state["retry_count"] + 1
    event = "answer_regenerated" if is_retry else "analysis_and_answer_completed"
    title = "AI 답변 재생성" if is_retry else "AI 문의 분석 및 답변 생성"
    append_inquiry_log(
        state["inquiry_id"],
        stage="router",
        event=event,
        title=title,
        message=(
            "검수 반려 사유를 반영해 답변을 다시 생성했습니다."
            if is_retry
            else (
                "AI가 답변 가능한 문의로 판단했습니다."
                if intent == "AI_generate"
                else "상담원 답변이 필요한 문의로 판단했습니다."
            )
        ),
        attempt=attempt,
        duration_ms=duration,
        data={
            "model": os.getenv("LITELLM_CHAT_MODEL", "cs-chat"),
            "category": parsed.get("categories"),
            "intent": intent,
            "answer_available": bool(ai_answer),
            "answer": ai_answer,
            "previous_answer": previous_answer if is_retry else None,
            "feedback": state["review_feedback"] if is_retry else None,
            "next_node": "review" if intent == "AI_generate" else "final_save",
        },
    )

    return {
        "intent": intent,
        "categories": parsed.get("categories"),
        "ai_answer": ai_answer,
        "reviewer_type": None if ai_answer else "human",
        "status": "답변 생성",
    }


@log_node_errors("review")
def review_node(state: InquiryState) -> dict:
    """ROUTER: 평가 및 재시도. ai_answer의 타당성을 검증한다."""
    query_text = _query_text(state)
    docs_text = "\n".join(f"- {d['content']}" for d in state["retrieved_docs"])

    prompt = f"""당신은 AI가 생성한 고객 문의 답변이 타당한지 검토하는 검수자입니다.

[문의 내용]
{query_text}

[관련 규정]
{docs_text}

[AI가 생성한 답변]
{state["ai_answer"]}

[가드레일 기준]
1. faithfulness: 답변 내용이 제공된 RAG 문서에만 기반하는가?
2. relevance: 답변이 유저의 문의 원본에 대한 직접적인 답인가?
3. safety: 유해하거나 부적절한 표현이 없는가?
대한항공과 무관한 경우 '대한항공과 관련이 없습니다'라는 명확한 안내만 제공해야 합니다.\

무조건 아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요.
{{
  "answer_review": "pass 또는 fail 중 하나",
  "review_feedback": "fail인 경우 구체적인 반려 사유. pass면 null"
}}"""

    started = time.perf_counter()
    raw = llm.ask(prompt)
    duration = _duration_ms(started)
    logger.debug("review: LLM 원문=%r", raw)
    parsed = _parse_llm_json(raw)

    review_result = parsed["answer_review"]
    updates: dict = {
        "answer_review": review_result,
        "review_feedback": parsed.get("review_feedback"),
    }
    if review_result == "fail":
        updates["retry_count"] = state["retry_count"] + 1
        logger.info(
            "review: FAIL (retry_count %d -> %d, MAX=%d) 사유=%r",
            state["retry_count"],
            updates["retry_count"],
            MAX_RETRY,
            parsed.get("review_feedback"),
        )
    else:
        logger.info("review: PASS")

    resulting_retry_count = updates.get("retry_count", state["retry_count"])
    next_node = (
        "final_save" if review_result == "pass" or resulting_retry_count >= MAX_RETRY else "router"
    )
    append_inquiry_log(
        state["inquiry_id"],
        stage="review",
        event="review_passed" if review_result == "pass" else "review_failed",
        title="AI 답변 검수 통과" if review_result == "pass" else "AI 답변 검수 반려",
        message=(
            "생성된 답변이 문의와 관련 규정에 부합합니다."
            if review_result == "pass"
            else parsed.get("review_feedback")
        ),
        attempt=state["retry_count"] + 1,
        duration_ms=duration,
        data={
            "answer": state["ai_answer"],
            "review": review_result,
            "feedback": parsed.get("review_feedback"),
            "retry_count": resulting_retry_count,
            "max_retry": MAX_RETRY,
            "regulations": [doc["content"] for doc in state["retrieved_docs"]],
            "next_node": next_node,
        },
    )

    return updates
