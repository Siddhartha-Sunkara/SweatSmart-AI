import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# =====================================================
# Custom exception classes
# =====================================================

class AgentError(Exception):
    """Raised when an agent (intent router, workout planner) fails."""

    def __init__(self, agent_name: str, detail: str):
        self.agent_name = agent_name
        self.detail = detail
        super().__init__(f"{agent_name}: {detail}")


class ServiceUnavailableError(Exception):
    """Raised when an external service (Groq, Qdrant) is unreachable."""

    def __init__(self, service: str, detail: str = "Service is unavailable"):
        self.service = service
        self.detail = detail
        super().__init__(f"{service}: {detail}")


class ResourceNotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        self.detail = f"{resource} '{identifier}' not found"
        super().__init__(self.detail)


# =====================================================
# Exception handlers
# =====================================================

async def agent_error_handler(request: Request, exc: AgentError) -> JSONResponse:
    logger.error("AgentError in %s: %s", exc.agent_name, exc.detail)
    return JSONResponse(
        status_code=500,
        content={
            "error": "agent_error",
            "agent": exc.agent_name,
            "detail": exc.detail,
        },
    )


async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError) -> JSONResponse:
    logger.error("ServiceUnavailable: %s — %s", exc.service, exc.detail)
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_unavailable",
            "service": exc.service,
            "detail": exc.detail,
        },
    )


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "resource": exc.resource,
            "detail": exc.detail,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""
    app.add_exception_handler(AgentError, agent_error_handler)
    app.add_exception_handler(ServiceUnavailableError, service_unavailable_handler)
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
