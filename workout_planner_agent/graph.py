"""LangGraph wiring for the multi-stage workout planner pipeline."""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langsmith import traceable

from .state import WorkoutState
from .pipeline.query_rewriter import query_rewriter_node
from .pipeline.filter_builder import filter_builder_node
from .pipeline.decomposer import decomposer_node
from .pipeline.retriever import retrieve_node
from .pipeline.aggregator import aggregate_node
from .pipeline.planner import planner_node


# =====================================================
# CONDITIONAL EDGES
# =====================================================

@traceable(name="fanout_to_retrieve", run_type="tool")
def fanout_to_retrieve(state: WorkoutState):
    """Send-API fanout: one parallel `retrieve_node` per sub-query."""
    common = state.get("common_filters") or {}
    subqueries = state.get("subqueries") or []
    return [
        Send(
            "retrieve_node",
            {
                "muscle":         sq["muscle"],
                "query":          sq["query"],
                "common_filters": common,
            },
        )
        for sq in subqueries
    ]


# =====================================================
# BUILD
# =====================================================

def build_agent():
    builder = StateGraph(WorkoutState)

    builder.add_node("query_rewriter", query_rewriter_node)
    builder.add_node("filter_builder", filter_builder_node)
    builder.add_node("decomposer",     decomposer_node)
    builder.add_node("retrieve_node",  retrieve_node)
    builder.add_node("aggregator",     aggregate_node)
    builder.add_node("planner",        planner_node)

    builder.set_entry_point("query_rewriter")
    builder.add_edge("query_rewriter", "filter_builder")
    builder.add_edge("filter_builder", "decomposer")
    builder.add_conditional_edges(
        "decomposer",
        fanout_to_retrieve,
        ["retrieve_node"],
    )
    builder.add_edge("retrieve_node", "aggregator")
    builder.add_edge("aggregator", "planner")
    builder.add_edge("planner", END)

    return builder.compile()
