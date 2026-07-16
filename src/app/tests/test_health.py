import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from main import app
from middleware.logging_middleware import LoggingMiddleware


@pytest.mark.asyncio
async def test_liveness_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_logging_middleware_does_not_suppress_exceptions() -> None:
    middleware = LoggingMiddleware(app=app)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/failing",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("test", 80),
            "scheme": "http",
            "http_version": "1.1",
        }
    )

    async def failing_call_next(_: Request):
        raise ValueError("expected failure")

    with pytest.raises(ValueError, match="expected failure"):
        await middleware.dispatch(request, failing_call_next)
