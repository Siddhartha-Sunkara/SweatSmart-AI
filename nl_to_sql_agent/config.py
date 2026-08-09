"""Configuration for the NL-to-SQL agent."""

import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Writer needs strong SQL reasoning
GROQ_WRITER_MODEL = os.environ.get("GROQ_SQL_WRITER_MODEL", "llama-3.3-70b-versatile")
# Validator and formatter are simpler review tasks
GROQ_VALIDATOR_MODEL = os.environ.get("GROQ_SQL_VALIDATOR_MODEL", "openai/gpt-oss-20b")
GROQ_FORMATTER_MODEL = os.environ.get("GROQ_SQL_FORMATTER_MODEL", "openai/gpt-oss-20b")

LLM_TEMPERATURE = 0

MAX_ROWS = 50
QUERY_TIMEOUT = 5  # seconds
