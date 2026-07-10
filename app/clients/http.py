"""
LLM(LiteLLM) 호출과 Supabase REST 호출이 공통으로 사용.
"""

import http.client
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def env(name: str) -> str:
    """필수 환경변수를 읽는다. 값이 없으면 RuntimeError."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def read_json(request: urllib.request.Request) -> Any:
    """요청을 보내고 JSON 응답을 파싱한다."""
    method = request.get_method()
    url = request.full_url
    logger.debug("HTTP %s %s", method, url)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            logger.debug("HTTP %s %s -> %s (%d bytes)", method, url, response.status, len(body))
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("HTTP %s %s -> %d: %s", method, url, exc.code, detail)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except (http.client.RemoteDisconnected, urllib.error.URLError) as exc:
        logger.error("HTTP %s %s -> 연결 실패: %s", method, url, exc)
        raise RuntimeError(f"Connection failed: {exc}") from exc


def post_json(url: str, headers: dict[str, str], payload: Any) -> Any:
    """POST 요청을 보내고 JSON 응답을 파싱한다."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return read_json(request)
