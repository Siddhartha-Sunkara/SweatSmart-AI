"""BM25 + Reciprocal Rank Fusion re-ranking over a dense candidate pool.

This is a client-side hybrid implementation — it does NOT require sparse
vectors in Qdrant. It works by:

1. Fetching a larger dense candidate pool from Qdrant (with the usual filter).
2. Tokenizing the page_content of each candidate.
3. Running BM25 against the query over those tokens.
4. Combining the dense rank and the BM25 rank with RRF (k=60).
"""

from __future__ import annotations

import logging
import re

from langchain_core.documents import Document
from langsmith import traceable
from qdrant_client.models import Filter
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

_RRF_K = 60
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


@traceable(name="rag.hybrid_search", run_type="retriever")
def hybrid_search(
    vector_store,
    query: str,
    qdrant_filter: Filter | None,
    candidate_pool_size: int,
    top_k: int,
) -> list[dict]:
    """Run dense retrieval over a larger pool, then BM25 + RRF re-rank.

    Returns the same shape as :func:`retrieve_exercises`:
        [{"score", "exercise_name", "document", "metadata"}, ...]
    """
    dense: list[tuple[Document, float]] = vector_store.similarity_search_with_score(
        query=query,
        k=candidate_pool_size,
        filter=qdrant_filter,
    )

    if not dense:
        return []

    # Dense ranks (highest similarity == rank 1).
    dense_rank: dict[int, int] = {}
    for rank, (_, _) in enumerate(dense, start=1):
        dense_rank[rank - 1] = rank  # index -> rank

    # BM25 over page_content.
    corpus_tokens = [_tokenize(doc.page_content) for doc, _ in dense]
    if not any(corpus_tokens):
        bm25_rank: dict[int, int] = {i: len(dense) for i in range(len(dense))}
    else:
        bm25 = BM25Okapi(corpus_tokens)
        scores = bm25.get_scores(_tokenize(query))
        # Sort indices by BM25 score desc and assign ranks.
        order = sorted(range(len(dense)), key=lambda i: scores[i], reverse=True)
        bm25_rank = {idx: rank for rank, idx in enumerate(order, start=1)}

    # RRF fusion.
    fused: list[tuple[int, float]] = []
    for idx in range(len(dense)):
        rrf = 1.0 / (_RRF_K + dense_rank[idx]) + 1.0 / (_RRF_K + bm25_rank[idx])
        fused.append((idx, rrf))
    fused.sort(key=lambda x: x[1], reverse=True)

    top = fused[:top_k]
    result: list[dict] = []
    for idx, rrf_score in top:
        doc, dense_score = dense[idx]
        result.append({
            "score": dense_score,
            "rrf_score": rrf_score,
            "exercise_name": doc.metadata.get("exercise_name"),
            "document": doc.page_content,
            "metadata": doc.metadata,
        })
    return result
