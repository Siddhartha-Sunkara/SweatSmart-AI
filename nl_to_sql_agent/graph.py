"""Graph construction for the NL-to-SQL agent."""

from langgraph.graph import StateGraph, END
from langsmith import traceable

from .state import NLToSQLState
from .pipeline.schema_inspector import schema_inspector_node
from .pipeline.query_writer import query_writer_node
from .pipeline.query_validator import query_validator_node
from .pipeline.query_executor import query_executor_node
from .pipeline.response_formatter import response_formatter_node

MAX_RETRIES = 2


@traceable(name="route_on_validation", run_type="tool")
def _route_on_validation(state: NLToSQLState) -> str:
    """Route based on validation result: execute if valid, format error if not."""
    if state.get("is_valid", False):
        return "query_executor"
    return "response_formatter"


@traceable(name="route_after_execution", run_type="tool")
def _route_after_execution(state: NLToSQLState) -> str:
    """After execution: if it failed and retries remain, loop back to the writer."""
    error = state.get("execution_error", "")
    retries = state.get("retry_count", 0)
    if error and retries < MAX_RETRIES:
        return "retry"
    return "format"


@traceable(name="bump_retry", run_type="tool")
async def _bump_retry(state: NLToSQLState) -> dict:
    """Increment the retry counter before re-entering the writer."""
    return {"retry_count": state.get("retry_count", 0) + 1}


def build_agent():
    graph = StateGraph(NLToSQLState)

    graph.add_node("schema_inspector", schema_inspector_node)
    graph.add_node("query_writer", query_writer_node)
    graph.add_node("query_validator", query_validator_node)
    graph.add_node("query_executor", query_executor_node)
    graph.add_node("bump_retry", _bump_retry)
    graph.add_node("response_formatter", response_formatter_node)

    graph.set_entry_point("schema_inspector")
    graph.add_edge("schema_inspector", "query_writer")
    graph.add_edge("query_writer", "query_validator")
    graph.add_conditional_edges(
        "query_validator",
        _route_on_validation,
        {
            "query_executor": "query_executor",
            "response_formatter": "response_formatter",
        },
    )
    graph.add_conditional_edges(
        "query_executor",
        _route_after_execution,
        {
            "retry": "bump_retry",
            "format": "response_formatter",
        },
    )
    graph.add_edge("bump_retry", "query_writer")
    graph.add_edge("response_formatter", END)

    return graph.compile()
