"""Filter builder: deterministic projection from RewrittenQuery to CommonFilters.

Caller-supplied `user_filters` (e.g. via /api/workout) override the values
derived from the rewritten query.
"""

from __future__ import annotations

from langsmith import traceable

from ..rules import EXPERIENCE_TO_MAX_FATIGUE
from ..schemas import CommonFilters
from ..state import WorkoutState


_KNOWN_FILTER_KEYS = {"difficulty_level", "equipment", "max_fatigue_score"}


def _has_meaningful_filters(filters: dict) -> bool:
    return any(filters.get(k) for k in _KNOWN_FILTER_KEYS)


@traceable(name="filter_builder.build_common_filters", run_type="tool")
def _build_common_filters(rewritten: dict, user_filters: dict) -> CommonFilters:
    experience = rewritten.get("experience")
    derived = CommonFilters(
        difficulty_level=experience or None,
        equipment=rewritten.get("equipment") or None,
        max_fatigue_score=EXPERIENCE_TO_MAX_FATIGUE.get(experience) if experience else None,
    )

    # User overrides win when present.
    if user_filters.get("difficulty_level"):
        derived.difficulty_level = user_filters["difficulty_level"]
    if user_filters.get("equipment"):
        derived.equipment = user_filters["equipment"]
    if user_filters.get("max_fatigue_score") is not None:
        derived.max_fatigue_score = float(user_filters["max_fatigue_score"])
    return derived


@traceable(name="filter_builder_node", run_type="chain")
async def filter_builder_node(state: WorkoutState) -> dict:
    rewritten = state.get("rewritten_query") or {}
    user_filters = state.get("user_filters") or {}

    cf = _build_common_filters(rewritten, user_filters)
    return {"common_filters": cf.model_dump()}
