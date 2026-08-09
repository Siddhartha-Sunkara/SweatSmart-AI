"""LLM node: convert natural language to a SELECT statement."""

import logging
import re

from langsmith import traceable
from langchain_groq import ChatGroq

from nl_to_sql_agent.config import (
    GROQ_API_KEY,
    GROQ_WRITER_MODEL,
    LLM_TEMPERATURE,
    MAX_ROWS,
)
from nl_to_sql_agent.prompts import WRITER_PROMPT
from nl_to_sql_agent.schemas import GeneratedSQL
from nl_to_sql_agent.state import NLToSQLState

logger = logging.getLogger(__name__)

_writer_chain = None


def _get_writer_chain():
    global _writer_chain
    if _writer_chain is None:
        llm = ChatGroq(
            model=GROQ_WRITER_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _writer_chain = WRITER_PROMPT | llm.with_structured_output(GeneratedSQL)
    return _writer_chain


# =====================================================
# CASE-INSENSITIVE SQL POST-PROCESSING
# =====================================================

_CI_COLUMNS = ('primary_muscle', 'username', 'exercise_name', 'equipment')


def _ensure_case_insensitive(sql: str) -> str:
    """Wrap bare string-column comparisons with LOWER() for case-insensitive matching.

    The LLM prompt already asks for LOWER(), but this is a defensive
    code-level guarantee so queries never silently fail due to casing.
    """
    sql_lower = sql.lower()
    for col in _CI_COLUMNS:
        # If LOWER() is already applied for this column, skip it.
        if f"lower({col})" in sql_lower:
            continue

        # column = 'value' / column != 'value' / column LIKE 'value'
        eq_pattern = re.compile(
            rf"\b({col})\s*(=|!=|<>|LIKE)\s*('(?:[^'\\]|\\.)*')",
            re.IGNORECASE,
        )
        sql = eq_pattern.sub(
            lambda m: f"LOWER({m.group(1)}) {m.group(2)} LOWER({m.group(3)})",
            sql,
        )

        # column IN ('v1', 'v2', ...)
        in_pattern = re.compile(
            rf"\b({col})\s+(IN)\s*\(([^)]+)\)",
            re.IGNORECASE,
        )

        def _fix_in_clause(m: re.Match) -> str:
            col_name = m.group(1)
            values = m.group(3)
            fixed = re.sub(r"('(?:[^'\\]|\\.)*')", r"LOWER(\1)", values)
            return f"LOWER({col_name}) IN ({fixed})"

        sql = in_pattern.sub(_fix_in_clause, sql)

    return sql


@traceable(name="query_writer", run_type="chain")
async def query_writer_node(state: NLToSQLState) -> dict:
    """Use an LLM to convert the user's question into a SELECT statement."""
    query = state.get("query", "")

    # On retry, append the execution error so the LLM can self-correct.
    execution_error = state.get("execution_error", "")
    if execution_error:
        failed_sql = state.get("generated_sql", "")
        query = (
            f"{query}\n\n"
            f"PREVIOUS ATTEMPT FAILED. Fix the SQL error below.\n"
            f"Failed SQL:\n{failed_sql}\n"
            f"Error:\n{execution_error}\n"
            f"Carefully check that every column is referenced with the correct table. "
            f"Re-read the schema and try again."
        )

    try:
        result: GeneratedSQL = await _get_writer_chain().ainvoke({
            "query": query,
            "ddl_schema": state.get("ddl_schema", ""),
            "user_id": state.get("user_id", 0),
            "max_rows": MAX_ROWS,
        })
        sql = _ensure_case_insensitive(result.sql.strip())
        return {"generated_sql": sql, "execution_error": ""}
    except Exception as e:
        logger.exception("Query writer failed")
        return {"generated_sql": "", "is_valid": False, "validation_error": str(e)}
