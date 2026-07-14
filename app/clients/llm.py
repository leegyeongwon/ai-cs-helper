"""
LiteLLM 프록시를 통한 llm 호출 클라이언트.
"""

import logging
import os

from app.clients.http import env, post_json

logger = logging.getLogger(__name__)


def litellm_base_url() -> str:
    """LiteLLM 엔드포인트 base URL을 결정한다."""
    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1").strip()
    return base_url.rstrip("/")


def chat(messages: list[dict[str, str]], model: str | None = None) -> str:
    """messages 목록을 보내 assistant 응답 문자열을 받는다."""
    base_url = litellm_base_url()
    used_model = model or env("LITELLM_CHAT_MODEL")
    logger.info("LLM 요청: model=%s base_url=%s messages=%d", used_model, base_url, len(messages))
    response = post_json(
        f"{base_url}/chat/completions",
        {
            "Authorization": f"Bearer {env('LITELLM_MASTER_KEY')}",
            "Content-Type": "application/json",
        },
        {
            "model": used_model,
            "messages": messages,
        },
    )
    content = response["choices"][0]["message"]["content"]
    logger.info("LLM 응답 수신: %d자", len(content or ""))
    logger.debug("LLM 응답 원문(앞 500자): %s", (content or "")[:500])
    return content


def ask(prompt: str, model: str | None = None) -> str:
    """user 프롬프트를 보내 답변을 받는다."""
    return chat([{"role": "user", "content": prompt}], model=model)
