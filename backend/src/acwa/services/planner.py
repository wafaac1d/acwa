import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.domain.status import CampaignStatus, JobKind, PostOrigin, PostStatus
from acwa.errors import ApiError
from acwa.models import Campaign, Post, SkippedSlot, ThreadsAccount
from acwa.scheduling.calc import Schedule, schedule_from_campaign, slots_between, upcoming_slots
from acwa.services.jobs import cancel_open_jobs, enqueue_job


def plan_due_campaigns(session: Session, clock: Clock, settings: Settings) -> None:
    campaigns = session.scalars(select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)).all()
    now = clock.now()
    for campaign in campaigns:
        plan_campaign(session, campaign, now, settings)


def plan_campaign(session: Session, campaign: Campaign, now: datetime, settings: Settings) -> None:
    account = session.get(ThreadsAccount, campaign.account_id)
    if account is None or account.status != "connected":
        return
    in_flight = session.scalar(
        select(Post.id).where(
            Post.campaign_id == campaign.id,
            Post.origin == PostOrigin.SCHEDULE,
            Post.status.in_(
                [
                    PostStatus.GENERATING,
                    PostStatus.PENDING_APPROVAL,
                    PostStatus.SCHEDULED,
                    PostStatus.PUBLISHING,
                    PostStatus.UNKNOWN,
                ]
            ),
        )
    )
    if in_flight is not None:
        return
    cursor = campaign.schedule_cursor or campaign.created_at
    due = slots_between(schedule_from_campaign(campaign), after=cursor, until=now)
    if not due:
        return
    grace_edge = due[-1]
    actionable = grace_edge if now - grace_edge <= timedelta(seconds=settings.missed_slot_grace_seconds) else None
    for slot in due:
        if slot == actionable:
            continue
        _skip(session, campaign.id, slot, now)
    if actionable is not None and not _slot_exists(session, campaign.id, actionable):
        _create_slot_post(session, campaign, actionable, now, settings)
    campaign.schedule_cursor = due[-1]
    campaign.updated_at = now


def upcoming_for(campaign: Campaign, after: datetime, count: int = 5) -> list[datetime]:
    if campaign.status == CampaignStatus.ARCHIVED:
        return []
    return upcoming_slots(schedule_from_campaign(campaign), after, count)


def schedule_changed(before: Schedule, after: Schedule) -> bool:
    return before != after


def apply_schedule_change(session: Session, campaign: Campaign, now: datetime) -> None:
    posts = session.scalars(
        select(Post).where(
            Post.campaign_id == campaign.id,
            Post.origin == PostOrigin.SCHEDULE,
            Post.publish_dispatched_at.is_(None),
            Post.status.in_([PostStatus.SCHEDULED, PostStatus.GENERATING]),
        )
    ).all()
    for post in posts:
        cancel_open_jobs(session, post.id, now)
        if post.approved_at is not None:
            post.status = PostStatus.PENDING_APPROVAL
            post.scheduled_for = None
            post.last_error = "Расписание изменилось. Проверьте текст и одобрите публикацию заново."
        else:
            post.status = PostStatus.CANCELLED
            post.last_error = "Слот отменён: расписание кампании изменилось до отправки"
        post.updated_at = now
    campaign.schedule_cursor = now
    campaign.updated_at = now


def pause_campaign(session: Session, campaign: Campaign, now: datetime) -> None:
    if campaign.status == CampaignStatus.ARCHIVED:
        raise ApiError(409, "archived", "Архивную кампанию нельзя поставить на паузу")
    campaign.status = CampaignStatus.PAUSED
    campaign.schedule_cursor = now
    campaign.updated_at = now
    posts = session.scalars(
        select(Post).where(
            Post.campaign_id == campaign.id,
            Post.origin == PostOrigin.SCHEDULE,
            Post.publish_dispatched_at.is_(None),
            Post.status.in_([PostStatus.SCHEDULED, PostStatus.GENERATING]),
        )
    ).all()
    for post in posts:
        cancel_open_jobs(session, post.id, now)
        post.status = PostStatus.CANCELLED
        post.last_error = "Кампания на паузе, неотправленный слот отменён"
        post.updated_at = now


def resume_campaign(session: Session, campaign: Campaign, account: ThreadsAccount, now: datetime) -> None:
    if campaign.status == CampaignStatus.ARCHIVED:
        raise ApiError(409, "archived", "Сначала верните кампанию из архива")
    if account.status != "connected":
        raise ApiError(409, "account_unavailable", "Сначала подключите аккаунт Threads")
    campaign.status = CampaignStatus.ACTIVE
    campaign.schedule_cursor = now
    campaign.updated_at = now


def _create_slot_post(
    session: Session,
    campaign: Campaign,
    slot: datetime,
    now: datetime,
    settings: Settings,
) -> None:
    post = Post(
        campaign_id=campaign.id,
        account_id=campaign.account_id,
        origin=PostOrigin.SCHEDULE,
        status=PostStatus.GENERATING,
        scheduled_for=slot,
        created_at=now,
        updated_at=now,
    )
    session.add(post)
    session.flush()
    enqueue_job(
        session,
        post_id=post.id,
        kind=JobKind.GENERATE,
        run_at=now,
        max_attempts=settings.max_generate_attempts,
    )


def _skip(session: Session, campaign_id: uuid.UUID, slot: datetime, now: datetime) -> None:
    exists = session.scalar(
        select(SkippedSlot.id).where(
            SkippedSlot.campaign_id == campaign_id,
            SkippedSlot.slot_at == slot,
        )
    )
    if exists is not None:
        return
    session.add(
        SkippedSlot(
            campaign_id=campaign_id,
            slot_at=slot,
            reason="missed_outside_grace",
            created_at=now,
        )
    )


def _slot_exists(session: Session, campaign_id: uuid.UUID, slot: datetime) -> bool:
    found = session.scalar(
        select(Post.id).where(
            Post.campaign_id == campaign_id,
            Post.scheduled_for == slot,
            Post.origin == PostOrigin.SCHEDULE,
            Post.status != PostStatus.CANCELLED,
        )
    )
    return found is not None
