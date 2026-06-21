import requests

from api.config import settings
from api.exceptions import ServiceUnavailableError
from qdrant_client import QdrantClient


def check_groq_health() -> bool:
    """Probe Groq's public /openai/v1/models endpoint with the configured key."""
    if not settings.GROQ_API_KEY:
        return False
    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            timeout=5,
        )
        response.raise_for_status()
        return True
    except Exception:
        return False


def require_groq():
    if not check_groq_health():
        raise ServiceUnavailableError("groq", "Groq is not reachable")


def check_qdrant_health():
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        client.get_collections()
        return True
    except Exception:
        return False


def require_qdrant():
    if not check_qdrant_health():
        raise ServiceUnavailableError("qdrant", "Qdrant is not reachable")


def check_redis_health() -> bool:
    """Reports whether the semantic chat cache (Redis) is reachable.
    Returns False if the cache is disabled by config or unreachable."""
    from api.services import semantic_cache
    return semantic_cache.ping()
