"""Regex blocklist + LLM safety/correctness check."""

import logging
import re

from langsmith import traceable
from langchain_groq import ChatGroq

from nl_to_sql_agent.config import (
    GROQ_API_KEY,
    GROQ_VALIDATOR_MODEL,
    LLM_TEMPERATURE,
)
from nl_to_sql_agent.prompts import VALIDATOR_PROMPT
from nl_to_sql_agent.schemas import SQLValidation
from nl_to_sql_agent.state import NLToSQLState

logger = logging.getLogger(__name__)

# =====================================================
# Regex blocklist (Layer 2)
# =====================================================

_BLOCKLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b" + kw + r"\b", re.IGNORECASE)
    for kw in [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "ATTACH", "DETACH",
        "PRAGMA", "VACUUM", "REINDEX",
    ]
] + [
    re.compile(r"load_extension", re.IGNORECASE),
    re.compile(r"writefile", re.IGNORECASE),
]


def _regex_check(sql: str) -> tuple[bool, str]:
    """Return (is_safe, error_message). Safe means no blocklisted tokens."""
    if not sql.strip():
        return False, "Empty SQL query"

    # Multi-statement check: reject if there are multiple statements
    # Strip trailing semicolons/whitespace, then check for interior semicolons
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        return False, "Multi-statement queries are not allowed"

    for pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(sql):
            return False, f"Blocked keyword detected: {pattern.pattern}"

    return True, ""


# =====================================================
# LLM validator chain (Layer 3)
# =====================================================

_validator_chain = None


def _get_validator_chain():
    global _validator_chain
    if _validator_chain is None:
        llm = ChatGroq(
            model=GROQ_VALIDATOR_MODEL,
            api_key=GROQ_API_KEY,
            temperature=LLM_TEMPERATURE,
        )
        _validator_chain = VALIDATOR_PROMPT | llm.with_structured_output(SQLValidation)
    return _validator_chain


@traceable(name="query_validator", run_type="chain")
async def query_validator_node(state: NLToSQLState) -> dict:
    """Validate the generated SQL with regex blocklist + LLM review."""
    sql = state.get("generated_sql", "")
    user_id = state.get("user_id", 0)

    # Layer 2: Regex blocklist
    is_safe, error = _regex_check(sql)
    if not is_safe:
        logger.warning("Regex blocklist rejected query: %s", error)
        return {"is_valid": False, "validation_error": error}

    # Layer 3: LLM validation
    try:
        result: SQLValidation = await _get_validator_chain().ainvoke({
            "ddl_schema": state.get("ddl_schema", ""),
            "user_id": user_id,
            "generated_sql": sql,
        })

        if not result.is_safe:
            return {"is_valid": False, "validation_error": f"Safety check failed: {result.issues}"}
        if not result.has_user_scope:
            return {"is_valid": False, "validation_error": f"Missing user_id scope: {result.issues}"}
        if not result.is_correct:
            return {"is_valid": False, "validation_error": f"Correctness issue: {result.issues}"}

        return {"is_valid": True, "validation_error": ""}

    except Exception as e:
        logger.exception("LLM validator failed")
        # Fail closed: if the validator itself errors, reject the query
        return {"is_valid": False, "validation_error": f"Validation error: {e}"}
