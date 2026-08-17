import datetime
import hashlib
import re
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from core.config import (
    AUTH_LOCKOUT_MINUTES,
    AUTH_MAX_FAILED_LOGINS,
    AUTH_MAX_SESSIONS_PER_USER,
    AUTH_SESSION_HOURS,
)
from database import UserAccount, UserSession
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

# OWASP's Argon2id baseline: 19 MiB memory, two iterations, one lane.
PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("invalid-password-for-timing-only")


class InvalidCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class SessionCredentials:
    token: str
    csrf_token: str
    expires_at: datetime.datetime


@dataclass(frozen=True)
class AuthenticatedContext:
    user: UserAccount
    session: UserSession


def utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Username must contain 3-64 lowercase Latin letters, digits, '.', '_' or '-'"
        )
    return normalized


def validate_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must contain at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must contain no more than {PASSWORD_MAX_LENGTH} characters")


def hash_password(password: str) -> str:
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


class AuthService:
    @staticmethod
    async def authenticate(
        username: str,
        password: str,
        user_agent: str | None,
        db: AsyncSession,
    ) -> tuple[UserAccount, SessionCredentials]:
        normalized = normalize_username(username)
        result = await db.execute(
            select(UserAccount)
            .where(UserAccount.username == normalized)
            .with_for_update()
        )
        user = result.scalar_one_or_none()

        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError

        now = utcnow()
        password_matches = verify_password(password, user.password_hash)
        account_locked = bool(user.locked_until and user.locked_until > now)

        if not user.is_active or account_locked or not password_matches:
            if user.is_active and not account_locked and not password_matches:
                user.failed_login_count += 1
                if user.failed_login_count >= AUTH_MAX_FAILED_LOGINS:
                    user.locked_until = now + datetime.timedelta(
                        minutes=AUTH_LOCKOUT_MINUTES
                    )
                await db.commit()
            raise InvalidCredentialsError

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if PASSWORD_HASHER.check_needs_rehash(user.password_hash):
            user.password_hash = PASSWORD_HASHER.hash(password)

        await db.execute(delete(UserSession).where(UserSession.expires_at <= now))

        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = now + datetime.timedelta(hours=AUTH_SESSION_HOURS)
        session = UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            csrf_token=csrf_token,
            user_agent_hash=hash_user_agent(user_agent),
            created_at=now,
            last_seen_at=now,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()

        active_sessions = await db.execute(
            select(UserSession)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at.desc(), UserSession.id.desc())
        )
        for obsolete_session in list(active_sessions.scalars())[AUTH_MAX_SESSIONS_PER_USER:]:
            await db.delete(obsolete_session)

        await db.commit()
        return user, SessionCredentials(
            token=token,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    @staticmethod
    async def load_session(
        token: str | None,
        db: AsyncSession,
    ) -> AuthenticatedContext | None:
        if not token or len(token) > 256:
            return None

        result = await db.execute(
            select(UserSession, UserAccount)
            .join(UserAccount, UserAccount.id == UserSession.user_id)
            .where(UserSession.token_hash == hash_session_token(token))
        )
        row = result.one_or_none()
        if row is None:
            return None

        session, user = row
        now = utcnow()
        invalid = (
            session.expires_at <= now
            or not user.is_active
            or session.created_at < user.password_changed_at
        )
        if invalid:
            await db.delete(session)
            await db.commit()
            return None

        return AuthenticatedContext(user=user, session=session)

    @staticmethod
    async def logout(session: UserSession, db: AsyncSession) -> None:
        await db.delete(session)
        await db.commit()

    @staticmethod
    async def invalidate_user_sessions(user_id: int, db: AsyncSession) -> None:
        await db.execute(delete(UserSession).where(UserSession.user_id == user_id))
        await db.commit()
