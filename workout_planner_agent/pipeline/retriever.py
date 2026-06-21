"""Per-branch retriever invoked via LangGraph's Send-API fanout."""

from __future__ import annotations

import logging
from typing import Any

from langsmith import traceable

from ..config import RETRIEVAL_TOP_K
from rag.retrieval_pipeline import retrieve_one_async

logger = logging.getLogger(__name__)


@traceable(name="retriever.normalize_doc", run_type="tool")
def _normalize_doc(raw: dict, muscle: str) -> dict:
    """Flatten the legacy {score, exercise_name, document, metadata} doc into
    a flat dict tagged with the sub-query muscle."""
    md = raw.get("metadata") or {}
    return {
        "exercise_id":       md.get("exercise_id"),
        "exercise_name":     raw.get("exercise_name") or md.get("exercise_name"),
        "primary_muscles":   md.get("primary_muscles", []) or [],
        "secondary_muscles": md.get("secondary_muscles", []) or [],
        "equipment":         md.get("equipment", []) or [],
        "difficulty_level":  md.get("difficulty_level"),
        "movement_patterns": md.get("movement_patterns", []) or [],
        "fatigue_score":     md.get("fatigue_score"),
        "score":             raw.get("score"),
        "document":          raw.get("document"),
        "_subquery_muscle":  muscle,
    }


@traceable(name="retrieve_node", run_type="retriever")
async def retrieve_node(state: dict) -> dict[str, Any]:
    """Receives a sub-state from a Send: {muscle, query, common_filters}."""
    muscle = state["muscle"]
    query = state["query"]
    common = dict(state.get("common_filters") or {})

    # Per-branch filter: combine common filters with this muscle.
    branch_filters: dict[str, Any] = {k: v for k, v in common.items() if v}
    branch_filters["primary_muscle"] = [muscle]

    try:
        raw_docs = await retrieve_one_async(
            query=query,
            filters=branch_filters,
            top_k=RETRIEVAL_TOP_K,
        )
    except Exception as e:
        logger.warning("Retrieval failed for muscle=%s: %s", muscle, e)
        return {"retrieved_docs": []}

    tagged = [_normalize_doc(d, muscle) for d in raw_docs]
    return {"retrieved_docs": tagged}
