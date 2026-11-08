from dataclasses import dataclass
from datetime import date, datetime, timedelta

from acwa.models import Campaign


class ErrorKind:
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    AMBIGUOUS = "ambiguous"


@dataclass
class IntegrationError(Exception):
    kind: str
    message: str
    retry_after: timedelta | None = None
    http_status: int | None = None
    code: int | None = None

    def __str__(self) -> str:
        return self.message


class AmbiguousPublishError(IntegrationError):
    def __init__(self, message: str) -> None:
        super().__init__(kind=ErrorKind.AMBIGUOUS, message=message)


class Postpone(Exception):
    def __init__(self, delay: timedelta, message: str) -> None:
        super().__init__(message)
        self.delay = delay
        self.message = message


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    usage: dict[str, int] | None


@dataclass(frozen=True)
class ThreadsProfile:
    user_id: str
    username: str | None
    name: str | None
    profile_picture_url: str | None


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    expires_in: int | None
    user_id: str | None = None


@dataclass(frozen=True)
class ContainerInfo:
    container_id: str
    status: str
    error_message: str | None = None


@dataclass(frozen=True)
class MediaInfo:
    media_id: str
    text: str | None
    permalink: str | None
    timestamp: datetime | None


@dataclass(frozen=True)
class MediaInsights:
    views: int | None = None
    likes: int | None = None
    replies: int | None = None
    reposts: int | None = None
    quotes: int | None = None
    shares: int | None = None


@dataclass(frozen=True)
class PublishingLimit:
    quota_usage: int
    quota_total: int
    quota_duration: int


@dataclass(frozen=True)
class PublishResult:
    media_id: str
    permalink: str | None
    is_demo: bool


def should_refresh_token(
    *,
    obtained_at: datetime,
    expires_at: datetime,
    now: datetime,
) -> bool:
    """Long-lived Threads tokens refresh only after 24 hours and before expiry."""
    if expires_at <= now:
        return False
    if now < obtained_at + timedelta(hours=24):
        return False
    return expires_at <= now + timedelta(days=7)


def token_is_expired(*, expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and expires_at <= now


def campaign_snapshot(campaign: Campaign) -> dict[str, object]:
    ends_on = campaign.ends_on
    return {
        "name": campaign.name,
        "topic": campaign.topic,
        "context": campaign.context,
        "audience": campaign.audience,
        "language": campaign.language,
        "tone": campaign.tone,
        "goal": campaign.goal,
        "desired_length": campaign.desired_length,
        "extra_instructions": campaign.extra_instructions,
        "required_points": campaign.required_points,
        "forbidden": campaign.forbidden,
        "examples": campaign.examples,
        "allow_emoji": campaign.allow_emoji,
        "allow_hashtags": campaign.allow_hashtags,
        "allow_links": campaign.allow_links,
        "publish_mode": campaign.publish_mode,
        "timezone": campaign.timezone,
        "weekdays": list(campaign.weekdays),
        "times_of_day": list(campaign.times_of_day),
        "starts_on": campaign.starts_on.isoformat(),
        "ends_on": ends_on.isoformat() if isinstance(ends_on, date) else None,
    }
