from typing import Optional

from database import Role
from pydantic import BaseModel, ConfigDict


class ParticipantResponse(BaseModel):
    id: int
    event_id: int
    name: str
    email: str
    role: str
    place: Optional[str] = None
    is_generated: bool
    is_sent: bool
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    role: Role

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EventResponse(BaseModel):
    id: int
    name: str
    date_str: str
    description: str
    image_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EventDetailResponse(EventResponse):
    user_role: str | None = None
    user_place: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str
