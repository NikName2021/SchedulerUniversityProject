import json
import stat

import pytest
from database import UserAccount
from services.auth_service import verify_password
from services.default_users_service import bootstrap_default_users, load_default_users
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from create_env import ensure_default_users_file


def _write_users_file(path, users: list[dict]) -> None:
    path.write_text(
        json.dumps({"version": 1, "users": users}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_default_user_secret_generator_is_private_and_idempotent(tmp_path) -> None:
    source = tmp_path / "secrets" / "default_users.json"

    assert ensure_default_users_file(source) is True
    original = source.read_bytes()
    definition = load_default_users(source)

    assert [user.username for user in definition.users] == ["admin", "operator"]
    assert all(
        len(user.password.get_secret_value()) == 24 for user in definition.users
    )
    assert stat.S_IMODE(source.stat().st_mode) == 0o600
    assert ensure_default_users_file(source) is False
    assert source.read_bytes() == original


@pytest.mark.asyncio
async def test_default_users_are_created_once_without_password_overwrite(
    tmp_path,
    db_session: AsyncSession,
) -> None:
    source = tmp_path / "default_users.json"
    _write_users_file(
        source,
        [
            {
                "username": "admin",
                "password": "InitialAdminPassword123!",
                "display_name": "Администратор",
                "role": "admin",
            },
            {
                "username": "operator",
                "password": "InitialOperatorPassword123!",
                "display_name": "Оператор",
                "role": "operator",
            },
        ],
    )

    created = await bootstrap_default_users(source, db_session)

    assert created == ["admin", "operator"]
    accounts = list(
        (
            await db_session.execute(
                select(UserAccount).order_by(UserAccount.username)
            )
        ).scalars()
    )
    assert [account.username for account in accounts] == ["admin", "operator"]
    assert verify_password("InitialAdminPassword123!", accounts[0].password_hash)

    _write_users_file(
        source,
        [
            {
                "username": "admin",
                "password": "ReplacementPassword123!",
                "display_name": "Изменённое имя",
                "role": "operator",
            }
        ],
    )
    assert await bootstrap_default_users(source, db_session) == []
    db_session.expire_all()
    admin = (
        await db_session.execute(
            select(UserAccount).where(UserAccount.username == "admin")
        )
    ).scalar_one()
    assert admin.display_name == "Администратор"
    assert admin.role == "admin"
    assert verify_password("InitialAdminPassword123!", admin.password_hash)
    assert not verify_password("ReplacementPassword123!", admin.password_hash)


def test_default_users_file_rejects_duplicate_usernames(tmp_path) -> None:
    source = tmp_path / "default_users.json"
    users = [
        {
            "username": username,
            "password": "SecureDefaultPassword123!",
            "display_name": username,
            "role": "operator",
        }
        for username in ("operator", "OPERATOR")
    ]
    _write_users_file(source, users)

    with pytest.raises(RuntimeError, match="Invalid default users file"):
        load_default_users(source)
