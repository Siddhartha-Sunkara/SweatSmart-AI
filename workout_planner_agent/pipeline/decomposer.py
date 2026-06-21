"""Decomposer: deterministic per-muscle subquery builder."""

from __future__ import annotations

from langsmith import traceable

from ..schemas import SubQuery
from ..state import WorkoutState


@traceable(name="decomposer.build_subqueries", run_type="tool")
def build_subqueries(rewritten: dict) -> list[dict]:
    """Pure helper used by tests and by the node.

    Given a RewrittenQuery dict, emit one SubQuery per target muscle.
    """
    muscles = rewritten.get("muscles") or []
    experience = (rewritten.get("experience") or "").strip()
    equipment = rewritten.get("equipment") or []
    equipment_str = ", ".join(equipment) if equipment else ""

    subqueries: list[dict] = []
    for muscle in muscles:
        parts: list[str] = []
        if experience:
            parts.append(experience)
        parts.append(muscle.replace("_", " "))
        parts.append("exercises")
        if equipment_str:
            parts.append(f"with {equipment_str}")
        query = " ".join(p for p in parts if p).strip()
        subqueries.append(SubQuery(muscle=muscle, query=query).model_dump())
    return subqueries


@traceable(name="decomposer_node", run_type="chain")
async def decomposer_node(state: WorkoutState) -> dict:
    rewritten = state.get("rewritten_query") or {}
    return {"subqueries": build_subqueries(rewritten)}
