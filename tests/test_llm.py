from app.clients import llm


def test_litellm_base_url_prefers_local_override(monkeypatch):
    monkeypatch.setenv("LITELLM_LOCAL_BASE_URL", "http://localhost:9000/v1")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000/v1")

    assert llm.litellm_base_url() == "http://localhost:9000/v1"


def test_litellm_base_url_ignores_docker_internal_host(monkeypatch):
    monkeypatch.delenv("LITELLM_LOCAL_BASE_URL", raising=False)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000/v1")

    assert llm.litellm_base_url() == "http://localhost:4000/v1"


def test_litellm_base_url_uses_external_base_url(monkeypatch):
    monkeypatch.delenv("LITELLM_LOCAL_BASE_URL", raising=False)
    monkeypatch.setenv("LITELLM_BASE_URL", "https://litellm.example.com/v1")

    assert llm.litellm_base_url() == "https://litellm.example.com/v1"


def test_litellm_base_url_default_when_unset(monkeypatch):
    monkeypatch.delenv("LITELLM_LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)

    assert llm.litellm_base_url() == "http://localhost:4000/v1"


def test_ask_returns_message_content(monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "master-key")
    monkeypatch.setenv("LITELLM_CHAT_MODEL", "gpt-test")
    monkeypatch.delenv("LITELLM_LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)

    def fake_post_json(url, headers, payload):
        assert url == "http://localhost:4000/v1/chat/completions"
        assert payload["model"] == "gpt-test"
        assert payload["messages"] == [{"role": "user", "content": "안녕"}]
        return {"choices": [{"message": {"content": "안녕하세요!"}}]}

    monkeypatch.setattr(llm, "post_json", fake_post_json)

    assert llm.ask("안녕") == "안녕하세요!"
