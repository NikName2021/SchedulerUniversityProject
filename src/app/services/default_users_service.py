import json
from pathlib import Path
from typing import Literal

from database import UserAccount
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service import hash_password, validate_username

MAX_DEFAULT_USERS_FILE_BYTES = 64 * 1024


class DefaultUserDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "operator"]

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return validate_username(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be empty")
        return normalized


class DefaultUsersDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    users: list[DefaultUserDefinition] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_usernames(self) -> "DefaultUsersDefinition":
        usernames = [user.username for user in self.users]
        if len(usernames) != len(set(usernames)):
            raise ValueError("Default usernames must be unique")
        return self


def load_default_users(path: str | Path) -> DefaultUsersDefinition:
    source = Path(path)
    try:
        size = source.stat().st_size
        if size > MAX_DEFAULT_USERS_FILE_BYTES:
            raise ValueError("file exceeds 64 KiB")
        payload = json.loads(source.read_text(encoding="utf-8"))
        return DefaultUsersDefinition.model_validate(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise RuntimeError(f"Invalid default users file: {source}") from exc


async def bootstrap_default_users(
    path: str | Path,
    db: AsyncSession,
) -> list[str]:
    definition = load_default_users(path)
    usernames = [user.username for user in definition.users]
    existing_result = await db.execute(
        select(UserAccount.username).where(UserAccount.username.in_(usernames))
    )
    existing = set(existing_result.scalars())

    created: list[str] = []
    for item, username in zip(definition.users, usernames, strict=True):
        if username in existing:
            continue
        db.add(
            UserAccount(
                username=username,
                display_name=item.display_name,
                password_hash=hash_password(item.password.get_secret_value()),
                role=item.role,
            )
        )
        created.append(username)

    if created:
        await db.commit()
    return created
