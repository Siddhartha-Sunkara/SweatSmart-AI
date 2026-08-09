"""Node functions for the Intent Router Agent (async)."""

import logging

from langsmith import traceable
from langchain_groq import ChatGroq

from .config import GROQ_API_KEY, GROQ_INTENT_MODEL, LLM_TEMPERATURE
from .prompts import CLASSIFIER_PROMPT
from .schemas import IntentClassification
from .state import RouterState

logger = logging.getLogger(__name__)

# =====================================================
# LLM (lazy)
# =====================================================

_classifier_chain = None


def _get_classifier_chain():
    global _classifier_chain
    if _classifier_chain is None:
        llm = ChatGroq(
            model=GROQ_INTENT_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _classifier_chain = CLASSIFIER_PROMPT | llm.with_structured_output(IntentClassification)
    return _classifier_chain


# =====================================================
# NODES
# =====================================================

@traceable(name="classify_intent", run_type="chain")
async def classify_intent_node(state: RouterState) -> dict:
    """LLM intent classification."""
    query = state.get("query", "")
    try:
        result: IntentClassification = await _get_classifier_chain().ainvoke({"query": query})
        return {"intent": result.intent}
    except Exception as e:
        logger.warning("Intent classification failed: %s. Falling back to 'greeting'.", e)
        return {"intent": "greeting"}


@traceable(name="greeting_node", run_type="chain")
async def greeting_node(state: RouterState) -> dict:
    """Friendly canned reply for greetings / small talk."""
    response = (
        "Hi! I can build workout plans for you. "
        "Try: 'give me a 30 min push workout with dumbbells' or "
        "'beginner leg day with bodyweight'."
    )
    return {"response": response, "result": {"intent": state.get("intent", "greeting")}}


@traceable(name="stub_node", run_type="chain")
async def stub_node(state: RouterState) -> dict:
    """Polite stub for intents we don't fully support yet."""
    intent = state.get("intent", "unknown")
    label = intent.replace("_", " ")
    response = (
        f"{label.capitalize()} support is coming soon. "
        "For now I can generate workout plans — try "
        "'give me a push workout with dumbbells'."
    )
    return {"response": response, "result": {"intent": intent}}


@traceable(name="run_workout", run_type="chain")
async def run_workout_node(state: RouterState) -> dict:
    """Delegate the full workout pipeline to the workout_planner_agent."""
    try:
        from workout_planner_agent.agent import aask as workout_aask

        result = await workout_aask(
            user_goal=state["query"],
            filters={},
        )
    except Exception as e:
        logger.exception("Workout planner failed")
        return {
            "result": {"error": str(e)},
            "response": f"Something went wrong: {e}",
        }

    return {
        "result": result,
        "response": _format_workout_response(result),
    }


@traceable(name="run_nl_to_sql", run_type="chain")
async def run_nl_to_sql_node(state: RouterState) -> dict:
    """Delegate to the NL-to-SQL agent for workout history queries."""
    try:
        from nl_to_sql_agent.agent import aask as nl_to_sql_aask

        user_id = state.get("user_id", 1)
        result = await nl_to_sql_aask(
            query=state["query"],
            user_id=user_id,
        )
    except Exception as e:
        logger.exception("NL-to-SQL agent failed")
        return {
            "result": {"error": str(e)},
            "response": f"Something went wrong querying your workout history: {e}",
        }

    return {
        "result": result,
        "response": result.get("response", ""),
    }


# =====================================================
# FORMATTING
# =====================================================

@traceable(name="format_workout_response", run_type="tool")
def _format_workout_response(result: dict) -> str:
    if result.get("error"):
        return f"Something went wrong: {result['error']}"

    plan = result.get("workout_plan")
    if not plan or not plan.get("exercises"):
        return (
            "I couldn't find enough matching exercises to build that plan. "
            "Try loosening the equipment or muscle constraints."
        )

    lines = [
        f"Workout Plan: {plan.get('plan_title', 'Untitled')}",
        f"Duration: {plan.get('estimated_duration_minutes', '?')} mins",
        f"Target Muscle: {plan.get('target_muscle', '?')}",
        f"Difficulty: {plan.get('difficulty', '?')}",
        "",
        f"Tip: {plan.get('general_tip', '')}",
        "",
        "Exercises:",
    ]
    for ex in plan.get("exercises", []):
        lines.append(
            f"  - {ex['exercise_name']}  {ex['sets']}x{ex['reps']}  "
            f"rest {ex['rest_seconds']}s"
        )
        lines.append(f"    {ex['coaching_cue']}")
    return "\n".join(lines)
