"""
LangGraph 조건부 엣지(conditional edge) 라우팅 함수 모음.
"""

from app.graph.nodes import MAX_RETRY
from app.graph.state import InquiryState


def route_after_router(state: InquiryState) -> str:
    """ROUTER: 답변 가능/불가능 판단 이후 분기.

    가능(AI_generate) -> 평가 노드로.
    불가능(to_human) -> 바로 DB 저장으로.
    """
    if state["intent"] == "AI_generate":
        return "review"
    return "save_to_db"


def route_after_review(state: InquiryState) -> str:
    """ROUTER: 평가 및 재시도 이후 분기.

    통과했거나 3번 연속 실패 -> DB 저장으로.
    실패(재시도 여력 있음) -> 다시 router 노드로 (답변 재생성).
    """
    if state["answer_review"] == "pass":
        return "save_to_db"
    if state["retry_count"] >= MAX_RETRY:
        return "save_to_db"
    return "router"