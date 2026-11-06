import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.content.prompt import build_prompt
from acwa.content.validate import validate_post_text
from acwa.domain.status import (
    CampaignStatus,
    JobKind,
    PostOrigin,
    PostStatus,
    PublishMode,
)
from acwa.errors import ApiError
from acwa.integrations.deepseek import ContentGenerator
from acwa.integrations.threads import ThreadsGateway
from acwa.integrations.types import (
    AmbiguousPublishError,
    ErrorKind,
    IntegrationError,
    Postpone,
    campaign_snapshot,
    should_refresh_token,
    token_is_expired,
)
from acwa.models import AppSetting, Campaign, Post, PostAttempt, ThreadsAccount
from acwa.security.crypto import TokenCipher
from acwa.security.redact import redact
from acwa.services.jobs import cancel_open_jobs, enqueue_job

SAFE_REPUBLISH_MESSAGE = (
    "Запрос публикации уже отправлялся, а Threads не подтвердил новый пост. "
    "Автоматический повтор остановлен. Если публикации в Threads нет, подтвердите повтор: "
    "будет отправлен тот же текст и, если он есть, тот же контейнер."
)


def request_trial(session: Session, campaign: Campaign, clock: Clock, settings: Settings) -> Post:
    if campaign.status == CampaignStatus.ARCHIVED:
        raise ApiError(409, "archived", "Архивную кампанию нельзя использовать для генерации")
    now = clock.now()
    post = Post(
        campaign_id=campaign.id,
        account_id=campaign.account_id,
        origin=PostOrigin.TRIAL,
        status=PostStatus.GENERATING,
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
    return post


def approve_post(session: Session, post: Post, clock: Clock, settings: Settings) -> Post:
    if post.status != PostStatus.PENDING_APPROVAL:
        raise ApiError(409, "invalid_state", "Одобрить можно только пост, который ждёт проверки")
    if not post.text:
        raise ApiError(409, "empty_text", "У поста нет текста")
    errors = _errors_for_post(session, post, post.text)
    if errors:
        raise ApiError(422, "validation_error", errors[0], {"text": errors[0]})
    now = clock.now()
    post.approved_at = now
    run_at = post.scheduled_for if post.scheduled_for and post.scheduled_for > now else now
    if post.scheduled_for is None:
        post.scheduled_for = now
    post.status = PostStatus.SCHEDULED
    post.last_error = None
    post.updated_at = now
    enqueue_job(
        session,
        post_id=post.id,
        kind=JobKind.PUBLISH,
        run_at=run_at,
        max_attempts=settings.max_publish_attempts,
    )
    return post


def reject_post(session: Session, post: Post, clock: Clock) -> Post:
    if post.status != PostStatus.PENDING_APPROVAL:
        raise ApiError(409, "invalid_state", "Отклонить можно только пост, который ждёт проверки")
    now = clock.now()
    post.status = PostStatus.CANCELLED
    post.last_error = "Отклонено вручную"
    post.updated_at = now
    cancel_open_jobs(session, post.id, now)
    return post


def update_post_text(session: Session, post: Post, text: str, clock: Clock) -> Post:
    if post.status not in {
        PostStatus.DRAFT,
        PostStatus.PENDING_APPROVAL,
        PostStatus.SCHEDULED,
        PostStatus.FAILED,
    }:
        raise ApiError(409, "invalid_state", "Этот пост уже нельзя редактировать")
    if post.publish_dispatched_at is not None:
        raise ApiError(409, "already_sent", "Запрос публикации уже отправлялся, текст менять нельзя")
    errors = _errors_for_post(session, post, text)
    if errors:
        raise ApiError(422, "validation_error", "Текст не проходит ограничения", {"text": " ".join(errors)})
    now = clock.now()
    post.text = text.strip()
    post.updated_at = now
    if post.status == PostStatus.FAILED:
        post.status = PostStatus.PENDING_APPROVAL
        post.last_error = None
        post.generation_error = None
    return post


def regenerate_post(session: Session, post: Post, clock: Clock, settings: Settings) -> Post:
    if post.status in {PostStatus.PUBLISHED, PostStatus.PUBLISHING, PostStatus.CANCELLED, PostStatus.UNKNOWN}:
        raise ApiError(409, "invalid_state", "Этот пост нельзя перегенерировать")
    if post.publish_dispatched_at is not None:
        raise ApiError(409, "already_sent", "Публикация уже запрашивалась. Новый текст сам не отправится.")
    now = clock.now()
    cancel_open_jobs(session, post.id, now)
    post.status = PostStatus.GENERATING
    post.generation_error = None
    post.last_error = None
    post.updated_at = now
    enqueue_job(
        session,
        post_id=post.id,
        kind=JobKind.GENERATE,
        run_at=now,
        max_attempts=settings.max_generate_attempts,
    )
    return post


def retry_publish(session: Session, post: Post, clock: Clock, settings: Settings) -> Post:
    if post.status not in {PostStatus.FAILED, PostStatus.UNKNOWN}:
        raise ApiError(409, "invalid_state", "Повторить публикацию можно для ошибки или неясного результата")
    if not post.text:
        raise ApiError(
            409,
            "needs_generation",
            "Повтор публикации не создаёт новый текст. Сначала сгенерируйте пост.",
        )
    if post.container_id is None and post.publish_dispatched_at is None and post.generation_error:
        raise ApiError(
            409,
            "needs_generation",
            "Ошибка произошла при генерации. Повтор публикации не вызывает модель заново.",
        )
    errors = _errors_for_post(session, post, post.text)
    if errors:
        raise ApiError(422, "validation_error", errors[0], {"text": errors[0]})
    now = clock.now()
    post.allow_republish = True
    post.status = PostStatus.SCHEDULED
    post.last_error = None
    post.updated_at = now
    enqueue_job(
        session,
        post_id=post.id,
        kind=JobKind.PUBLISH,
        run_at=now,
        max_attempts=settings.max_publish_attempts,
    )
    return post


def cancel_post(session: Session, post: Post, clock: Clock) -> Post:
    if post.status in {PostStatus.PUBLISHED, PostStatus.PUBLISHING}:
        raise ApiError(409, "invalid_state", "Уже отправляемый или опубликованный пост нельзя отменить")
    now = clock.now()
    post.status = PostStatus.CANCELLED
    post.updated_at = now
    cancel_open_jobs(session, post.id, now)
    return post


def run_generation(
    session: Session,
    post_id: uuid.UUID,
    *,
    generator: ContentGenerator,
    clock: Clock,
    settings: Settings,
) -> None:
    post = session.get(Post, post_id)
    if post is None or post.status == PostStatus.CANCELLED:
        return
    campaign = session.get(Campaign, post.campaign_id)
    if campaign is None:
        return
    if post.origin == PostOrigin.SCHEDULE and campaign.status != CampaignStatus.ACTIVE:
        post.status = PostStatus.CANCELLED
        post.last_error = "Кампания неактивна, слот не будет опубликован"
        post.updated_at = clock.now()
        session.commit()
        return
    post.generation_count += 1
    variation = post.generation_count
    snapshot = campaign_snapshot(campaign)
    history = _recent_texts(session, campaign.id, settings.recent_posts_in_prompt)
    app_settings = _app_settings(session, settings)
    prompt = build_prompt(
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
        recent_posts=history,
        temperature=app_settings.temperature,
        max_tokens=app_settings.max_tokens,
        variation=variation,
    )
    flags = (campaign.allow_emoji, campaign.allow_hashtags, campaign.allow_links, campaign.forbidden)
    mode = campaign.publish_mode
    origin = post.origin
    scheduled_for = post.scheduled_for
    session.commit()
    started = clock.now()
    try:
        result = generator.generate(prompt)
    except IntegrationError as exc:
        post = session.get(Post, post_id)
        if post is None:
            raise
        post.generation_error = redact(exc.message)
        post.last_error = post.generation_error
        post.error_kind = exc.kind
        post.updated_at = clock.now()
        _attempt(session, post.id, "generate", started, clock.now(), "failed", post.last_error, None)
        if exc.kind in {ErrorKind.PERMANENT, ErrorKind.AUTH}:
            post.status = PostStatus.FAILED
        session.commit()
        raise
    post = session.get(Post, post_id)
    if post is None:
        return
    text = str(result.text).strip()
    post.text = text
    post.model = result.model
    post.prompt_version = prompt.version
    post.settings_snapshot = snapshot
    post.usage = {key: value for key, value in result.usage.items()} if result.usage else None
    post.generated_at = clock.now()
    post.updated_at = clock.now()
    errors = validate_post_text(
        text,
        allow_emoji=flags[0],
        allow_hashtags=flags[1],
        allow_links=flags[2],
        forbidden=flags[3],
    )
    if errors:
        post.status = PostStatus.FAILED
        post.generation_error = " ".join(errors)
        post.last_error = post.generation_error
        post.error_kind = ErrorKind.PERMANENT
        _attempt(session, post.id, "generate", started, clock.now(), "failed", post.last_error, None)
        session.commit()
        return
    _attempt(session, post.id, "generate", started, clock.now(), "success", None, None)
    if origin == PostOrigin.TRIAL or mode == PublishMode.MANUAL:
        post.status = PostStatus.PENDING_APPROVAL
    else:
        post.status = PostStatus.SCHEDULED
        enqueue_job(
            session,
            post_id=post.id,
            kind=JobKind.PUBLISH,
            run_at=scheduled_for or clock.now(),
            max_attempts=settings.max_publish_attempts,
        )
    session.commit()


def run_publish(
    session: Session,
    post_id: uuid.UUID,
    *,
    threads: ThreadsGateway,
    cipher: TokenCipher,
    clock: Clock,
    settings: Settings,
) -> None:
    post = session.get(Post, post_id)
    if post is None or post.status in {PostStatus.CANCELLED, PostStatus.PUBLISHED}:
        return
    campaign = session.get(Campaign, post.campaign_id)
    account = session.get(ThreadsAccount, post.account_id)
    if campaign is None or account is None or not post.text:
        return
    now = clock.now()
    if (
        post.origin == PostOrigin.SCHEDULE
        and campaign.publish_mode == PublishMode.AUTOMATIC
        and campaign.status != CampaignStatus.ACTIVE
        and post.approved_at is None
    ):
        post.status = PostStatus.CANCELLED
        post.last_error = "Кампания на паузе, автоматическая публикация отменена"
        post.updated_at = now
        session.commit()
        return
    if _requires_approval(post, campaign) and post.approved_at is None:
        post.status = PostStatus.PENDING_APPROVAL
        post.last_error = "Публикация ждёт одобрения и не отправлена"
        post.updated_at = now
        session.commit()
        return
    if settings.integration_mode == "live" and account.is_demo:
        post.status = PostStatus.FAILED
        post.last_error = "Демонстрационный аккаунт нельзя использовать для настоящей публикации"
        post.error_kind = ErrorKind.PERMANENT
        session.commit()
        return
    if post.external_id:
        _mark_published(post, now, post.permalink, post.is_demo_publication)
        session.commit()
        return
    if account.status != "connected":
        post.status = PostStatus.FAILED
        post.error_kind = ErrorKind.AUTH
        post.last_error = "Аккаунт Threads не подключён. Публикация остановлена."
        post.updated_at = now
        session.commit()
        return
    try:
        token = _token(session, account, threads, cipher, clock)
    except IntegrationError as exc:
        post.status = PostStatus.FAILED
        post.error_kind = exc.kind
        post.last_error = redact(exc.message)
        if exc.kind == ErrorKind.AUTH:
            account.status = "needs_reauth"
            account.last_error = post.last_error
        session.commit()
        if exc.kind == ErrorKind.AUTH:
            return
        raise

    if post.container_id:
        try:
            info = threads.get_container(post.container_id, token)
        except IntegrationError:
            session.commit()
            raise
        post.container_status = info.status
        if info.status == "PUBLISHED":
            _match_published(post, threads, account, token, clock)
            session.commit()
            return
        if info.status in {"ERROR", "EXPIRED"}:
            post.status = PostStatus.FAILED
            post.error_kind = ErrorKind.PERMANENT
            post.last_error = info.error_message or f"Контейнер Threads в состоянии {info.status}"
            session.commit()
            return
        if info.status == "IN_PROGRESS":
            session.commit()
            raise Postpone(
                timedelta(seconds=settings.container_wait_seconds),
                "Контейнер Threads ещё обрабатывается",
            )
        if info.status == "FINISHED" and post.publish_dispatched_at and not post.allow_republish:
            post.status = PostStatus.UNKNOWN
            post.error_kind = ErrorKind.AMBIGUOUS
            post.last_error = SAFE_REPUBLISH_MESSAGE
            session.commit()
            return
    else:
        _ensure_quota(threads, account, token)
        post.status = PostStatus.PUBLISHING
        post.updated_at = clock.now()
        session.commit()
        container_id = threads.create_text_container(account.threads_user_id or "", token, post.text)
        post = _reload(session, post_id)
        post.container_id = container_id
        post.container_status = "FINISHED"
        session.commit()

    post = _reload(session, post_id)
    account = session.get(ThreadsAccount, post.account_id)
    if account is None or post.container_id is None or post.text is None:
        return
    token = _token(session, account, threads, cipher, clock)
    post.status = PostStatus.PUBLISHING
    post.publish_dispatched_at = clock.now()
    post.allow_republish = False
    post.attempt_count += 1
    post.updated_at = clock.now()
    session.commit()
    started = clock.now()
    try:
        result = threads.publish_container(account.threads_user_id or "", token, post.container_id)
    except AmbiguousPublishError as exc:
        post = _reload(session, post_id)
        post.status = PostStatus.UNKNOWN
        post.error_kind = ErrorKind.AMBIGUOUS
        post.last_error = redact(str(exc))
        _attempt(session, post.id, "publish", started, clock.now(), "ambiguous", post.last_error, None)
        enqueue_job(
            session,
            post_id=post.id,
            kind=JobKind.RECONCILE,
            run_at=clock.now() + timedelta(seconds=settings.container_wait_seconds),
            max_attempts=settings.max_publish_attempts,
        )
        session.commit()
        return
    except IntegrationError as exc:
        post = _reload(session, post_id)
        account = session.get(ThreadsAccount, post.account_id)
        message = redact(exc.message)
        _attempt(session, post.id, "publish", started, clock.now(), "failed", message, exc.http_status)
        post.last_error = message
        post.error_kind = exc.kind
        post.updated_at = clock.now()
        if exc.kind == ErrorKind.AUTH and account is not None:
            account.status = "needs_reauth"
            account.last_error = message
            post.status = PostStatus.FAILED
            session.commit()
            return
        if exc.kind == ErrorKind.RATE_LIMIT:
            # A definite rate-limit response means the publish did not happen.
            post.publish_dispatched_at = None
            post.status = PostStatus.SCHEDULED
            session.commit()
            raise
        if exc.kind == ErrorKind.PERMANENT:
            post.status = PostStatus.FAILED
            session.commit()
            return
        post.status = PostStatus.UNKNOWN if post.publish_dispatched_at else PostStatus.SCHEDULED
        session.commit()
        if post.status == PostStatus.UNKNOWN:
            return
        raise
    post = _reload(session, post_id)
    post.external_id = result.media_id
    post.permalink = result.permalink
    post.is_demo_publication = result.is_demo
    post.container_status = "PUBLISHED"
    _mark_published(post, clock.now(), result.permalink, result.is_demo)
    _attempt(session, post.id, "publish", started, clock.now(), "success", None, None)
    session.commit()


def _requires_approval(post: Post, campaign: Campaign) -> bool:
    return post.origin == PostOrigin.TRIAL or campaign.publish_mode == PublishMode.MANUAL


def _mark_published(post: Post, now: datetime, permalink: str | None, demo: bool) -> None:
    post.status = PostStatus.PUBLISHED
    post.published_at = post.published_at or now
    post.permalink = permalink
    post.is_demo_publication = demo
    post.last_error = None
    post.error_kind = None
    post.updated_at = now


def _match_published(
    post: Post,
    threads: ThreadsGateway,
    account: ThreadsAccount,
    token: str,
    clock: Clock,
) -> None:
    if account.threads_user_id is None or post.text is None:
        post.status = PostStatus.UNKNOWN
        post.last_error = SAFE_REPUBLISH_MESSAGE
        return
    recent = threads.list_recent_posts(account.threads_user_id, token)
    floor = None
    if post.publish_dispatched_at is not None:
        floor = post.publish_dispatched_at.astimezone(UTC) - timedelta(minutes=5)
    for item in recent:
        if item.text != post.text:
            continue
        if floor is not None and item.timestamp is not None and item.timestamp < floor:
            continue
        post.external_id = item.media_id
        post.permalink = item.permalink
        post.is_demo_publication = item.media_id.startswith("demo:")
        _mark_published(post, clock.now(), item.permalink, post.is_demo_publication)
        return
    post.status = PostStatus.UNKNOWN
    post.error_kind = ErrorKind.AMBIGUOUS
    post.last_error = (
        "Threads сообщает, что контейнер уже опубликован, но пост не удалось сопоставить. "
        "Повторная отправка заблокирована, чтобы не создать дубликат."
    )


def _ensure_quota(threads: ThreadsGateway, account: ThreadsAccount, token: str) -> None:
    if account.threads_user_id is None:
        return
    try:
        limit = threads.publishing_limit(account.threads_user_id, token)
    except IntegrationError as exc:
        if exc.kind in {ErrorKind.AUTH, ErrorKind.RATE_LIMIT}:
            raise
        return
    if limit.quota_usage >= limit.quota_total:
        raise IntegrationError(
            ErrorKind.RATE_LIMIT,
            "Достигнут лимит публикаций Threads за текущее окно (250 постов за 24 часа).",
            retry_after=timedelta(seconds=max(limit.quota_duration, 60)),
        )


def _token(
    session: Session,
    account: ThreadsAccount,
    threads: ThreadsGateway,
    cipher: TokenCipher,
    clock: Clock,
) -> str:
    if account.is_demo:
        return "demo"
    if account.token_ciphertext is None:
        raise IntegrationError(ErrorKind.AUTH, "Токен Threads не сохранён. Подключите аккаунт заново.")
    token = cipher.decrypt(account.token_ciphertext)
    now = clock.now()
    if token_is_expired(expires_at=account.token_expires_at, now=now):
        account.status = "needs_reauth"
        account.last_error = "Срок действия токена Threads истёк. Подключите аккаунт заново."
        raise IntegrationError(ErrorKind.AUTH, account.last_error)
    if (
        account.token_obtained_at is not None
        and account.token_expires_at is not None
        and should_refresh_token(
            obtained_at=account.token_obtained_at,
            expires_at=account.token_expires_at,
            now=now,
        )
    ):
        refreshed = threads.refresh_long_lived(token)
        token = refreshed.access_token
        account.token_ciphertext = cipher.encrypt(token)
        account.token_obtained_at = now
        if refreshed.expires_in is not None:
            account.token_expires_at = now + timedelta(seconds=refreshed.expires_in)
        account.updated_at = now
        session.commit()
    return token


def _recent_texts(session: Session, campaign_id: uuid.UUID, limit: int) -> list[str]:
    rows = session.scalars(
        select(Post.text)
        .where(
            Post.campaign_id == campaign_id,
            Post.status == PostStatus.PUBLISHED,
            Post.text.is_not(None),
        )
        .order_by(Post.published_at.desc())
        .limit(limit)
    ).all()
    return [row for row in rows if isinstance(row, str)]


def _app_settings(session: Session, settings: Settings) -> AppSetting:
    row = session.get(AppSetting, 1)
    if row is None:
        row = AppSetting(
            id=1,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )
        session.add(row)
        session.flush()
    return row


def _errors_for_post(session: Session, post: Post, text: str) -> list[str]:
    campaign = session.get(Campaign, post.campaign_id)
    if campaign is None:
        return ["Кампания не найдена"]
    snapshot = post.settings_snapshot or {}
    return validate_post_text(
        text,
        allow_emoji=bool(snapshot.get("allow_emoji", campaign.allow_emoji)),
        allow_hashtags=bool(snapshot.get("allow_hashtags", campaign.allow_hashtags)),
        allow_links=bool(snapshot.get("allow_links", campaign.allow_links)),
        forbidden=str(snapshot.get("forbidden", campaign.forbidden)),
    )


def _attempt(
    session: Session,
    post_id: uuid.UUID,
    kind: str,
    started: datetime,
    finished: datetime,
    outcome: str,
    error_message: str | None,
    http_status: int | None,
) -> None:
    session.add(
        PostAttempt(
            post_id=post_id,
            kind=kind,
            started_at=started,
            finished_at=finished,
            outcome=outcome,
            error_message=error_message,
            http_status=http_status,
        )
    )


def _reload(session: Session, post_id: uuid.UUID) -> Post:
    post = session.get(Post, post_id)
    if post is None:
        raise ApiError(404, "not_found", "Пост не найден")
    return post
