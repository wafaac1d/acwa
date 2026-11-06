"""Yesterday's posts and their current Threads insight totals.

Media insights are lifetime counters for one post, not the gain during that day.
The window selects posts published yesterday in the campaign timezone.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.domain.status import PostStatus
from acwa.integrations.threads import ThreadsGateway
from acwa.integrations.types import ErrorKind, IntegrationError
from acwa.models import Campaign, Post, ThreadsAccount
from acwa.security.crypto import TokenCipher
from acwa.security.redact import redact
from acwa.services.pipeline import _token

INSIGHT_KEYS = ("views", "likes", "replies", "reposts", "quotes", "shares")
SCOPE_MESSAGE = (
    "Threads не отдал статистику. Добавьте разрешение threads_manage_insights "
    "в приложении Meta и подключите аккаунт заново."
)


def yesterday_window(now: datetime, timezone: str) -> tuple[datetime, datetime, str]:
    zone = ZoneInfo(timezone)
    local_now = now.astimezone(zone)
    start_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday = start_today - timedelta(days=1)
    return (
        start_yesterday.astimezone(UTC),
        start_today.astimezone(UTC),
        start_yesterday.date().isoformat(),
    )


def yesterday_posts(session: Session, campaign: Campaign, clock: Clock) -> tuple[str, list[Post]]:
    start, end, label = yesterday_window(clock.now(), campaign.timezone)
    rows = session.scalars(
        select(Post)
        .where(
            Post.campaign_id == campaign.id,
            Post.status == PostStatus.PUBLISHED,
            Post.published_at.is_not(None),
            Post.published_at >= start,
            Post.published_at < end,
        )
        .order_by(Post.published_at.desc())
        .limit(100)
    ).all()
    return label, list(rows)


def collect_yesterday_insights(
    session: Session,
    campaign: Campaign,
    *,
    threads: ThreadsGateway,
    cipher: TokenCipher,
    clock: Clock,
    settings: Settings,
) -> str:
    """Fetch insights for yesterday's posts. Returns a notice when Threads is not called."""
    _, posts = yesterday_posts(session, campaign, clock)
    account = session.get(ThreadsAccount, campaign.account_id)
    if account is None:
        return "Аккаунт кампании не найден."
    if settings.integration_mode != "live" or account.is_demo:
        return "В демонстрационном режиме Threads не отдаёт статистику. Цифры ниже не запрашивались."
    if account.status != "connected":
        return "Аккаунт Threads не подключён. Статистика не запрашивалась."
    try:
        token = _token(session, account, threads, cipher, clock)
    except IntegrationError as exc:
        return redact(exc.message)
    now = clock.now()
    for post in posts:
        if post.is_demo_publication or not post.external_id or post.external_id.startswith("demo:"):
            post.insights_error = "Демонстрационная публикация, статистики Threads нет."
            post.updated_at = now
            continue
        try:
            metrics = threads.media_insights(post.external_id, token)
        except IntegrationError as exc:
            post.insights_error = (
                SCOPE_MESSAGE if exc.kind in {ErrorKind.AUTH, ErrorKind.PERMANENT} else redact(exc.message)
            )
            post.updated_at = now
            continue
        post.insights = {
            key: value
            for key, value in (
                ("views", metrics.views),
                ("likes", metrics.likes),
                ("replies", metrics.replies),
                ("reposts", metrics.reposts),
                ("quotes", metrics.quotes),
                ("shares", metrics.shares),
            )
            if type(value) is int
        }
        post.insights_collected_at = now
        post.insights_error = None
        post.updated_at = now
    return ""
