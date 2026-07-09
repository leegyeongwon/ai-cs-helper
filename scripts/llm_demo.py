"""
LLM 응답 확인용 콘솔 데모

콘솔에서 프롬프트를 입력하면 LiteLLM 프록시를 통해 답변을 받아 출력한다.
"""

import json
import http.client
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def litellm_base_url() -> str:
    local_url = os.getenv("LITELLM_LOCAL_BASE_URL", "").strip()
    if local_url:
        return local_url.rstrip("/")

    base_url = os.getenv("LITELLM_BASE_URL", "").strip()
    if base_url and "://litellm:" not in base_url:
        return base_url.rstrip("/")

    return "http://localhost:4000/v1"


def post_json(url: str, headers: dict[str, str], payload: Any) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except (http.client.RemoteDisconnected, urllib.error.URLError) as exc:
        raise RuntimeError(f"LiteLLM connection failed: {exc}") from exc


def ask(prompt: str) -> str:
    response = post_json(
        f"{litellm_base_url()}/chat/completions",
        {
            "Authorization": f"Bearer {env('LITELLM_MASTER_KEY')}",
            "Content-Type": "application/json",
        },
        {
            "model": env("LITELLM_CHAT_MODEL"),
            "messages": [
                {"role": "user", "content": prompt},
            ],
        },
    )
    return response["choices"][0]["message"]["content"]


def main() -> int:
    load_dotenv()

    prompt = input("프롬프트> ").strip()
    if not prompt:
        print("입력된 프롬프트가 없습니다.")
        return 0

    try:
        print("\n답변:")
        print(ask(prompt))
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
