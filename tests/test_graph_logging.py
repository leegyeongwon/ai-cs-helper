from langchain_core.messages import HumanMessage

from app.graph import nodes
from app.graph.state import create_initial_state


def test_review_node_receives_retrieved_regulations(monkeypatch):
    captured = {}
    state = create_initial_state("session", messages=[HumanMessage(content="환불 문의")])
    state.update(
        {
            "inquiry_id": "inq-1",
            "masked_text": "환불 문의",
            "ai_answer": "환불 규정에 따른 답변",
            "retrieved_docs": [
                {"content": "제10조 환불 규정", "metadata": {}, "score": 0.9},
                {"content": "제11조 수수료 규정", "metadata": {}, "score": 0.8},
            ],
        }
    )

    def fake_ask(prompt):
        captured["prompt"] = prompt
        return '{"answer_review":"pass","review_feedback":null}'

    monkeypatch.setattr(nodes.llm, "ask", fake_ask)
    monkeypatch.setattr(nodes, "append_inquiry_log", lambda *args, **kwargs: True)

    result = nodes.review_node(state)

    assert result["answer_review"] == "pass"
    assert "[관련 규정]" in captured["prompt"]
    assert "제10조 환불 규정" in captured["prompt"]
    assert "제11조 수수료 규정" in captured["prompt"]
