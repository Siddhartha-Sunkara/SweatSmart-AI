"""Pydantic schemas for the NL-to-SQL agent."""

from pydantic import BaseModel, Field


class GeneratedSQL(BaseModel):
    reasoning: str = Field(description="Step-by-step reasoning for the SQL query")
    sql: str = Field(description="The generated SELECT SQL query")


class SQLValidation(BaseModel):
    is_safe: bool = Field(description="True if query contains no dangerous operations")
    is_correct: bool = Field(description="True if query is syntactically and logically correct")
    has_user_scope: bool = Field(description="True if query filters by user_id")
    issues: str = Field(
        default="",
        description="Description of any issues found, empty string if none",
    )


class FormattedResponse(BaseModel):
    answer: str = Field(description="Natural language answer to the user's question")
