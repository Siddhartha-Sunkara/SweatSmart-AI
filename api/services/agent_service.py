# api/services/agent_service.py

import asyncio
import logging
from typing import Any, Dict, Optional

from langsmith import traceable

from api.exceptions import AgentError
from api.services import semantic_cache
from intent_agent.agent import aask as chat_aask, get_agent as get_chat_agent
from workout_planner_agent.agent import aask as workout_aask, get_agent as get_workout_agent

logger = logging.getLogger(__name__)


# =====================================================================
# Startup / Shutdown
# =====================================================================

async def warm_up_agents() -> None:
    """Compile both LangGraph singletons up front so the first request
    doesn't pay the cold-start cost. Compilation itself is sync, so we
    push it to a thread. Also touches the semantic cache so its index is
    created (or its failure logged) before the first request."""
    logger.info("Warming up agents...")
    await asyncio.gather(
        asyncio.to_thread(get_chat_agent),
        asyncio.to_thread(get_workout_agent),
        asyncio.to_thread(semantic_cache.is_enabled),
    )
    logger.info("Intent and workout planner agents initialized.")


async def shutdown_executor() -> None:
    """Tear down cache connections during lifespan shutdown."""
    await semantic_cache.aclose()
    logger.info("Agent service shutdown complete.")


@traceable(name="api.chat", run_type="chain")
async def chat(user_prompt: str) -> Dict[str, Any]:
    """Run the intent router asynchronously, with a semantic Redis cache
    in front. Cache is global (keyed on prompt)."""

    # 1. Cache lookup (silent on miss / error)
    cached = await semantic_cache.get(user_prompt)
    if cached is not None:
        return cached

    # 2. Cache miss → run the pipeline
    try:
        result = await chat_aask(user_prompt)
    except Exception as e:
        raise AgentError("intent_router", str(e))

    # 3. Store (fire-and-forget; failures are swallowed inside set_)
    await semantic_cache.set_(user_prompt, result)
    result["cached"] = False
    return result


@traceable(name="api.generate_workout", run_type="chain")
async def generate_workout(
    user_goal: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the workout planner pipeline asynchronously."""
    try:
        return await workout_aask(user_goal, filters or {})
    except Exception as e:
        raise AgentError("workout_planner", str(e))
