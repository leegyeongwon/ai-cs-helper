"""
LiteLLM 프록시를 통한 llm 호출 클라이언트.
"""

import os

from app.clients.http import env, post_json


def litellm_base_url() -> str:
    """LiteLLM 엔드포인트 base URL을 결정한다.

    로컬 콘솔에서는 Docker Compose 내부 주소(http://litellm:4000)가 잡히지
    않으므로, 로컬 override → 일반 base URL → 기본값 순으로 선택한다.
    """
    local_url = os.getenv("LITELLM_LOCAL_BASE_URL", "").strip()
    if local_url:
        return local_url.rstrip("/")

    base_url = os.getenv("LITELLM_BASE_URL", "").strip()
    if base_url and "://litellm:" not in base_url:
        return base_url.rstrip("/")

    return "http://localhost:4000/v1"


def chat(messages: list[dict[str, str]], model: str | None = None) -> str:
    """messages 목록을 보내 assistant 응답 문자열을 받는다."""
    response = post_json(
        f"{litellm_base_url()}/chat/completions",
        {
            "Authorization": f"Bearer {env('LITELLM_MASTER_KEY')}",
            "Content-Type": "application/json",
        },
        {
            "model": model or env("LITELLM_CHAT_MODEL"),
            "messages": messages,
        },
    )
    return response["choices"][0]["message"]["content"]


def ask(prompt: str, model: str | None = None) -> str:
    """user 프롬프트를 보내 답변을 받는다."""
    return chat([{"role": "user", "content": prompt}], model=model)
