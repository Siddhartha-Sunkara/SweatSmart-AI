import os

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Rewriter only runs when rules fail → mid-tier model is enough.
GROQ_REWRITER_MODEL = os.environ.get("GROQ_REWRITER_MODEL", "openai/gpt-oss-20b")

# Complex planning agent → flagship Groq Llama 3.3 70B.
GROQ_PLANNER_MODEL = os.environ.get("GROQ_PLANNER_MODEL", "llama-3.3-70b-versatile")

LLM_TEMPERATURE = float(os.environ.get("WORKOUT_LLM_TEMPERATURE", "0.3"))

# =====================================================
# RETRIEVAL CONFIG
# =====================================================

USE_HYBRID               = os.environ.get("USE_HYBRID", "false").lower() == "true"
RETRIEVAL_TOP_K          = int(os.environ.get("RETRIEVAL_TOP_K", "8"))
RETRIEVAL_CANDIDATE_POOL = int(os.environ.get("RETRIEVAL_CANDIDATE_POOL", "30"))
