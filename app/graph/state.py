from typing import TypedDict, Literal, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InquiryState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

    # Router 노드에서 결정된 의도
    intent: Literal["to_human", "AI_generate"] | None

    # 두번째 Router 노드에서 결정된 ai답변의 타당성
    answer_review: Literal["pass", "fail"] | None

    retry_count: int  # 초기값 0

    # RAG 노드에서 검색된 문서 (content + metadata 포함)
    retrieved_docs: list[dict]

    # AI가 분류한 카테고리
    categories: str | None

    # AI가 생성한 답변
    ai_answer: str | None

    # 인간이 승인/수정한 최종 답변
    final_answer: str | None

    # 처리 상태
    status: Literal["문의 접수", "답변 생성", "답변 완료"]

    # 처리자 (AI 또는 사람)
    reviewer_type: str | None

    # 세션
    session_id: str

    # 문의 식별자 (DB의 inquiry_id와 매칭)
    inquiry_id: str | None


def create_initial_state(
    session_id: str,
    inquiry_id: str | None = None,
    messages: list[BaseMessage] | None = None,
) -> InquiryState:
    """
    초기 상태를 생성합니다.

    Args:
        session_id: 세션 식별자
        inquiry_id: 문의 식별자 (선택)
        messages: 초기 메시지 목록 (선택)

    Returns:
        InquiryState: 초기화된 상태 딕셔너리
    """
    return InquiryState(
        messages=messages or [],
        intent=None,
        retrieved_docs=[],
        categories=None,
        ai_answer=None,
        final_answer=None,
        status="문의 접수",
        reviewer_type=None,
        answer_review=None,
        retry_count=0,
        session_id=session_id,
        inquiry_id=inquiry_id,
    )