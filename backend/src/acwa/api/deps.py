import base64
import secrets
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from acwa.clock import Clock
from acwa.config import Settings
from acwa.errors import ApiError
from acwa.security.crypto import TokenCipher


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_cipher(request: Request) -> TokenCipher:
    return request.app.state.cipher


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def password_is_valid(authorization: str | None, expected: str | None) -> bool:
    secret = expected or ""
    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization.split(" ", 1)[1]
    if len(secret) < 12 or len(presented) != len(secret):
        return False
    return secrets.compare_digest(presented, secret)


def require_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    if request.url.path in {"/api/health", "/api/accounts/threads/callback"}:
        return
    if not password_is_valid(authorization, request.app.state.settings.auth_token):
        raise ApiError(401, "unauthorized", "Нужен пароль приложения")


def encode_cursor(moment: datetime, ident: UUID) -> str:
    raw = f"{moment.isoformat()}|{ident}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        moment_raw, ident_raw = raw.split("|", 1)
        moment = datetime.fromisoformat(moment_raw)
        if moment.tzinfo is None:
            raise ValueError
        return moment, UUID(ident_raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(400, "bad_cursor", "Некорректный курсор списка") from exc


SessionDep = Depends(get_session)
SettingsDep = Depends(get_settings)
ClockDep = Depends(get_clock)
CipherDep = Depends(get_cipher)
