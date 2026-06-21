from fastapi import APIRouter
from api.models.responses import HealthResponse, ServiceHealthResponse
from api.services.health_service import check_groq_health, check_qdrant_health, check_redis_health

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health():
    groq = check_groq_health()
    qdrant = check_qdrant_health()
    overall_status = "Healthy" if all([groq, qdrant]) else "Unhealthy"
    return HealthResponse(status=overall_status)


@router.get("/api/groq_health", response_model=ServiceHealthResponse)
def groq_health():
    healthy = check_groq_health()
    return ServiceHealthResponse(service="groq", status="Healthy" if healthy else "Unhealthy")


@router.get("/api/qdrant_health", response_model=ServiceHealthResponse)
def qdrant_health():
    healthy = check_qdrant_health()
    return ServiceHealthResponse(service="qdrant", status="Healthy" if healthy else "Unhealthy")


@router.get("/api/redis_health", response_model=ServiceHealthResponse)
def redis_health():
    healthy = check_redis_health()
    return ServiceHealthResponse(service="redis", status="Healthy" if healthy else "Unhealthy")
