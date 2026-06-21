"""Planner — the only complex LLM agent in the pipeline.

Picks 5-7 exercises from the candidate pool. Must NEVER invent.
"""

from __future__ import annotations

import json
import logging

from langsmith import traceable
from langchain_groq import ChatGroq

from ..config import GROQ_API_KEY, GROQ_PLANNER_MODEL, LLM_TEMPERATURE
from ..prompts import PLANNER_PROMPT
from ..schemas import WorkoutPlan
from ..state import WorkoutState

logger = logging.getLogger(__name__)


_planner_chain = None


def _get_planner_chain():
    global _planner_chain
    if _planner_chain is None:
        llm = ChatGroq(
            model=GROQ_PLANNER_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _planner_chain = PLANNER_PROMPT | llm.with_structured_output(WorkoutPlan)
    return _planner_chain


@traceable(name="planner.format_candidate_pool", run_type="tool")
def _format_candidate_pool(pool: dict[str, list[dict]]) -> str:
    """Compact, LLM-friendly text representation."""
    if not pool:
        return "(empty)"

    lines: list[str] = []
    for muscle, docs in pool.items():
        lines.append(f"## {muscle}")
        if not docs:
            lines.append("  (no candidates)")
            continue
        for d in docs:
            name = d.get("exercise_name", "?")
            equip = ", ".join(d.get("equipment") or []) or "any"
            diff = d.get("difficulty_level") or "?"
            patt = ", ".join(d.get("movement_patterns") or []) or "?"
            fatigue = d.get("fatigue_score")
            lines.append(
                f"- {name} | equipment={equip} | difficulty={diff} "
                f"| patterns={patt} | fatigue={fatigue}"
            )
        lines.append("")
    return "\n".join(lines).strip()


@traceable(name="planner.empty_plan_fallback", run_type="tool")
def _empty_plan(rewritten: dict, reason: str) -> WorkoutPlan:
    muscles = rewritten.get("muscles") or []
    label = ", ".join(muscles) if muscles else "general"
    return WorkoutPlan(
        plan_title="No matching exercises",
        target_muscle=label,
        difficulty=rewritten.get("experience") or "any",
        estimated_duration_minutes=rewritten.get("duration_minutes") or 0,
        exercises=[],
        general_tip=reason,
    )


@traceable(name="planner_node", run_type="chain")
async def planner_node(state: WorkoutState) -> dict:
    rewritten = state.get("rewritten_query") or {}
    pool = state.get("candidate_pool") or {}

    # Short-circuit when the pool has zero exercises.
    total_candidates = sum(len(v) for v in pool.values())
    if total_candidates == 0:
        plan = _empty_plan(
            rewritten,
            "Couldn't find exercises matching those constraints. "
            "Try loosening the equipment or muscle filters.",
        )
        return {"workout_plan": plan.model_dump()}

    target_muscles = rewritten.get("muscles") or []
    inputs = {
        "user_goal":         state.get("user_goal", ""),
        "difficulty":        rewritten.get("experience") or "any",
        "target_muscles":    json.dumps(target_muscles),
        "movement_pattern":  rewritten.get("movement_pattern") or "custom",
        "duration_minutes":  rewritten.get("duration_minutes") or "null",
        "candidate_pool":    _format_candidate_pool(pool),
    }

    try:
        plan: WorkoutPlan = await _get_planner_chain().ainvoke(inputs)
    except Exception as e:
        logger.exception("Planner LLM failed")
        return {
            "workout_plan": _empty_plan(
                rewritten, f"Planner failed: {e}"
            ).model_dump()
        }

    return {"workout_plan": plan.model_dump()}
