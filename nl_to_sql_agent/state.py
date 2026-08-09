"""State definition for the NL-to-SQL agent."""

from typing import TypedDict


class NLToSQLState(TypedDict, total=False):
    # Inputs
    query: str
    user_id: int

    # schema_inspector
    ddl_schema: str

    # query_writer
    generated_sql: str

    # query_validator
    is_valid: bool
    validation_error: str

    # query_executor
    query_results: list[dict]
    row_count: int

    # retry loop
    retry_count: int
    execution_error: str

    # response_formatter
    response: str
