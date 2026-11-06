import json
import time
from typing import Protocol

import httpx

from acwa.config import Settings
from acwa.content.prompt import Prompt
from acwa.integrations.types import ErrorKind, GenerationResult, IntegrationError
from acwa.security.redact import redact


class ContentGenerator(Protocol):
    def generate(self, prompt: Prompt) -> GenerationResult: ...


class DeepSeekClient:
    """Official DeepSeek chat completions client.

    Sends only documented fields: model, messages, temperature, max_tokens,
    stream, thinking and response_format. top_p is omitted because the docs
    recommend not changing it together with temperature.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    def generate(self, prompt: Prompt) -> GenerationResult:
        if not self._settings.deepseek_api_key:
            raise IntegrationError(
                ErrorKind.PERMANENT,
                "Ключ DeepSeek не задан. Укажите ACWA_DEEPSEEK_API_KEY на сервере.",
            )
        payload = {
            "model": self._settings.deepseek_model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "temperature": prompt.temperature,
            "max_tokens": prompt.max_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
        response = self._post_with_retries(payload)
        body = _json_body(response)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise IntegrationError(
                ErrorKind.TRANSIENT,
                "DeepSeek вернул ответ без текста поста",
                http_status=response.status_code,
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise IntegrationError(
                ErrorKind.TRANSIENT,
                "DeepSeek вернул ответ без текста поста",
                http_status=response.status_code,
            )
        content = message.get("content")
        text = _extract_text(content if isinstance(content, str) else "")
        raw_usage = body.get("usage")
        safe_usage = _usage(raw_usage if isinstance(raw_usage, dict) else None)
        raw_model = body.get("model")
        model = raw_model if isinstance(raw_model, str) else self._settings.deepseek_model
        return GenerationResult(text=text, model=model, usage=safe_usage)

    def _post_with_retries(self, payload: dict[str, object]) -> httpx.Response:
        url = self._settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self._settings.deepseek_timeout_seconds, connect=10.0)
        attempts = self._settings.deepseek_max_retries + 1
        last_error: IntegrationError | None = None
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=timeout, transport=self._transport) as client:
                    response = client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                last_error = IntegrationError(
                    ErrorKind.TRANSIENT,
                    "DeepSeek не ответил вовремя",
                )
                if attempt + 1 >= attempts:
                    raise last_error from exc
                time.sleep(min(2**attempt, 4))
                continue
            except httpx.HTTPError as exc:
                last_error = IntegrationError(ErrorKind.TRANSIENT, "Сбой сети при обращении к DeepSeek")
                if attempt + 1 >= attempts:
                    raise last_error from exc
                time.sleep(min(2**attempt, 4))
                continue
            if response.status_code < 400:
                return response
            error = _map_status(response)
            last_error = error
            if error.kind not in {ErrorKind.TRANSIENT, ErrorKind.RATE_LIMIT} or attempt + 1 >= attempts:
                raise error
            delay = error.retry_after.total_seconds() if error.retry_after else min(2**attempt, 8)
            time.sleep(delay)
        raise last_error or IntegrationError(ErrorKind.TRANSIENT, "DeepSeek недоступен")


def _map_status(response: httpx.Response) -> IntegrationError:
    message = _error_message(response)
    if response.status_code == 401:
        return IntegrationError(ErrorKind.AUTH, "DeepSeek отклонил ключ API", http_status=401)
    if response.status_code == 402:
        return IntegrationError(
            ErrorKind.PERMANENT,
            "На счёте DeepSeek недостаточно средств",
            http_status=402,
        )
    if response.status_code == 429:
        return IntegrationError(
            ErrorKind.RATE_LIMIT,
            "DeepSeek ограничил частоту запросов",
            http_status=429,
        )
    if response.status_code >= 500:
        return IntegrationError(ErrorKind.TRANSIENT, message, http_status=response.status_code)
    return IntegrationError(ErrorKind.PERMANENT, message, http_status=response.status_code)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return "DeepSeek вернул ошибку"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return redact(error["message"])[:300]
    return "DeepSeek вернул ошибку"


def _json_body(response: httpx.Response) -> dict[str, object]:
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise IntegrationError(ErrorKind.TRANSIENT, "DeepSeek вернул не-JSON") from exc
    if not isinstance(body, dict):
        raise IntegrationError(ErrorKind.TRANSIENT, "DeepSeek вернул неожиданный ответ")
    return body


def _extract_text(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not stripped:
        raise IntegrationError(ErrorKind.TRANSIENT, "DeepSeek вернул пустой текст")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        if stripped.startswith("{"):
            raise IntegrationError(ErrorKind.TRANSIENT, "DeepSeek вернул неразборчивый JSON") from None
        return stripped
    if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
        text = parsed["text"].strip()
        if text:
            return text
    raise IntegrationError(ErrorKind.TRANSIENT, "В ответе DeepSeek нет поля text")


def _usage(raw: dict[str, object] | None) -> dict[str, int] | None:
    if raw is None:
        return None
    usage: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int):
            usage[key] = value
    return usage or None
