"""Multi-stage workout generation pipeline.

Each module here is either a small "agent" (LLM-backed) or a deterministic
"tool" node:

- ``query_rewriter``  — LLM-driven rewrite to canonical slugs.
- ``filter_builder``  — deterministic projection (tool).
- ``decomposer``      — deterministic per-muscle subquery builder (tool).
- ``retriever``       — Qdrant per-muscle retrieval (tool, async).
- ``aggregator``      — dedupe + group + rank (tool).
- ``planner``         — the only complex agent: picks 5-7 exercises.
"""
