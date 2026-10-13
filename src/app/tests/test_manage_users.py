import csv
import io
from types import SimpleNamespace

import pytest
from database import UserAccount
from manage_users import _create_users
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_bulk_user_creation_is_atomic_and_outputs_credentials(
    db_session: AsyncSession, monkeypatch, capsys
) -> None:
    import manage_users

    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(manage_users, "sessionmaker", factory)
    await _create_users(
        SimpleNamespace(
            prefix="operator",
            count=6,
            start=1,
            display_name_prefix="Оператор",
            role="operator",
        )
    )

    credentials = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert [item["username"] for item in credentials] == [
        f"operator{index}" for index in range(1, 7)
    ]
    assert all(len(item["password"]) >= 12 for item in credentials)
    assert all(item["role"] == "operator" for item in credentials)

    async with factory() as db:
        users = list(
            (
                await db.scalars(
                    select(UserAccount)
                    .where(UserAccount.username.like("operator%"))
                    .order_by(UserAccount.username)
                )
            ).all()
        )
    assert [user.display_name for user in users] == [
        f"Оператор {index}" for index in range(1, 7)
    ]

    with pytest.raises(ValueError, match="already exist"):
        await _create_users(
            SimpleNamespace(
                prefix="operator",
                count=6,
                start=1,
                display_name_prefix="Оператор",
                role="operator",
            )
        )
