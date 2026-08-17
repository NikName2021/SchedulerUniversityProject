import datetime

import pytest
from core.constants import AUTH_COOKIE_NAME, AUTH_MAX_FAILED_LOGINS
from database import UserAccount, UserSession
from httpx import AsyncClient
from services.auth_service import hash_password, hash_session_token, verify_password
from sqlalchemy import select


def test_passwords_use_salted_argon2id_hashes() -> None:
    first = hash_password("CorrectPassword123!")
    second = hash_password("CorrectPassword123!")

    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password("CorrectPassword123!", first)
    assert not verify_password("WrongPassword123!", first)


@pytest.mark.asyncio
async def test_protected_api_requires_authentication(
    unauthenticated_api_client: AsyncClient,
) -> None:
    protected = await unauthenticated_api_client.get("/api/v1/scheduler/stats")
    health = await unauthenticated_api_client.get("/health/live")

    assert protected.status_code == 401
    assert protected.json() == {"detail": "Authentication required"}
    assert health.status_code == 200


@pytest.mark.asyncio
async def test_login_failure_is_generic_for_known_and_unknown_users(
    unauthenticated_api_client: AsyncClient,
    test_user: UserAccount,
) -> None:
    known = await unauthenticated_api_client.post(
        "/api/v1/auth/login",
        json={"username": test_user.username, "password": "WrongPassword123!"},
    )
    unknown = await unauthenticated_api_client.post(
        "/api/v1/auth/login",
        json={"username": "not-found", "password": "WrongPassword123!"},
    )

    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json() == {
        "detail": "Invalid username or password"
    }
    assert known.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_login_restores_session_and_stores_only_token_hash(
    unauthenticated_api_client: AsyncClient,
    test_user: UserAccount,
    db_session,
) -> None:
    login = await unauthenticated_api_client.post(
        "/api/v1/auth/login",
        json={
            "username": "  TESTADMIN  ",
            "password": "CorrectPassword123!",
        },
    )

    assert login.status_code == 200
    assert login.json()["user"] == {
        "id": test_user.id,
        "username": "testadmin",
        "display_name": "Test Administrator",
        "role": "admin",
    }
    assert len(login.json()["csrf_token"]) >= 32
    set_cookie = login.headers["set-cookie"]
    assert f"{AUTH_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie

    session = (await db_session.execute(select(UserSession))).scalar_one()
    cookie_token = unauthenticated_api_client.cookies.get(AUTH_COOKIE_NAME)
    assert cookie_token is not None
    assert session.token_hash == hash_session_token(cookie_token)
    assert session.token_hash != cookie_token

    current = await unauthenticated_api_client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["user"]["username"] == "testadmin"
    assert current.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_csrf_is_required_and_logout_revokes_session(
    unauthenticated_api_client: AsyncClient,
    test_user: UserAccount,
) -> None:
    login = await unauthenticated_api_client.post(
        "/api/v1/auth/login",
        json={
            "username": test_user.username,
            "password": "CorrectPassword123!",
        },
    )
    csrf_token = login.json()["csrf_token"]

    missing_csrf = await unauthenticated_api_client.post(
        "/api/v1/reference/departments",
        json={"code": "TEST", "name": "Test Department"},
    )
    assert missing_csrf.status_code == 403

    accepted = await unauthenticated_api_client.post(
        "/api/v1/reference/departments",
        headers={"X-CSRF-Token": csrf_token},
        json={"code": "TEST", "name": "Test Department"},
    )
    assert accepted.status_code == 201

    logout = await unauthenticated_api_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout.status_code == 204
    assert AUTH_COOKIE_NAME not in unauthenticated_api_client.cookies
    assert (await unauthenticated_api_client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_expired_session_is_rejected_and_removed(
    unauthenticated_api_client: AsyncClient,
    test_user: UserAccount,
    db_session,
) -> None:
    token = "expired-session"
    now = datetime.datetime.utcnow()
    db_session.add(
        UserSession(
            user_id=test_user.id,
            token_hash=hash_session_token(token),
            csrf_token="expired-csrf",
            created_at=now - datetime.timedelta(hours=2),
            last_seen_at=now - datetime.timedelta(hours=2),
            expires_at=now - datetime.timedelta(hours=1),
        )
    )
    await db_session.commit()
    unauthenticated_api_client.cookies.set(AUTH_COOKIE_NAME, token)

    response = await unauthenticated_api_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    sessions = list((await db_session.execute(select(UserSession))).scalars())
    assert sessions == []


@pytest.mark.asyncio
async def test_repeated_failures_temporarily_lock_account(
    unauthenticated_api_client: AsyncClient,
    test_user: UserAccount,
    db_session,
) -> None:
    user_id = test_user.id
    for _ in range(AUTH_MAX_FAILED_LOGINS):
        response = await unauthenticated_api_client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user.username,
                "password": "WrongPassword123!",
            },
        )
        assert response.status_code == 401

    db_session.expire_all()
    locked_user = await db_session.get(UserAccount, user_id)
    assert locked_user is not None
    assert locked_user.locked_until is not None
    assert locked_user.failed_login_count == AUTH_MAX_FAILED_LOGINS

    correct_while_locked = await unauthenticated_api_client.post(
        "/api/v1/auth/login",
        json={
            "username": test_user.username,
            "password": "CorrectPassword123!",
        },
    )
    assert correct_while_locked.status_code == 401
