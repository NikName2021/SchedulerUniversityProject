from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().casefold()


class AuthenticatedUser(BaseModel):
    id: int
    username: str
    display_name: str
    role: Literal["admin", "operator"]


class AuthResponse(BaseModel):
    user: AuthenticatedUser
    csrf_token: str
