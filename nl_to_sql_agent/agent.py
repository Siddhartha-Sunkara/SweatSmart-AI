"""NL-to-SQL Agent — async natural language to SQL pipeline."""

from dotenv import load_dotenv

load_dotenv()

import asyncio
import threading
from langsmith import traceable

from .graph import build_agent
from .state import NLToSQLState

# =====================================================
# LAZY SINGLETON
# =====================================================

_agent = None
_lock = threading.Lock()


def get_agent():
    global _agent
    with _lock:
        if _agent is None:
            _agent = build_agent()
    return _agent


@traceable(name="nl_to_sql_agent", run_type="chain")
async def aask(query: str, user_id: int) -> dict:
    """Run the NL-to-SQL pipeline and return a result dict (async)."""
    agent = get_agent()
    initial_state: NLToSQLState = {"query": query, "user_id": user_id}
    final_state = await agent.ainvoke(initial_state)
    return {
        "query": final_state.get("query", query),
        "user_id": final_state.get("user_id", user_id),
        "generated_sql": final_state.get("generated_sql", ""),
        "is_valid": final_state.get("is_valid", False),
        "row_count": final_state.get("row_count", 0),
        "response": final_state.get("response", ""),
    }


def ask(query: str, user_id: int) -> dict:
    """Sync wrapper around :func:`aask`. Useful for CLI/scripts."""
    return asyncio.run(aask(query, user_id))


# =====================================================
# CLI DEMO
# =====================================================

if __name__ == "__main__":
    sample_queries = [
        ("What is my heaviest bench press?", 1),
        ("How many workouts did I do last week?", 1),
        ("Show my most recent 5 sessions", 2),
    ]

    print("=" * 60)
    print("NL-to-SQL Agent Demo")
    print("=" * 60)

    for q, uid in sample_queries:
        print(f"\nQuery:    {q} (user_id={uid})")
        result = ask(q, uid)
        print(f"SQL:      {result.get('generated_sql', '')[:100]}")
        print(f"Valid:    {result.get('is_valid')}")
        print(f"Response: {result['response'][:200]}")
        print("-" * 60)
