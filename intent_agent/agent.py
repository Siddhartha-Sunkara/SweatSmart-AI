"""Intent Router Agent — async classifier + router."""

from dotenv import load_dotenv

load_dotenv()

import asyncio
import threading
from langsmith import traceable

from .graph import build_agent
from .state import RouterState

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


@traceable(name="intent_router_agent", run_type="chain")
async def aask(query: str) -> dict:
    """Run the intent router and return a result dict (async)."""
    agent = get_agent()
    initial_state: RouterState = {"query": query}
    final_state = await agent.ainvoke(initial_state)
    return {
        "query": final_state.get("query", query),
        "intent": final_state.get("intent"),
        "result": final_state.get("result", {}),
        "response": final_state.get("response", ""),
    }


def ask(query: str) -> dict:
    """Sync wrapper around :func:`aask`. Useful for CLI/scripts."""
    return asyncio.run(aask(query))


# =====================================================
# CLI DEMO
# =====================================================

if __name__ == "__main__":
    sample_queries = [
        "hello",
        "how do I avoid knee pain when squatting?",
        "give me a beginner push workout with dumbbells",
    ]

    print("=" * 60)
    print("Intent Router Agent Demo")
    print("=" * 60)

    for q in sample_queries:
        print(f"\nQuery:    {q}")
        result = ask(q)
        print(f"Intent:   {result.get('intent')}")
        print(f"Response: {result['response'][:200]}")
        print("-" * 60)
