import secrets
from typing import Annotated

from core.config import AUTH_COOKIE_NAME, async_get_db
from fastapi import Depends, HTTPException, Request, status
from services.auth_service import AuthenticatedContext, AuthService
from sqlalchemy.ext.asyncio import AsyncSession

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def require_authenticated_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> AuthenticatedContext:
    context = await AuthService.load_session(
        request.cookies.get(AUTH_COOKIE_NAME),
        db,
    )
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    if request.method not in SAFE_METHODS:
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not csrf_token or not secrets.compare_digest(
            csrf_token,
            context.session.csrf_token,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

    request.state.auth = context
    return context
