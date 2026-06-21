"""Aggregator: dedupe, group by muscle, rank within muscle."""

from __future__ import annotations

from langsmith import traceable

from ..state import WorkoutState


@traceable(name="aggregator.pick_better", run_type="tool")
def _better(a: dict | None, b: dict) -> dict:
    """Pick the doc with the higher dense score (treating None as worst)."""
    if a is None:
        return b
    a_score = a.get("score") if a.get("score") is not None else float("-inf")
    b_score = b.get("score") if b.get("score") is not None else float("-inf")
    return b if b_score > a_score else a


@traceable(name="aggregate_node", run_type="chain")
async def aggregate_node(state: WorkoutState) -> dict:
    docs = state.get("retrieved_docs") or []

    # Dedupe by exercise_name (case-insensitive), keep highest-score variant.
    best_by_name: dict[str, dict] = {}
    for d in docs:
        name = (d.get("exercise_name") or "").strip().lower()
        if not name:
            continue
        best_by_name[name] = _better(best_by_name.get(name), d)

    # Group by the sub-query muscle that surfaced the doc.
    grouped: dict[str, list[dict]] = {}
    for d in best_by_name.values():
        muscle = d.get("_subquery_muscle") or "unknown"
        grouped.setdefault(muscle, []).append(d)

    # Sort each muscle's bucket by score desc.
    for muscle, bucket in grouped.items():
        bucket.sort(
            key=lambda x: x.get("score") if x.get("score") is not None else float("-inf"),
            reverse=True,
        )

    return {"candidate_pool": grouped}
