"""Execute validated SQL with rollback, timeout, and row limit."""

import asyncio
import logging
import re

from langsmith import traceable
from sqlalchemy import text

from db.engine import engine
from nl_to_sql_agent.config import MAX_ROWS, QUERY_TIMEOUT
from nl_to_sql_agent.state import NLToSQLState

logger = logging.getLogger(__name__)


def _inject_limit(sql: str, max_rows: int) -> str:
    """Ensure the query has a LIMIT clause, injecting one if missing."""
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return sql
    return f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"


def _execute_readonly(sql: str) -> list[dict]:
    """Run SQL in a transaction that is always rolled back."""
    with engine.connect() as conn:
        # Begin a transaction
        trans = conn.begin()
        try:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows
        finally:
            # Always rollback — we never commit
            trans.rollback()


@traceable(name="query_executor", run_type="chain")
async def query_executor_node(state: NLToSQLState) -> dict:
    """Execute the SQL query with timeout and row limit safeguards."""
    sql = state.get("generated_sql", "")

    # Inject LIMIT if missing
    sql = _inject_limit(sql, MAX_ROWS)

    try:
        rows = await asyncio.wait_for(
            asyncio.to_thread(_execute_readonly, sql),
            timeout=QUERY_TIMEOUT,
        )
        return {
            "query_results": rows[:MAX_ROWS],
            "row_count": len(rows),
        }
    except asyncio.TimeoutError:
        logger.warning("Query execution timed out after %ss", QUERY_TIMEOUT)
        return {
            "query_results": [],
            "row_count": 0,
            "is_valid": False,
            "validation_error": f"Query timed out after {QUERY_TIMEOUT}s",
            "execution_error": f"Query timed out after {QUERY_TIMEOUT}s",
        }
    except Exception as e:
        logger.exception("Query execution failed")
        return {
            "query_results": [],
            "row_count": 0,
            "is_valid": False,
            "validation_error": f"Execution error: {e}",
            "execution_error": str(e),
        }
