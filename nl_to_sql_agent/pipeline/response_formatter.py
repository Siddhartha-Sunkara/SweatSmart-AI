"""LLM node: convert raw query results into a natural language answer."""

import json
import logging

from langsmith import traceable
from langchain_groq import ChatGroq

from nl_to_sql_agent.config import (
    GROQ_API_KEY,
    GROQ_FORMATTER_MODEL,
    LLM_TEMPERATURE,
)
from nl_to_sql_agent.prompts import FORMATTER_PROMPT
from nl_to_sql_agent.schemas import FormattedResponse
from nl_to_sql_agent.state import NLToSQLState

logger = logging.getLogger(__name__)

_formatter_chain = None


def _get_formatter_chain():
    global _formatter_chain
    if _formatter_chain is None:
        llm = ChatGroq(
            model=GROQ_FORMATTER_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _formatter_chain = FORMATTER_PROMPT | llm.with_structured_output(FormattedResponse)
    return _formatter_chain


def _format_results(results: list[dict]) -> str:
    """Pretty-print query results for the LLM."""
    if not results:
        return "(no results)"
    try:
        return json.dumps(results, indent=2, default=str)
    except (TypeError, ValueError):
        return str(results)


@traceable(name="response_formatter", run_type="chain")
async def response_formatter_node(state: NLToSQLState) -> dict:
    """Format raw SQL results into a natural language answer."""
    try:
        result: FormattedResponse = await _get_formatter_chain().ainvoke({
            "query": state.get("query", ""),
            "generated_sql": state.get("generated_sql", ""),
            "is_valid": state.get("is_valid", False),
            "validation_error": state.get("validation_error", ""),
            "row_count": state.get("row_count", 0),
            "query_results": _format_results(state.get("query_results", [])),
        })
        return {"response": result.answer}
    except Exception as e:
        logger.exception("Response formatter failed")
        # Fallback: return raw data
        if not state.get("is_valid", False):
            return {"response": f"I couldn't process that query: {state.get('validation_error', 'unknown error')}"}
        results = state.get("query_results", [])
        if results:
            return {"response": f"Here are the raw results:\n{_format_results(results)}"}
        return {"response": "No results found for your query."}
