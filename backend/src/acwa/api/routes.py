from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from acwa.api.deps import decode_cursor, encode_cursor, get_cipher, get_clock, get_session, get_settings
from acwa.api.schemas import (
    AccountPage,
    AccountRead,
    AttemptRead,
    CampaignPage,
    CampaignRead,
    CampaignSummary,
    CampaignWrite,
    DashboardRead,
    DeepSeekPublic,
    GenerationSettings,
    HealthResponse,
    OAuthStartRead,
    PostPage,
    PostRead,
    PostTextUpdate,
    SettingsRead,
    SettingsUpdate,
    SkippedSlotRead,
    SlotRead,
    ThreadsPublic,
)
from acwa.clock import Clock
from acwa.config import PROMPT_VERSION, THREADS_TEXT_LIMIT, Settings
from acwa.domain.status import HISTORY_STATUSES, MISSED_SLOT_POLICY, QUEUE_STATUSES, UNAPPROVED_OVERDUE_POLICY
from acwa.errors import ApiError
from acwa.models import AppSetting, Campaign, Post, PostAttempt, SkippedSlot, ThreadsAccount
from acwa.security.crypto import TokenCipher
from acwa.services.accounts import (
    complete_oauth,
    connect_demo,
    disconnect_account,
    public_account_dict,
    start_oauth,
)
from acwa.services.campaigns import archive_campaign, save_campaign, set_active, set_paused, unarchive_campaign
from acwa.services.pipeline import (
    approve_post,
    cancel_post,
    regenerate_post,
    reject_post,
    request_trial,
    retry_publish,
    update_post_text,
)
from acwa.services.planner import upcoming_for

router = APIRouter(prefix="/api")
DEMO_BANNER = "Демонстрационный режим. Тексты помечаются как демо, в DeepSeek и Threads ничего не отправляется."


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    database = "ok"
    try:
        from sqlalchemy import text

        from acwa.db import get_engine

        with get_engine().connect() as connection:
            connection.execute(text("select 1"))
    except Exception:
        database = "error"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        integration_mode=settings.integration_mode,
        auth_required=bool(settings.auth_token),
        public_deployment_ready=False,
    )


@router.get("/settings", response_model=SettingsRead)
def read_settings(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SettingsRead:
    row = _settings_row(session, settings)
    return _settings_read(settings, row)


@router.patch("/settings", response_model=SettingsRead)
def update_settings(
    body: SettingsUpdate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> SettingsRead:
    row = _settings_row(session, settings)
    row.temperature = body.temperature
    row.max_tokens = body.max_tokens
    row.updated_at = clock.now()
    return _settings_read(settings, row)


@router.get("/accounts", response_model=AccountPage)
def list_accounts(
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> AccountPage:
    rows = session.scalars(select(ThreadsAccount).order_by(ThreadsAccount.created_at.desc())).all()
    return AccountPage(
        items=[AccountRead.model_validate(public_account_dict(row, clock.now())) for row in rows],
        next_cursor=None,
    )


@router.post("/accounts/demo", response_model=AccountRead)
def create_demo_account(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
    cipher: TokenCipher = Depends(get_cipher),
) -> AccountRead:
    account = connect_demo(session, cipher, clock, settings)
    return AccountRead.model_validate(public_account_dict(account, clock.now()))


@router.post("/accounts/threads/start", response_model=OAuthStartRead)
def oauth_start(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> OAuthStartRead:
    return OAuthStartRead(authorization_url=start_oauth(session, clock, settings))


@router.get("/accounts/threads/callback")
def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
    cipher: TokenCipher = Depends(get_cipher),
) -> RedirectResponse:
    target = complete_oauth(
        session,
        code=code,
        state=state,
        error=error,
        clock=clock,
        settings=settings,
        threads=request.app.state.threads,
        cipher=cipher,
    )
    return RedirectResponse(target, status_code=302)


@router.post("/accounts/{account_id}/disconnect", response_model=AccountRead)
def disconnect(
    account_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> AccountRead:
    account = _account(session, account_id)
    disconnect_account(session, account, clock)
    return AccountRead.model_validate(public_account_dict(account, clock.now()))


@router.get("/campaigns", response_model=CampaignPage)
def list_campaigns(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignPage:
    stmt = select(Campaign).order_by(Campaign.created_at.desc(), Campaign.id.desc())
    if status:
        stmt = stmt.where(Campaign.status == status)
    if cursor:
        moment, ident = decode_cursor(cursor)
        stmt = stmt.where(tuple_(Campaign.created_at, Campaign.id) < tuple_(moment, ident))
    rows = session.scalars(stmt.limit(limit + 1)).all()
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit and page else None
    return CampaignPage(
        items=[_summary(row, clock) for row in page],
        next_cursor=next_cursor,
    )


@router.post("/campaigns", response_model=CampaignRead, status_code=201)
def create_campaign(
    body: CampaignWrite,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    account = _account(session, str(body.account_id))
    campaign = save_campaign(
        session,
        campaign=None,
        payload=body.model_dump(),
        account=account,
        clock=clock,
        activate=body.activate,
    )
    session.flush()
    return _campaign_read(session, campaign, clock)


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    return _campaign_read(session, _campaign(session, campaign_id), clock)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: str,
    body: CampaignWrite,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    campaign = _campaign(session, campaign_id)
    account = _account(session, str(body.account_id))
    save_campaign(
        session,
        campaign=campaign,
        payload=body.model_dump(),
        account=account,
        clock=clock,
        activate=body.activate,
    )
    return _campaign_read(session, campaign, clock)


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignRead)
def pause(
    campaign_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    campaign = set_paused(session, _campaign(session, campaign_id), clock)
    return _campaign_read(session, campaign, clock)


@router.post("/campaigns/{campaign_id}/resume", response_model=CampaignRead)
def resume(
    campaign_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    campaign = _campaign(session, campaign_id)
    account = _account(session, str(campaign.account_id))
    set_active(session, campaign, account, clock)
    return _campaign_read(session, campaign, clock)


@router.post("/campaigns/{campaign_id}/archive", response_model=CampaignRead)
def archive(
    campaign_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    campaign = archive_campaign(session, _campaign(session, campaign_id), clock)
    return _campaign_read(session, campaign, clock)


@router.post("/campaigns/{campaign_id}/unarchive", response_model=CampaignRead)
def unarchive(
    campaign_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> CampaignRead:
    campaign = unarchive_campaign(session, _campaign(session, campaign_id), clock)
    return _campaign_read(session, campaign, clock)


@router.post("/campaigns/{campaign_id}/trial", response_model=PostRead, status_code=202)
def trial(
    campaign_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    post = request_trial(session, _campaign(session, campaign_id), clock, settings)
    session.flush()
    return _post_read(session, post)


@router.get("/posts", response_model=PostPage)
def list_posts(
    view: str = Query(default="queue", pattern="^(queue|history|all)$"),
    status: str | None = None,
    campaign_id: str | None = None,
    origin: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    session: Session = Depends(get_session),
) -> PostPage:
    stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc())
    if status:
        stmt = stmt.where(Post.status == status)
    elif view == "queue":
        stmt = stmt.where(Post.status.in_([item.value for item in QUEUE_STATUSES]))
    elif view == "history":
        stmt = stmt.where(Post.status.in_([item.value for item in HISTORY_STATUSES]))
    if campaign_id:
        stmt = stmt.where(Post.campaign_id == _uuid(campaign_id, "campaign_id"))
    if origin:
        stmt = stmt.where(Post.origin == origin)
    if cursor:
        moment, ident = decode_cursor(cursor)
        stmt = stmt.where(tuple_(Post.created_at, Post.id) < tuple_(moment, ident))
    rows = session.scalars(stmt.limit(limit + 1)).all()
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit and page else None
    return PostPage(items=[_post_read(session, row) for row in page], next_cursor=next_cursor)


@router.get("/posts/{post_id}", response_model=PostRead)
def get_post(post_id: str, session: Session = Depends(get_session)) -> PostRead:
    return _post_read(session, _post(session, post_id))


@router.patch("/posts/{post_id}", response_model=PostRead)
def edit_post(
    post_id: str,
    body: PostTextUpdate,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    post = update_post_text(session, _post(session, post_id), body.text, clock)
    return _post_read(session, post)


@router.post("/posts/{post_id}/approve", response_model=PostRead)
def approve(
    post_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    post = approve_post(session, _post(session, post_id), clock, settings)
    return _post_read(session, post)


@router.post("/posts/{post_id}/reject", response_model=PostRead)
def reject(
    post_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    return _post_read(session, reject_post(session, _post(session, post_id), clock))


@router.post("/posts/{post_id}/regenerate", response_model=PostRead, status_code=202)
def regenerate(
    post_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    post = regenerate_post(session, _post(session, post_id), clock, settings)
    return _post_read(session, post)


@router.post("/posts/{post_id}/retry", response_model=PostRead, status_code=202)
def retry(
    post_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    post = retry_publish(session, _post(session, post_id), clock, settings)
    return _post_read(session, post)


@router.post("/posts/{post_id}/cancel", response_model=PostRead)
def cancel(
    post_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> PostRead:
    return _post_read(session, cancel_post(session, _post(session, post_id), clock))


@router.get("/posts/{post_id}/attempts", response_model=list[AttemptRead])
def attempts(post_id: str, session: Session = Depends(get_session)) -> list[AttemptRead]:
    post = _post(session, post_id)
    rows = session.scalars(
        select(PostAttempt).where(PostAttempt.post_id == post.id).order_by(PostAttempt.started_at.desc())
    ).all()
    return [
        AttemptRead(
            id=row.id,
            kind=row.kind,
            started_at=row.started_at,
            finished_at=row.finished_at,
            outcome=row.outcome,
            error_message=row.error_message,
            http_status=row.http_status,
        )
        for row in rows
    ]


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    clock: Clock = Depends(get_clock),
) -> DashboardRead:
    now = clock.now()
    accounts = session.scalars(select(ThreadsAccount).order_by(ThreadsAccount.created_at.desc())).all()
    active = session.scalar(select(func.count()).select_from(Campaign).where(Campaign.status == "active")) or 0
    paused = session.scalar(select(func.count()).select_from(Campaign).where(Campaign.status == "paused")) or 0
    campaigns = session.scalars(select(Campaign).where(Campaign.status == "active")).all()
    upcoming: list[SlotRead] = []
    for campaign in campaigns:
        slots = upcoming_for(campaign, now, 1)
        if slots:
            upcoming.append(_slot(slots[0], campaign.timezone))
    upcoming.sort(key=lambda item: item.scheduled_for)
    errors = session.scalars(
        select(Post).where(Post.status.in_(["FAILED", "UNKNOWN"])).order_by(Post.updated_at.desc()).limit(5)
    ).all()
    skipped_rows = session.scalars(select(SkippedSlot).order_by(SkippedSlot.created_at.desc()).limit(5)).all()
    return DashboardRead(
        integration_mode=settings.integration_mode,
        auth_required=bool(settings.auth_token),
        public_deployment_ready=False,
        demo_banner=DEMO_BANNER if settings.integration_mode == "demo" else None,
        missed_slot_policy=MISSED_SLOT_POLICY,
        accounts=[AccountRead.model_validate(public_account_dict(row, now)) for row in accounts],
        active_campaigns=int(active),
        paused_campaigns=int(paused),
        upcoming=upcoming[:8],
        recent_errors=[_post_read(session, row) for row in errors],
        skipped=[_skipped(session, row) for row in skipped_rows],
    )


def _settings_row(session: Session, settings: Settings) -> AppSetting:
    row = session.get(AppSetting, 1)
    if row is None:
        row = AppSetting(id=1, temperature=settings.deepseek_temperature, max_tokens=settings.deepseek_max_tokens)
        session.add(row)
        session.flush()
    return row


def _settings_read(settings: Settings, row: AppSetting) -> SettingsRead:
    return SettingsRead(
        integration_mode=settings.integration_mode,
        auth_required=bool(settings.auth_token),
        demo_banner=DEMO_BANNER if settings.integration_mode == "demo" else None,
        missed_slot_policy=MISSED_SLOT_POLICY,
        unapproved_policy=UNAPPROVED_OVERDUE_POLICY,
        generation=GenerationSettings(
            temperature=row.temperature,
            max_tokens=row.max_tokens,
            prompt_version=PROMPT_VERSION,
            model=settings.deepseek_model if settings.integration_mode == "live" else "demo",
        ),
        deepseek=DeepSeekPublic(
            configured=bool(settings.deepseek_api_key),
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        ),
        threads=ThreadsPublic(
            configured=bool(settings.threads_app_id and settings.threads_app_secret),
            graph_base_url=settings.threads_graph_base_url,
            authorize_url=settings.threads_oauth_authorize_url,
            redirect_uri=settings.threads_redirect_uri,
            scopes=settings.threads_scope_list,
            text_limit=THREADS_TEXT_LIMIT,
        ),
    )


def _campaign(session: Session, campaign_id: str) -> Campaign:
    campaign = session.get(Campaign, _uuid(campaign_id, "campaign_id"))
    if campaign is None:
        raise ApiError(404, "not_found", "Кампания не найдена")
    return campaign


def _account(session: Session, account_id: str) -> ThreadsAccount:
    account = session.get(ThreadsAccount, _uuid(account_id, "account_id"))
    if account is None:
        raise ApiError(404, "not_found", "Аккаунт не найден")
    return account


def _post(session: Session, post_id: str) -> Post:
    post = session.get(Post, _uuid(post_id, "post_id"))
    if post is None:
        raise ApiError(404, "not_found", "Пост не найден")
    return post


def _uuid(value: str, field: str) -> object:
    from uuid import UUID

    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(422, "validation_error", "Некорректный идентификатор", {field: "Ожидается UUID"}) from exc


def _summary(campaign: Campaign, clock: Clock) -> CampaignSummary:
    slots = upcoming_for(campaign, clock.now(), 1)
    return CampaignSummary(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        publish_mode=campaign.publish_mode,
        timezone=campaign.timezone,
        topic=campaign.topic,
        account_id=campaign.account_id,
        next_slot=_slot(slots[0], campaign.timezone) if slots else None,
    )


def _campaign_read(session: Session, campaign: Campaign, clock: Clock) -> CampaignRead:
    skipped_rows = session.scalars(
        select(SkippedSlot).where(SkippedSlot.campaign_id == campaign.id).order_by(SkippedSlot.slot_at.desc()).limit(10)
    ).all()
    return CampaignRead(
        id=campaign.id,
        account_id=campaign.account_id,
        name=campaign.name,
        topic=campaign.topic,
        context=campaign.context,
        audience=campaign.audience,
        language=campaign.language,
        tone=campaign.tone,
        goal=campaign.goal,
        desired_length=campaign.desired_length,
        extra_instructions=campaign.extra_instructions,
        required_points=campaign.required_points,
        forbidden=campaign.forbidden,
        examples=campaign.examples,
        allow_emoji=campaign.allow_emoji,
        allow_hashtags=campaign.allow_hashtags,
        allow_links=campaign.allow_links,
        publish_mode=campaign.publish_mode,
        timezone=campaign.timezone,
        weekdays=list(campaign.weekdays),
        times_of_day=list(campaign.times_of_day),
        starts_on=campaign.starts_on,
        ends_on=campaign.ends_on,
        status=campaign.status,
        schedule_cursor=campaign.schedule_cursor,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        upcoming=[_slot(item, campaign.timezone) for item in upcoming_for(campaign, clock.now(), 5)],
        skipped=[_skipped(session, row) for row in skipped_rows],
        missed_slot_policy=MISSED_SLOT_POLICY,
    )


def _post_read(session: Session, post: Post) -> PostRead:
    campaign = session.get(Campaign, post.campaign_id)
    timezone = campaign.timezone if campaign is not None else "UTC"
    usage = post.usage if isinstance(post.usage, dict) else None
    safe_usage = {key: value for key, value in usage.items() if isinstance(value, int)} if usage else None
    return PostRead(
        id=post.id,
        campaign_id=post.campaign_id,
        account_id=post.account_id,
        campaign_name=campaign.name if campaign is not None else "",
        origin=post.origin,
        text=post.text,
        status=post.status,
        scheduled_for=post.scheduled_for,
        scheduled_local_time=_local(post.scheduled_for, timezone) if post.scheduled_for else None,
        timezone=timezone,
        published_at=post.published_at,
        generated_at=post.generated_at,
        approved_at=post.approved_at,
        model=post.model,
        prompt_version=post.prompt_version,
        usage=safe_usage,
        external_id=post.external_id,
        container_id=post.container_id,
        container_status=post.container_status,
        permalink=post.permalink,
        is_demo_publication=post.is_demo_publication,
        attempt_count=post.attempt_count,
        generation_count=post.generation_count,
        last_error=post.last_error,
        error_kind=post.error_kind,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _slot(moment: object, timezone: str) -> SlotRead:
    from datetime import datetime

    assert isinstance(moment, datetime)
    return SlotRead(scheduled_for=moment, local_time=_local(moment, timezone), timezone=timezone)


def _local(moment: object, timezone: str) -> str:
    from datetime import datetime

    assert isinstance(moment, datetime)
    local = moment.astimezone(ZoneInfo(timezone))
    return local.strftime("%Y-%m-%d %H:%M")


def _skipped(session: Session, row: SkippedSlot) -> SkippedSlotRead:
    campaign = session.get(Campaign, row.campaign_id)
    timezone = campaign.timezone if campaign is not None else "UTC"
    return SkippedSlotRead(
        slot_at=row.slot_at,
        local_time=_local(row.slot_at, timezone),
        reason=row.reason,
        reason_label="Пропущен: вне окна допуска, пачкой не публикуется",
    )
