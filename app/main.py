from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

import uuid

# 로컬 실행 시 .env를 로드한다 (Supabase/LLM 자격증명 등).
load_dotenv()

from app.clients.supabase import get_inquiry, list_inquiries, update_final_answer
from app.graph.graph import graph
from app.graph.state import create_initial_state

app = FastAPI(title="AI CS Helper", version="0.1.0")

# 데모용 CORS: 정적 프론트엔드(file:// 또는 localhost)에서의 호출을 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InquiryRequest(BaseModel):
    text: str


class AnswerUpdate(BaseModel):
    final_answer: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/inquiries")
def get_inquiries() -> list[dict]:
    """전체 문의 목록(최신순)을 반환한다."""
    return list_inquiries()


@app.get("/inquiries/{inquiry_id}")
def read_inquiry(inquiry_id: str) -> dict:
    """단일 문의 상세를 반환한다."""
    inquiry = get_inquiry(inquiry_id)
    if inquiry is None:
        raise HTTPException(status_code=404, detail="inquiry not found")
    return inquiry


@app.patch("/inquiries/{inquiry_id}")
def save_final_answer(inquiry_id: str, payload: AnswerUpdate) -> dict:
    """관리자가 검토,작성한 최종 답변을 저장한다."""
    updated = update_final_answer(inquiry_id, payload.final_answer)
    if updated is None:
        raise HTTPException(status_code=404, detail="inquiry not found")
    return updated


@app.post("/inquiries")
def create_inquiry(payload: InquiryRequest) -> dict[str, str]:
    """유저 문의를 받아 그래프를 실행한다. inquiry_id는 DB가 알아서 생성한다."""
    initial_state = create_initial_state(
        session_id=str(uuid.uuid4()),
        inquiry_id=None,
        messages=[HumanMessage(content=payload.text)],
    )

    result = graph.invoke(initial_state)

    return {"inquiry_id": result["inquiry_id"], "session_id": result["session_id"]}
