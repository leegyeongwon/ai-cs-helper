from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.graph.graph import graph
from app.graph.state import create_initial_state

app = FastAPI(title="AI CS Helper", version="0.1.0")


class InquiryRequest(BaseModel):
    text: str
    session_id: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/inquiries")
def create_inquiry(payload: InquiryRequest) -> dict[str, str]:
    """유저 문의를 받아 그래프를 실행한다. inquiry_id는 DB가 알아서 생성한다."""
    initial_state = create_initial_state(
        session_id=payload.session_id,
        inquiry_id=None,
        messages=[HumanMessage(content=payload.text)],
    )

    result = graph.invoke(initial_state)

    return {"inquiry_id": result["inquiry_id"], "session_id": result["session_id"]}
