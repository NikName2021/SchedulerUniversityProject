from typing import Annotated

from api.dependencies import require_authenticated_request
from core.config import async_get_db
from core.constants import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    AUTH_SESSION_HOURS,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from schemas.auth import AuthenticatedUser, AuthResponse, LoginRequest
from services.auth_service import (
    AuthenticatedContext,
    AuthService,
    InvalidCredentialsError,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _user_response(context: AuthenticatedContext) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=context.user.id,
        username=context.user.username,
        display_name=context.user.display_name,
        role=context.user.role,
    )


def _disable_auth_response_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> AuthResponse:
    try:
        user, credentials = await AuthService.authenticate(
            payload.username,
            payload.password,
            request.headers.get("User-Agent"),
            db,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=credentials.token,
        max_age=AUTH_SESSION_HOURS * 60 * 60,
        path="/",
        secure=AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    _disable_auth_response_caching(response)
    return AuthResponse(
        user=AuthenticatedUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
        ),
        csrf_token=credentials.csrf_token,
    )


@router.get("/me", response_model=AuthResponse)
async def current_user(
    response: Response,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_authenticated_request),
    ],
) -> AuthResponse:
    _disable_auth_response_caching(response)
    return AuthResponse(
        user=_user_response(context),
        csrf_token=context.session.csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    context: Annotated[
        AuthenticatedContext,
        Depends(require_authenticated_request),
    ],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    await AuthService.logout(context.session, db)
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        secure=AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    _disable_auth_response_caching(response)
