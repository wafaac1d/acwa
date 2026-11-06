"""Threads API client.

Endpoints and fields follow the official Threads documentation:
authorization window, code exchange, long-lived tokens, text container
creation, threads_publish, container status, user profile, recent posts
and the publishing limit. GET calls pass access_token as the documented
query parameter; those URLs are never logged.
"""

import json
from datetime import UTC, datetime
from typing import Protocol

import httpx

from acwa.config import Settings
from acwa.integrations.types import (
    AmbiguousPublishError,
    ContainerInfo,
    ErrorKind,
    IntegrationError,
    MediaInfo,
    PublishingLimit,
    PublishResult,
    ThreadsProfile,
    TokenBundle,
)
from acwa.security.redact import redact

RATE_LIMIT_CODES = {4, 17, 32, 613}
AUTH_CODES = {102, 190}
CONTAINER_STATUSES = {"EXPIRED", "ERROR", "FINISHED", "IN_PROGRESS", "PUBLISHED"}


class ThreadsGateway(Protocol):
    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle: ...

    def exchange_long_lived(self, short_lived_token: str) -> TokenBundle: ...

    def refresh_long_lived(self, access_token: str) -> TokenBundle: ...

    def get_profile(self, user_id: str, access_token: str) -> ThreadsProfile: ...

    def publishing_limit(self, user_id: str, access_token: str) -> PublishingLimit: ...

    def create_text_container(self, user_id: str, access_token: str, text: str) -> str: ...

    def get_container(self, container_id: str, access_token: str) -> ContainerInfo: ...

    def publish_container(self, user_id: str, access_token: str, container_id: str) -> PublishResult: ...

    def list_recent_posts(self, user_id: str, access_token: str) -> list[MediaInfo]: ...


class ThreadsClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        self._require_app()
        response = self._request(
            "POST",
            "/oauth/access_token",
            data={
                "client_id": self._settings.threads_app_id or "",
                "client_secret": self._settings.threads_app_secret or "",
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code.removesuffix("#_"),
            },
            ambiguous=False,
        )
        body = _object(response)
        token = body.get("access_token")
        user_id = body.get("user_id")
        if not isinstance(token, str) or user_id is None:
            raise IntegrationError(ErrorKind.PERMANENT, "Threads не вернул токен доступа")
        return TokenBundle(access_token=token, expires_in=None, user_id=str(user_id))

    def exchange_long_lived(self, short_lived_token: str) -> TokenBundle:
        self._require_app()
        response = self._request(
            "GET",
            "/access_token",
            params={
                "grant_type": "th_exchange_token",
                "client_secret": self._settings.threads_app_secret or "",
                "access_token": short_lived_token,
            },
            ambiguous=False,
        )
        return _token_bundle(response, user_id=None)

    def refresh_long_lived(self, access_token: str) -> TokenBundle:
        response = self._request(
            "GET",
            "/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": access_token},
            ambiguous=False,
        )
        return _token_bundle(response, user_id=None)

    def get_profile(self, user_id: str, access_token: str) -> ThreadsProfile:
        response = self._request(
            "GET",
            f"/v1.0/{user_id}",
            params={
                "fields": "id,username,name,threads_profile_picture_url",
                "access_token": access_token,
            },
            ambiguous=False,
        )
        body = _object(response)
        raw_id = body.get("id")
        if raw_id is None:
            raise IntegrationError(ErrorKind.PERMANENT, "Threads не вернул профиль")
        return ThreadsProfile(
            user_id=str(raw_id),
            username=_optional_str(body.get("username")),
            name=_optional_str(body.get("name")),
            profile_picture_url=_optional_str(body.get("threads_profile_picture_url")),
        )

    def publishing_limit(self, user_id: str, access_token: str) -> PublishingLimit:
        response = self._request(
            "GET",
            f"/v1.0/{user_id}/threads_publishing_limit",
            params={"fields": "quota_usage,config", "access_token": access_token},
            ambiguous=False,
        )
        body = _object(response)
        data = body.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise IntegrationError(ErrorKind.TRANSIENT, "Threads не вернул лимит публикаций")
        row = data[0]
        raw_config = row.get("config")
        config: dict[str, object] = raw_config if isinstance(raw_config, dict) else {}
        usage = row.get("quota_usage")
        total = config.get("quota_total")
        duration = config.get("quota_duration")
        if not isinstance(usage, int) or not isinstance(total, int):
            raise IntegrationError(ErrorKind.TRANSIENT, "Threads вернул неполный лимит публикаций")
        return PublishingLimit(
            quota_usage=usage,
            quota_total=total,
            quota_duration=duration if isinstance(duration, int) else 86400,
        )

    def create_text_container(self, user_id: str, access_token: str, text: str) -> str:
        response = self._request(
            "POST",
            f"/v1.0/{user_id}/threads",
            data={"media_type": "TEXT", "text": text, "access_token": access_token},
            ambiguous=False,
        )
        body = _object(response)
        container_id = body.get("id")
        if not isinstance(container_id, str):
            raise IntegrationError(ErrorKind.PERMANENT, "Threads не вернул идентификатор контейнера")
        return container_id

    def get_container(self, container_id: str, access_token: str) -> ContainerInfo:
        response = self._request(
            "GET",
            f"/v1.0/{container_id}",
            params={"fields": "status,error_message", "access_token": access_token},
            ambiguous=False,
        )
        body = _object(response)
        status = body.get("status")
        if not isinstance(status, str) or status not in CONTAINER_STATUSES:
            raise IntegrationError(ErrorKind.TRANSIENT, "Threads вернул неизвестный статус контейнера")
        error_message = body.get("error_message")
        return ContainerInfo(
            container_id=container_id,
            status=status,
            error_message=error_message if isinstance(error_message, str) else None,
        )

    def publish_container(self, user_id: str, access_token: str, container_id: str) -> PublishResult:
        response = self._request(
            "POST",
            f"/v1.0/{user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": access_token},
            ambiguous=True,
        )
        body = _object(response)
        media_id = body.get("id")
        if not isinstance(media_id, str):
            raise AmbiguousPublishError("Threads не подтвердил идентификатор поста после запроса публикации")
        return PublishResult(media_id=media_id, permalink=None, is_demo=False)

    def list_recent_posts(self, user_id: str, access_token: str) -> list[MediaInfo]:
        response = self._request(
            "GET",
            f"/v1.0/{user_id}/threads",
            params={
                "fields": "id,permalink,text,timestamp",
                "limit": "25",
                "access_token": access_token,
            },
            ambiguous=False,
        )
        body = _object(response)
        data = body.get("data")
        if not isinstance(data, list):
            raise IntegrationError(ErrorKind.TRANSIENT, "Threads не вернул список постов")
        items: list[MediaInfo] = []
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            items.append(
                MediaInfo(
                    media_id=row["id"],
                    text=_optional_str(row.get("text")),
                    permalink=_optional_str(row.get("permalink")),
                    timestamp=_parse_timestamp(row.get("timestamp")),
                )
            )
        return items

    def _require_app(self) -> None:
        if not self._settings.threads_app_id or not self._settings.threads_app_secret:
            raise IntegrationError(
                ErrorKind.PERMANENT,
                "Не заданы ACWA_THREADS_APP_ID и ACWA_THREADS_APP_SECRET",
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        ambiguous: bool,
    ) -> httpx.Response:
        url = self._settings.threads_graph_base_url.rstrip("/") + path
        timeout = httpx.Timeout(self._settings.threads_timeout_seconds, connect=10.0)
        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as client:
                response = client.request(method, url, params=params, data=data)
        except httpx.TimeoutException as exc:
            if ambiguous:
                raise AmbiguousPublishError(
                    "Таймаут во время публикации в Threads. Повтор автоматически не выполняется."
                ) from exc
            raise IntegrationError(ErrorKind.TRANSIENT, "Threads не ответил вовремя") from exc
        except httpx.HTTPError as exc:
            if ambiguous:
                raise AmbiguousPublishError(
                    "Сеть оборвалась во время публикации в Threads. Повтор автоматически не выполняется."
                ) from exc
            raise IntegrationError(ErrorKind.TRANSIENT, "Сбой сети при обращении к Threads") from exc
        if response.status_code >= 400:
            raise _map_threads_error(response, ambiguous=ambiguous)
        return response


def _map_threads_error(response: httpx.Response, *, ambiguous: bool) -> IntegrationError:
    message = "Threads вернул ошибку"
    code: int | None = None
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = None
    if isinstance(body, dict):
        error = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(error, dict):
            raw_code = error.get("code")
            if isinstance(raw_code, int):
                code = raw_code
            raw_message = error.get("message") or error.get("error_message")
            if isinstance(raw_message, str):
                message = redact(raw_message)[:300]
    if response.status_code == 429 or code in RATE_LIMIT_CODES:
        return IntegrationError(
            ErrorKind.RATE_LIMIT,
            "Threads ограничил частоту запросов или число публикаций",
            http_status=response.status_code,
        )
    if response.status_code in {401, 403} or code in AUTH_CODES:
        return IntegrationError(
            ErrorKind.AUTH,
            "Срок авторизации Threads истёк или доступ отозван. Подключите аккаунт заново.",
            http_status=response.status_code,
        )
    if response.status_code >= 500:
        if ambiguous:
            return AmbiguousPublishError(message)
        return IntegrationError(ErrorKind.TRANSIENT, message, http_status=response.status_code)
    return IntegrationError(ErrorKind.PERMANENT, message, http_status=response.status_code)


def _token_bundle(response: httpx.Response, user_id: str | None) -> TokenBundle:
    body = _object(response)
    token = body.get("access_token")
    expires_in = body.get("expires_in")
    if not isinstance(token, str):
        raise IntegrationError(ErrorKind.PERMANENT, "Threads не вернул долгоживущий токен")
    return TokenBundle(
        access_token=token,
        expires_in=expires_in if isinstance(expires_in, int) else None,
        user_id=user_id,
    )


def _object(response: httpx.Response) -> dict[str, object]:
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise IntegrationError(ErrorKind.TRANSIENT, "Threads вернул не-JSON") from exc
    if not isinstance(body, dict):
        raise IntegrationError(ErrorKind.TRANSIENT, "Threads вернул неожиданный ответ")
    return body


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
