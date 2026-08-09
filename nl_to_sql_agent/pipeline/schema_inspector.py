"""Deterministic node: extract DDL from SQLAlchemy metadata."""

import logging

from langsmith import traceable

from nl_to_sql_agent.state import NLToSQLState

logger = logging.getLogger(__name__)

_ddl_cache: str | None = None


def _extract_ddl() -> str:
    """Generate CREATE TABLE DDL from SQLAlchemy metadata."""
    global _ddl_cache
    if _ddl_cache is not None:
        return _ddl_cache

    from sqlalchemy import create_engine
    from sqlalchemy.schema import CreateTable

    # Import models so metadata is populated
    from db.engine import engine, Base
    import db.models  # noqa: F401 — registers tables on Base.metadata

    ddl_lines: list[str] = []
    for table in Base.metadata.sorted_tables:
        create_stmt = CreateTable(table).compile(engine)
        ddl_lines.append(str(create_stmt).strip())

    _ddl_cache = "\n\n".join(ddl_lines)
    return _ddl_cache


@traceable(name="schema_inspector", run_type="chain")
async def schema_inspector_node(state: NLToSQLState) -> dict:
    """Extract DDL schema from the database metadata."""
    try:
        ddl = _extract_ddl()
    except Exception as e:
        logger.exception("Failed to extract DDL schema")
        ddl = f"-- Schema extraction failed: {e}"
    return {"ddl_schema": ddl}
