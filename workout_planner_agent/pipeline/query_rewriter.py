"""Query rewriter: LLM-driven. Async.

Translates a free-form user goal like

    "give me a beginner push workout with dumbbells"

into a structured :class:`RewrittenQuery`. The decision is delegated to
the LLM, prompted with the full muscle / difficulty / movement-pattern
definitions (see ``prompts.REWRITER_PROMPT``). A thin post-processing
pass lowercases and dedupes the emitted slugs to defend against minor
formatting drift.
"""

from __future__ import annotations

import logging

from langsmith import traceable
from langchain_groq import ChatGroq

from ..config import GROQ_API_KEY, GROQ_REWRITER_MODEL, LLM_TEMPERATURE
from ..prompts import REWRITER_PROMPT
from ..schemas import RewrittenQuery
from ..state import WorkoutState

logger = logging.getLogger(__name__)


# =====================================================
# LLM (lazy)
# =====================================================

_llm_chain = None


def _get_llm_chain():
    global _llm_chain
    if _llm_chain is None:
        llm = ChatGroq(
            model=GROQ_REWRITER_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _llm_chain = REWRITER_PROMPT | llm.with_structured_output(RewrittenQuery)
    return _llm_chain


# =====================================================
# DEFENSIVE NORMALIZATION
# =====================================================

def _clean_slug(s: str | None) -> str | None:
    if not s:
        return None
    return s.strip().lower().replace(" ", "_")


def _clean_list(xs: list[str] | None) -> list[str]:
    if not xs:
        return []
    cleaned = [_clean_slug(x) for x in xs]
    return list(dict.fromkeys([c for c in cleaned if c]))


@traceable(name="query_rewriter.normalize", run_type="tool")
def _normalize(rq: RewrittenQuery) -> RewrittenQuery:
    rq.muscles = _clean_list(rq.muscles)
    rq.equipment = _clean_list(rq.equipment) or None
    rq.experience = _clean_slug(rq.experience)
    rq.movement_pattern = _clean_slug(rq.movement_pattern)
    return rq


# =====================================================
# NODE
# =====================================================

@traceable(name="query_rewriter_node", run_type="chain")
async def query_rewriter_node(state: WorkoutState) -> dict:
    user_goal = state.get("user_goal", "") or ""

    try:
        llm_rq: RewrittenQuery = await _get_llm_chain().ainvoke(
            {"user_goal": user_goal}
        )
    except Exception as e:
        logger.warning("Rewriter LLM call failed (%s). Emitting empty rewrite.", e)
        llm_rq = RewrittenQuery(muscles=[])

    rq = _normalize(llm_rq)
    return {"rewritten_query": rq.model_dump()}
