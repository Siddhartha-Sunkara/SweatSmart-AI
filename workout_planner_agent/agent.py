"""Workout Planner Agent — async multi-stage pipeline."""

from dotenv import load_dotenv

load_dotenv()

import asyncio
import threading
from langsmith import traceable

from .graph import build_agent
from .state import WorkoutState

# =====================================================
# LAZY SINGLETON
# =====================================================

_agent = None
_lock = threading.Lock()


def get_agent():
    global _agent
    with _lock:
        if _agent is None:
            _agent = build_agent()
    return _agent


@traceable(name="workout_planner_agent", run_type="chain")
async def aask(
    user_goal: str,
    filters: dict | None = None,
) -> dict:
    """Run the workout planner pipeline asynchronously."""
    agent = get_agent()
    state: WorkoutState = {
        "user_goal":    user_goal,
        "user_filters": filters or {},
    }
    return await agent.ainvoke(state)


def ask(
    user_goal: str,
    filters: dict | None = None,
) -> dict:
    """Sync wrapper for CLI/scripts."""
    return asyncio.run(aask(user_goal, filters))


# =====================================================
# CLI DEMO
# =====================================================

if __name__ == "__main__":

    result = ask(
        user_goal="High intense advanced chest workout",
        filters={"equipment": ["machine"]},
    )

    plan = result.get("workout_plan", {})

    print("\n" + "=" * 60)
    print(f"\nPLAN:     {plan.get('plan_title')}")
    print(f"Duration: {plan.get('estimated_duration_minutes')} mins")
    print(f"Muscle:   {plan.get('target_muscle')}")
    print(f"Diff:     {plan.get('difficulty')}")
    print(f"\nTip: {plan.get('general_tip')}")

    print("\nEXERCISES:")
    for ex in plan.get("exercises", []):
        print(f"  {ex['exercise_name']}  {ex['sets']}x{ex['reps']}  rest {ex['rest_seconds']}s")
        print(f"  -> {ex['coaching_cue']}")
