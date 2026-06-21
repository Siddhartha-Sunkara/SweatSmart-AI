"""Configuration constants for the Intent Router Agent."""

import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# Tiny classification task. (llama-3.1-8b-instant blocked at project level on this account.)
GROQ_INTENT_MODEL = os.environ.get("GROQ_INTENT_MODEL", "openai/gpt-oss-20b")
LLM_TEMPERATURE = float(os.environ.get("INTENT_LLM_TEMPERATURE", "0"))
