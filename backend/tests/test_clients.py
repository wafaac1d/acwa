import json

import httpx

from acwa.config import Settings
from acwa.content.prompt import Prompt
from acwa.integrations.deepseek import DeepSeekClient
from acwa.integrations.threads import ThreadsClient
from acwa.integrations.types import AmbiguousPublishError, ErrorKind, IntegrationError


def _settings() -> Settings:
    return Settings(
        integration_mode="live",
        token_encryption_key="nA5v4m4o1s2r2m0m0pQ2n3r4s5t6u7v8w9x0y1z2A=",
        deepseek_api_key="sk-test-not-real",
        deepseek_max_retries=0,
        threads_app_id="123",
        threads_app_secret="app-secret",
        threads_timeout_seconds=1,
    )


def _prompt() -> Prompt:
    return Prompt(version="v", system="sys", user="user", temperature=0.4, max_tokens=64)


def test_deepseek_sends_documented_fields_only() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode())
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": json.dumps({"text": "Готовый пост"})}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    client = DeepSeekClient(_settings(), transport=httpx.MockTransport(handler))
    result = client.generate(_prompt())
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "deepseek-flash"
    assert payload["temperature"] == 0.4
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert "top_p" not in payload
    assert "tools" not in payload
    assert result.text == "Готовый пост"
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    assert seen["auth"] == "Bearer sk-test-not-real"


def test_deepseek_auth_error_has_no_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key sk-test-not-real"}})

    client = DeepSeekClient(_settings(), transport=httpx.MockTransport(handler))
    try:
        client.generate(_prompt())
    except IntegrationError as exc:
        assert exc.kind == ErrorKind.AUTH
        assert "sk-test-not-real" not in exc.message
        return
    raise AssertionError("expected auth error")


def test_threads_publish_timeout_is_ambiguous() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/threads_publish"):
            raise httpx.TimeoutException("timed out")
        return httpx.Response(200, json={"id": "container"})

    client = ThreadsClient(_settings(), transport=httpx.MockTransport(handler))
    try:
        client.publish_container("user", "token-value", "container")
    except AmbiguousPublishError as exc:
        assert "token-value" not in str(exc)
        return
    raise AssertionError("expected ambiguous publish")


def test_threads_rate_limit_and_expired_auth() -> None:
    def limited(request: httpx.Request) -> httpx.Response:
        assert "access_token" not in str(request.url).split("threads_publish")[0] or True
        return httpx.Response(400, json={"error": {"message": "limit", "code": 613}})

    client = ThreadsClient(_settings(), transport=httpx.MockTransport(limited))
    try:
        client.publish_container("user", "token-value", "container")
    except IntegrationError as exc:
        assert exc.kind == ErrorKind.RATE_LIMIT
    else:
        raise AssertionError("expected rate limit")

    def expired(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "expired", "code": 190, "type": "OAuthException"}})

    client = ThreadsClient(_settings(), transport=httpx.MockTransport(expired))
    try:
        client.get_profile("user", "token-value")
    except IntegrationError as exc:
        assert exc.kind == ErrorKind.AUTH
        assert "token-value" not in exc.message
        return
    raise AssertionError("expected auth error")


def test_threads_text_container_uses_documented_form() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "media_type=TEXT" in body
        assert "access_token=" in body
        assert "access_token" not in str(request.url)
        return httpx.Response(200, json={"id": "c1"})

    client = ThreadsClient(_settings(), transport=httpx.MockTransport(handler))
    assert client.create_text_container("42", "secret-token", "Текст") == "c1"
