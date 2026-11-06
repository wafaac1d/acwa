import uuid
from datetime import UTC, datetime, timedelta

from acwa.content.prompt import Prompt
from acwa.integrations.types import (
    ContainerInfo,
    GenerationResult,
    MediaInfo,
    MediaInsights,
    PublishingLimit,
    PublishResult,
    ThreadsProfile,
    TokenBundle,
)


class DemoGenerator:
    """Local generator. The text is explicitly marked and is not a model call."""

    def generate(self, prompt: Prompt) -> GenerationResult:
        topic = _topic_from_prompt(prompt.user)
        text = (
            f"[демо {prompt_variation(prompt.user)}] {topic}. "
            "Демонстрационный текст: в Threads и DeepSeek ничего не отправлялось."
        )
        return GenerationResult(
            text=text,
            model="demo",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )


class DemoThreads:
    """In-memory Threads stand-in.

    Publications stay inside the app and use demo: identifiers.
    permalink is always empty so the UI cannot present a real Threads link.
    """

    def __init__(self) -> None:
        self.container_text: dict[str, str] = {}
        self.creates: list[dict[str, str | None]] = []
        self.published_containers: set[str] = set()
        self.media: dict[str, str] = {}
        self.fail_publish_times = 0
        self.rate_limit_times = 0
        self.auth_failures = 0
        self.publish_calls = 0
        self.create_calls = 0
        self.insight_calls = 0

    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        del code, redirect_uri
        return TokenBundle(access_token="demo-short", expires_in=3600, user_id="demo-user")

    def exchange_long_lived(self, short_lived_token: str) -> TokenBundle:
        del short_lived_token
        return TokenBundle(access_token="demo-long", expires_in=5_183_944, user_id=None)

    def refresh_long_lived(self, access_token: str) -> TokenBundle:
        del access_token
        return TokenBundle(access_token="demo-refreshed", expires_in=5_183_944, user_id=None)

    def get_profile(self, user_id: str, access_token: str) -> ThreadsProfile:
        del access_token
        return ThreadsProfile(
            user_id=user_id,
            username="demo_account",
            name="Демонстрационный аккаунт",
            profile_picture_url=None,
        )

    def publishing_limit(self, user_id: str, access_token: str) -> PublishingLimit:
        del user_id, access_token
        return PublishingLimit(quota_usage=0, quota_total=250, quota_duration=86400)

    def create_text_container(
        self,
        user_id: str,
        access_token: str,
        text: str,
        *,
        reply_to_id: str | None = None,
        topic_tag: str | None = None,
    ) -> str:
        del user_id, access_token
        self.create_calls += 1
        container_id = f"demo-container-{uuid.uuid4()}"
        self.container_text[container_id] = text
        self.creates.append({"text": text, "reply_to_id": reply_to_id, "topic_tag": topic_tag})
        return container_id

    def get_container(self, container_id: str, access_token: str) -> ContainerInfo:
        del access_token
        status = "PUBLISHED" if container_id in self.published_containers else "FINISHED"
        return ContainerInfo(container_id=container_id, status=status)

    def publish_container(self, user_id: str, access_token: str, container_id: str) -> PublishResult:
        del user_id, access_token
        self.publish_calls += 1
        if self.auth_failures > 0:
            self.auth_failures -= 1
            from acwa.integrations.types import ErrorKind, IntegrationError

            raise IntegrationError(
                ErrorKind.AUTH,
                "Срок авторизации Threads истёк или доступ отозван. Подключите аккаунт заново.",
            )
        if self.rate_limit_times > 0:
            self.rate_limit_times -= 1
            from acwa.integrations.types import ErrorKind, IntegrationError

            raise IntegrationError(
                ErrorKind.RATE_LIMIT,
                "Threads ограничил частоту запросов или число публикаций",
                retry_after=timedelta(minutes=15),
            )
        if self.fail_publish_times > 0:
            self.fail_publish_times -= 1
            from acwa.integrations.types import AmbiguousPublishError

            raise AmbiguousPublishError("Таймаут во время публикации в Threads. Повтор автоматически не выполняется.")
        media_id = f"demo:{uuid.uuid4()}"
        text = self.container_text.get(container_id, "")
        self.published_containers.add(container_id)
        self.media[media_id] = text
        return PublishResult(media_id=media_id, permalink=None, is_demo=True)

    def media_insights(self, media_id: str, access_token: str) -> MediaInsights:
        del media_id, access_token
        self.insight_calls += 1
        from acwa.integrations.types import ErrorKind, IntegrationError

        raise IntegrationError(
            ErrorKind.PERMANENT,
            "Демонстрационный режим не запрашивает статистику Threads.",
        )

    def list_recent_posts(self, user_id: str, access_token: str) -> list[MediaInfo]:
        del user_id, access_token
        now = datetime.now(UTC)
        return [
            MediaInfo(media_id=media_id, text=text, permalink=None, timestamp=now)
            for media_id, text in self.media.items()
        ]


def prompt_variation(user_prompt: str) -> str:
    marker = "Номер варианта: "
    if marker not in user_prompt:
        return "1"
    tail = user_prompt.split(marker, 1)[1]
    return tail.split(".", 1)[0].strip() or "1"


def _topic_from_prompt(user_prompt: str) -> str:
    for line in user_prompt.splitlines():
        if line.startswith("Тема: "):
            topic = line.removeprefix("Тема: ").strip()
            return topic or "без темы"
    return "без темы"
