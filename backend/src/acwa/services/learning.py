"""Nightly learning: collect yesterday's insights and adjust the next prompt.

The user's context field stays as written. The adjustment is a separate note
built only from Threads numbers that were actually returned. Demo mode does
not invent engagement. After downtime only the latest finished day is learned;
missed midnights are not replayed one by one.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.domain.status import CampaignStatus
from acwa.integrations.threads import ThreadsGateway
from acwa.integrations.types import IntegrationError
from acwa.models import Campaign, Post
from acwa.security.crypto import TokenCipher
from acwa.security.redact import redact
from acwa.services.insights import collect_yesterday_insights, yesterday_posts

METRIC_LABELS = (
    ("views", "просмотры"),
    ("likes", "лайки"),
    ("replies", "ответы"),
    ("reposts", "репосты"),
    ("quotes", "цитаты"),
    ("shares", "пересылки"),
)
NOTES_LIMIT = 2000


def next_local_midnight(now: datetime, timezone: str) -> datetime:
    """The current local midnight if now is exactly then, otherwise the next one."""
    zone = ZoneInfo(timezone)
    local = now.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if local > start:
        start += timedelta(days=1)
    return start.astimezone(UTC)


def midnight_after(now: datetime, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    local = now.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return start.astimezone(UTC)


def learn_due_campaigns(
    session: Session,
    *,
    clock: Clock,
    settings: Settings,
    threads: ThreadsGateway,
    cipher: TokenCipher,
) -> None:
    now = clock.now()
    campaigns = session.scalars(
        select(Campaign).where(
            Campaign.learning_enabled.is_(True),
            Campaign.status != CampaignStatus.ARCHIVED,
            Campaign.learning_next_at.is_not(None),
            Campaign.learning_next_at <= now,
        )
    ).all()
    for campaign in campaigns:
        try:
            learn_campaign(session, campaign, clock=clock, settings=settings, threads=threads, cipher=cipher)
        except IntegrationError as exc:
            campaign.learning_status = redact(exc.message)[:500]
        except Exception:
            campaign.learning_status = "Не удалось обновить обучение."
        campaign.learning_checked_at = now
        campaign.learning_next_at = midnight_after(now, campaign.timezone)
        campaign.updated_at = now


def learn_campaign(
    session: Session,
    campaign: Campaign,
    *,
    clock: Clock,
    settings: Settings,
    threads: ThreadsGateway,
    cipher: TokenCipher,
) -> None:
    notice = collect_yesterday_insights(
        session,
        campaign,
        threads=threads,
        cipher=cipher,
        clock=clock,
        settings=settings,
    )
    label, posts = yesterday_posts(session, campaign, clock)
    if notice:
        campaign.learning_status = notice
        return
    measured = [post for post in posts if _measured(post)]
    if not posts:
        campaign.learning_status = "Вчера опубликованных постов не было. Контекст генерации не менялся."
        return
    if not measured:
        campaign.learning_status = "Статистика Threads за вчера не собрана. Контекст генерации не менялся."
        return
    campaign.learning_notes = learning_notes(measured, date_label=label, timezone=campaign.timezone)[:NOTES_LIMIT]
    campaign.learning_status = f"Контекст генерации уточнён по статистике за {label}."


def learning_notes(posts: list[Post], *, date_label: str, timezone: str) -> str:
    ranked = sorted(posts, key=_score, reverse=True)
    best = ranked[0]
    worst = ranked[-1]
    intro = (
        f"Статистика за {date_label} ({timezone}). Цифры — текущие итоги Threads на момент сбора, не прирост за день."
    )
    if best.id == worst.id or _score(best) == _score(worst):
        body = (
            f"За этот день опубликован пост ({_metrics(best)}): «{_excerpt(best.text)}». "
            "В следующих текстах сохраняй его конкретные детали и не растягивай мысль. Формулировки не копируй."
        )
    else:
        body = (
            f"Сильнее остальных набрал пост ({_metrics(best)}): «{_excerpt(best.text)}». "
            "В следующих текстах держись ближе к его конкретике и длине. Формулировки не копируй. "
            f"Слабее набрал пост ({_metrics(worst)}): «{_excerpt(worst.text)}». Такой приём не повторяй."
        )
    return f"{intro} {body}"


def _measured(post: Post) -> bool:
    if post.insights_collected_at is None or post.insights_error:
        return False
    data = post.insights if isinstance(post.insights, dict) else {}
    return any(type(data.get(key)) is int for key, _label in METRIC_LABELS)


def _score(post: Post) -> tuple[int, int, int]:
    data = post.insights if isinstance(post.insights, dict) else {}

    def number(key: str) -> int:
        value = data.get(key)
        return value if type(value) is int else 0

    return (
        number("views"),
        number("likes"),
        number("replies") + number("reposts") + number("quotes") + number("shares"),
    )


def _metrics(post: Post) -> str:
    data = post.insights if isinstance(post.insights, dict) else {}
    parts = [f"{label} {data[key]}" for key, label in METRIC_LABELS if type(data.get(key)) is int]
    return ", ".join(parts) if parts else "без цифр"


def _excerpt(text: str | None) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "без текста"
    if len(cleaned) > 140:
        return cleaned[:137] + "…"
    return cleaned
