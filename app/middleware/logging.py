import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()


def _extract_user_id(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ")
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        return payload.get("sub")
    except Exception:
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        user_id = _extract_user_id(request)
        if user_id:
            structlog.contextvars.bind_contextvars(user_id=user_id)
            request.state.user_id = user_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_kwargs = dict(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        if user_id:
            log_kwargs["user_id"] = user_id

        await logger.ainfo("http_request", **log_kwargs)

        return response
