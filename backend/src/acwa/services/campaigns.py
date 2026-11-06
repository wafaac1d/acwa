from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.domain.campaign_rules import campaign_field_errors
from acwa.domain.status import CampaignStatus
from acwa.errors import ApiError
from acwa.models import Campaign, ThreadsAccount
from acwa.scheduling.calc import Schedule, schedule_from_campaign
from acwa.services.accounts import assert_account_usable
from acwa.services.planner import apply_schedule_change, pause_campaign, resume_campaign

FIELDS = (
    "name",
    "topic",
    "context",
    "audience",
    "language",
    "tone",
    "goal",
    "desired_length",
    "extra_instructions",
    "required_points",
    "forbidden",
    "examples",
    "allow_emoji",
    "allow_hashtags",
    "allow_links",
    "publish_mode",
    "timezone",
    "weekdays",
    "times_of_day",
    "starts_on",
    "ends_on",
    "threads_topic_tag",
    "reply_text",
)


def save_campaign(
    session: Session,
    *,
    campaign: Campaign | None,
    payload: dict[str, object],
    account: ThreadsAccount,
    clock: Clock,
    activate: bool,
) -> Campaign:
    data = dict(payload)
    data["account_id"] = account.id
    errors = campaign_field_errors(data)
    if errors:
        raise ApiError(422, "validation_error", "Проверьте поля кампании", errors)
    if activate or (campaign is not None and campaign.status == CampaignStatus.ACTIVE):
        assert_account_usable(account)
    now = clock.now()
    previous = schedule_from_campaign(campaign) if campaign is not None else None
    if campaign is None:
        campaign = Campaign(account_id=account.id, created_at=now, status=CampaignStatus.PAUSED)
        session.add(campaign)
    for field in FIELDS:
        value = data.get(field)
        if field == "weekdays" and isinstance(value, list):
            value = sorted(set(value))
        if field == "times_of_day" and isinstance(value, list):
            value = sorted(set(value))
        setattr(campaign, field, value if value is not None else _empty(field))
    campaign.account_id = account.id
    campaign.updated_at = now
    current = Schedule(
        timezone=str(campaign.timezone),
        weekdays=tuple(int(item) for item in campaign.weekdays),
        times=tuple(str(item) for item in campaign.times_of_day),
        starts_on=campaign.starts_on,
        ends_on=campaign.ends_on if isinstance(campaign.ends_on, date) else None,
    )
    if previous is not None and previous != current:
        apply_schedule_change(session, campaign, now)
    if activate:
        resume_campaign(session, campaign, account, now)
    elif campaign.status == CampaignStatus.ACTIVE:
        campaign.updated_at = now
    return campaign


def set_paused(session: Session, campaign: Campaign, clock: Clock) -> Campaign:
    pause_campaign(session, campaign, clock.now())
    return campaign


def set_active(session: Session, campaign: Campaign, account: ThreadsAccount, clock: Clock) -> Campaign:
    resume_campaign(session, campaign, account, clock.now())
    return campaign


def archive_campaign(session: Session, campaign: Campaign, clock: Clock) -> Campaign:
    now = clock.now()
    if campaign.status == CampaignStatus.ACTIVE:
        pause_campaign(session, campaign, now)
    campaign.status = CampaignStatus.ARCHIVED
    campaign.updated_at = now
    return campaign


def unarchive_campaign(session: Session, campaign: Campaign, clock: Clock) -> Campaign:
    campaign.status = CampaignStatus.PAUSED
    campaign.schedule_cursor = clock.now()
    campaign.updated_at = clock.now()
    return campaign


def _empty(field: str) -> object:
    if field in {"context", "audience", "goal", "extra_instructions", "required_points", "forbidden", "examples"}:
        return ""
    if field in {"ends_on", "threads_topic_tag", "reply_text"}:
        return None
    raise ApiError(422, "validation_error", "Не хватает поля кампании", {field: "Обязательное поле"})


def account_id_of(payload: dict[str, object]) -> UUID:
    value = payload.get("account_id")
    if isinstance(value, UUID):
        return value
    raise ApiError(422, "validation_error", "Выберите аккаунт", {"account_id": "Выберите аккаунт"})
