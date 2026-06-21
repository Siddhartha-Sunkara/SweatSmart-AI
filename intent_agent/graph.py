"""Graph construction for the Intent Router Agent."""

from langgraph.graph import StateGraph, END
from langsmith import traceable

from .state import RouterState
from .nodes import (
    classify_intent_node,
    greeting_node,
    stub_node,
    run_workout_node,
)


@traceable(name="route_on_intent", run_type="tool")
def _route_on_intent(state: RouterState) -> str:
    intent = state.get("intent", "greeting")
    if intent == "workout_generation":
        return "run_workout"
    if intent == "greeting":
        return "greeting_node"
    return "stub_node"


def build_agent():
    graph = StateGraph(RouterState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("run_workout", run_workout_node)
    graph.add_node("greeting_node", greeting_node)
    graph.add_node("stub_node", stub_node)

    graph.set_entry_point("classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        _route_on_intent,
        {
            "run_workout": "run_workout",
            "greeting_node": "greeting_node",
            "stub_node": "stub_node",
        },
    )
    graph.add_edge("run_workout", END)
    graph.add_edge("greeting_node", END)
    graph.add_edge("stub_node", END)

    return graph.compile()
