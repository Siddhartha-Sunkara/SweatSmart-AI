# api/services/semantic_cache.py
"""Semantic Redis cache for /api/chat responses.

Uses redisvl.SemanticCache (RediSearch vector index) keyed on the user prompt.
The full chat response dict is JSON-serialized into the SemanticCache's
`response` field. Hits are decoded back into a dict and surfaced as
`{"cached": True, ...payload}`.

The cache is global (not per-user) per product decision: chat responses
do not embed user-specific data beyond the workout plan itself.

Behavior is fail-open: if Redis is unreachable or any cache operation
raises, the cache silently degrades to a no-op and /api/chat still works.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from langsmith import traceable

from api.config import settings

logger = logging.getLogger(__name__)


# Singleton state
_cache = None                # redisvl SemanticCache instance, or None
_initialized = False         # we tried at least once
_disabled_reason: str = ""


def _build_cache():
    """Construct the redisvl SemanticCache. Returns None on any failure."""
    if not settings.SEMANTIC_CACHE_ENABLED:
        return None, "SEMANTIC_CACHE_ENABLED=false"
    if not settings.REDIS_URL:
        return None, "REDIS_URL not set"

    try:
        from redisvl.extensions.cache.llm import SemanticCache
        from redisvl.utils.vectorize import HFTextVectorizer
    except Exception as e:
        return None, f"redisvl import failed: {e}"

    try:
        vectorizer = HFTextVectorizer(model=settings.SEMANTIC_CACHE_EMBED_MODEL)
        cache = SemanticCache(
            name=settings.SEMANTIC_CACHE_INDEX_NAME,
            distance_threshold=settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD,
            ttl=settings.SEMANTIC_CACHE_TTL_SECONDS,
            vectorizer=vectorizer,
            redis_url=settings.REDIS_URL,
        )
        return cache, ""
    except Exception as e:
        return None, f"SemanticCache init failed: {e}"


def _ensure_initialized() -> None:
    global _cache, _initialized, _disabled_reason
    if _initialized:
        return
    _initialized = True
    _cache, _disabled_reason = _build_cache()
    if _cache is None:
        logger.warning("Semantic chat cache disabled: %s", _disabled_reason)
    else:
        logger.info(
            "Semantic chat cache enabled (index=%s, threshold=%.3f, ttl=%ds)",
            settings.SEMANTIC_CACHE_INDEX_NAME,
            settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD,
            settings.SEMANTIC_CACHE_TTL_SECONDS,
        )


def is_enabled() -> bool:
    _ensure_initialized()
    return _cache is not None


def ping() -> bool:
    """For health checks. True iff cache initialized AND Redis is reachable."""
    _ensure_initialized()
    if _cache is None:
        return False
    try:
        client = _cache.index.client  # underlying redis.Redis
        return bool(client.ping())
    except Exception:
        return False


@traceable(name="api.chat_cache.get", run_type="retriever")
async def get(prompt: str) -> Optional[Dict[str, Any]]:
    """Look up a semantically similar cached chat response. None on miss/error."""
    _ensure_initialized()
    if _cache is None or not prompt:
        return None
    try:
        hits = await _cache.acheck(prompt=prompt, num_results=1)
    except Exception as e:
        logger.debug("semantic cache acheck failed: %s", e)
        return None

    if not hits:
        return None

    hit = hits[0]
    raw = hit.get("response")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None

    payload["cached"] = True
    payload["cache_distance"] = hit.get("vector_distance")
    return payload


@traceable(name="api.chat_cache.set", run_type="tool")
async def set_(prompt: str, payload: Dict[str, Any]) -> None:
    """Store a chat response. Silent on any error."""
    _ensure_initialized()
    if _cache is None or not prompt or not isinstance(payload, dict):
        return
    try:
        # Don't persist the cache flag itself
        to_store = {k: v for k, v in payload.items() if k not in ("cached", "cache_distance")}
        await _cache.astore(prompt=prompt, response=json.dumps(to_store))
    except Exception as e:
        logger.debug("semantic cache astore failed: %s", e)


async def aclose() -> None:
    """Close Redis connections on app shutdown."""
    global _cache, _initialized
    if _cache is None:
        return
    try:
        await _cache.adisconnect()
    except Exception:
        pass
    _cache = None
    _initialized = False
