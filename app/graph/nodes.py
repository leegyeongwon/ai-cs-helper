"""
LangGraph 노드 함수 모음.
"""

import json
import logging

from app.clients import llm
from app.clients.supabase import insert_inquiry, update_inquiry
from app.graph.state import InquiryState
from app.rag.search import search

logger = logging.getLogger(__name__)


MAX_RETRY = 3


def _last_user_text(state: InquiryState) -> str:
    """messages에서 가장 마지막 메시지의 텍스트를 꺼낸다."""
    if not state["messages"]:
        return ""
    return state["messages"][-1].content


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


def save_to_db_node(state: InquiryState) -> dict:
    """inquiry_id 유무로 최초 저장(INSERT)/이후 저장(UPDATE)을 분기한다."""
    if state["inquiry_id"] is None:
        new_id = insert_inquiry(state)
        logger.info("save_to_db: INSERT 완료 inquiry_id=%s", new_id)
        return {"inquiry_id": new_id}
    update_inquiry(state)
    logger.info(
        "save_to_db: UPDATE 완료 inquiry_id=%s status=%s", state["inquiry_id"], state["status"]
    )
    return {}


def rag_search_node(state: InquiryState) -> dict:
    """문의 원문으로 규정 문서를 검색해 retrieved_docs를 채운다."""
    query_text = _last_user_text(state)
    results = search(query_text, top_k=5)
    docs = [
        {"content": doc["content"], "metadata": doc.get("metadata", {}), "score": score}
        for score, doc in results
    ]
    logger.info("rag_search: 문의=%r 검색결과=%d건", query_text[:80], len(docs))
    return {"retrieved_docs": docs}


def router_node(state: InquiryState) -> dict:
    """
    ROUTER: 답변 가능/불가능 판단 + (가능 시) 답변 동시 생성.

    intent가 None이면 최초 호출(판단+생성).
    intent가 이미 있으면 재시도 호출(답변만 재생성, review_feedback 참고).
    """
    query_text = _last_user_text(state)
    docs_text = "\n".join(f"- {d['content']}" for d in state["retrieved_docs"])

    if state["intent"] is None:
        prompt = f"""당신은 고객 문의를 분류하고 답변을 생성하는 AI입니다.

[문의 내용]
{query_text}

[관련 규정]
{docs_text}

아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요. 
{{
  "intent": "AI_generate 또는 to_human 중 하나. 관련 규정에 기반하여 답변 가능하면 AI_generate, 불가능하면 to_human을 선택하세요. 최대한 AI가 답변할수 있도록 하세요. 정말 적절한 규정이 없어 답변자체가 불가능할때 to_human을 선택하세요.",
  "categories": "문의 카테고리 (예: 환불, 배송, 개인정보, 등)",
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

    mode = "최초" if state["intent"] is None else f"재시도(retry_count={state['retry_count']})"
    logger.info("router: %s 호출", mode)
    raw = llm.ask(prompt)
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

    return {
        "intent": intent,
        "categories": parsed.get("categories"),
        "ai_answer": ai_answer,
        "status": "답변 생성",
    }


def review_node(state: InquiryState) -> dict:
    """ROUTER: 평가 및 재시도. ai_answer의 타당성을 검증한다."""
    query_text = _last_user_text(state)

    prompt = f"""당신은 AI가 생성한 고객 문의 답변이 타당한지 검토하는 검수자입니다.

[문의 내용]
{query_text}

[AI가 생성한 답변]
{state["ai_answer"]}

아래 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요.
{{
  "answer_review": "pass 또는 fail 중 하나",
  "review_feedback": "fail인 경우 구체적인 반려 사유. pass면 null"
}}"""

    raw = llm.ask(prompt)
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

    return updates
