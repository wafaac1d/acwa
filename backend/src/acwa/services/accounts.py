import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.errors import ApiError
from acwa.integrations.threads import ThreadsGateway
from acwa.integrations.types import ErrorKind, IntegrationError
from acwa.models import Campaign, OAuthState, ThreadsAccount
from acwa.security.crypto import TokenCipher
from acwa.services.planner import pause_campaign


def connect_demo(session: Session, cipher: TokenCipher, clock: Clock, settings: Settings) -> ThreadsAccount:
    if settings.integration_mode != "demo":
        raise ApiError(
            409,
            "live_mode",
            "Демонстрательный аккаунт доступен только в режиме demo.",
        )
    existing = session.scalar(
        select(ThreadsAccount).where(
            ThreadsAccount.is_demo.is_(True),
            ThreadsAccount.status == "connected",
        )
    )
    if existing is not None:
        return existing
    now = clock.now()
    account = ThreadsAccount(
        threads_user_id="demo",
        username="demo_account",
        display_name="Демонстрационный аккаунт",
        status="connected",
        is_demo=True,
        token_ciphertext=cipher.encrypt("demo-not-a-real-token"),
        scopes="demo",
        connected_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    session.flush()
    return account


def start_oauth(session: Session, clock: Clock, settings: Settings) -> str:
    if settings.integration_mode != "live":
        raise ApiError(
            409,
            "demo_mode",
            "В демонстрационном режиме OAuth Threads выключен. Подключите демонстрационный аккаунт.",
        )
    if not settings.threads_app_id or not settings.threads_app_secret:
        raise ApiError(
            503,
            "threads_not_configured",
            "Задайте ACWA_THREADS_APP_ID, ACWA_THREADS_APP_SECRET и redirect URI в кабинете Meta.",
        )
    now = clock.now()
    state = secrets.token_urlsafe(32)
    session.add(OAuthState(state=state, expires_at=now + timedelta(minutes=15)))
    query = urlencode(
        {
            "client_id": settings.threads_app_id,
            "redirect_uri": settings.threads_redirect_uri,
            "scope": ",".join(settings.threads_scope_list),
            "response_type": "code",
            "state": state,
        }
    )
    return f"{settings.threads_oauth_authorize_url}?{query}"


def complete_oauth(
    session: Session,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    clock: Clock,
    settings: Settings,
    threads: ThreadsGateway,
    cipher: TokenCipher,
) -> str:
    frontend = settings.frontend_origin.rstrip("/")
    if error:
        return f"{frontend}/settings?error=access_denied"
    if not code or not state:
        return f"{frontend}/settings?error=missing_code"
    row = session.get(OAuthState, state)
    now = clock.now()
    if row is None or row.used_at is not None or row.expires_at < now:
        return f"{frontend}/settings?error=state"
    row.used_at = now
    try:
        short = threads.exchange_code(code, settings.threads_redirect_uri)
        if short.user_id is None:
            raise IntegrationError(ErrorKind.PERMANENT, "Threads не вернул пользователя")
        long = threads.exchange_long_lived(short.access_token)
        profile = threads.get_profile(short.user_id, long.access_token)
    except IntegrationError:
        session.commit()
        return f"{frontend}/settings?error=oauth"
    account = session.scalar(select(ThreadsAccount).where(ThreadsAccount.threads_user_id == profile.user_id))
    expires_at = now + timedelta(seconds=long.expires_in or 5_183_944)
    if account is None:
        account = ThreadsAccount(threads_user_id=profile.user_id, created_at=now)
        session.add(account)
    account.username = profile.username
    account.display_name = profile.name
    account.profile_picture_url = profile.profile_picture_url
    account.status = "connected"
    account.is_demo = False
    account.token_ciphertext = cipher.encrypt(long.access_token)
    account.token_obtained_at = now
    account.token_expires_at = expires_at
    account.scopes = settings.threads_scopes
    account.connected_at = now
    account.last_error = None
    account.updated_at = now
    return f"{frontend}/settings?connected=1"


def disconnect_account(session: Session, account: ThreadsAccount, clock: Clock) -> ThreadsAccount:
    now = clock.now()
    account.status = "disconnected"
    account.token_ciphertext = None
    account.token_expires_at = None
    account.token_obtained_at = None
    account.updated_at = now
    campaigns = session.scalars(
        select(Campaign).where(
            Campaign.account_id == account.id,
            Campaign.status == "active",
        )
    ).all()
    for campaign in campaigns:
        pause_campaign(session, campaign, now)
    return account


def reauth_message(account: ThreadsAccount, now: datetime) -> str | None:
    if account.status == "needs_reauth":
        return account.last_error or "Нужно заново авторизовать Threads."
    if account.status == "disconnected":
        return "Аккаунт отключён. Публикации не отправляются."
    if not account.is_demo and account.token_expires_at is not None and account.token_expires_at <= now:
        return "Срок действия токена Threads истёк. Подключите аккаунт заново."
    return None


def assert_account_usable(account: ThreadsAccount) -> None:
    if account.status != "connected":
        raise ApiError(409, "account_unavailable", "Выбранный аккаунт Threads не подключён")


def public_account_dict(account: ThreadsAccount, now: datetime) -> dict[str, object]:
    return {
        "id": account.id,
        "threads_user_id": account.threads_user_id,
        "username": account.username,
        "display_name": account.display_name,
        "profile_picture_url": account.profile_picture_url,
        "status": account.status,
        "token_expires_at": account.token_expires_at,
        "is_demo": account.is_demo,
        "connected_at": account.connected_at,
        "reauth_message": reauth_message(account, now),
    }
