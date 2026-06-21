import asyncio
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.config import settings

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID to every request/response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Return 504 if the handler exceeds REQUEST_TIMEOUT_SECONDS."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error("Request %s timed out after %ss", request_id, settings.REQUEST_TIMEOUT_SECONDS)
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timed out"},
            )
