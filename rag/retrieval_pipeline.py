import asyncio
import logging
import os

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range, MatchAny
from langsmith import traceable

logger = logging.getLogger(__name__)

# =====================================================
# CONFIG
# =====================================================

COLLECTION_NAME = "exercise_knowledge"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

USE_HYBRID = os.environ.get("USE_HYBRID", "false").lower() == "true"
RETRIEVAL_CANDIDATE_POOL = int(os.environ.get("RETRIEVAL_CANDIDATE_POOL", "30"))

# =====================================================
# LAZY INITIALIZATION FOR EMBEDDING & VECTOR STORE
# =====================================================

_embeddings = None
_vector_store = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        logger.info("Loading embedding model...")
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
    return _embeddings


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore.from_existing_collection(
            embedding=get_embeddings(),
            url=QDRANT_URL,
            collection_name=COLLECTION_NAME
        )
    return _vector_store

# =====================================================
# FILTER BUILDER
# =====================================================
@traceable(name="rag.build_qdrant_filter", run_type="tool")
def build_filters(filters: dict) -> Filter | None:

    conditions = []

    # PRIMARY MUSCLE
    if "primary_muscle" in filters:
        conditions.append(
            FieldCondition(
                key="metadata.primary_muscles",
                match=MatchAny(any=[v.lower() for v in filters["primary_muscle"]])
            )
        )

    # EQUIPMENT
    if "equipment" in filters:
        conditions.append(
            FieldCondition(
                key="metadata.equipment",
                match=MatchAny(any=[v.lower() for v in filters["equipment"]])
            )
        )

    # FATIGUE
    if "max_fatigue_score" in filters:
        conditions.append(
            FieldCondition(
                key="metadata.fatigue_score",
                range=Range(lte=float(filters["max_fatigue_score"]))
            )
        )

    # DIFFICULTY
    if "difficulty_level" in filters:
        conditions.append(
            FieldCondition(
                key="metadata.difficulty_level",
                match=MatchValue(value=filters["difficulty_level"].lower())
            )
        )

    if not conditions:
        return None

    return Filter(must=conditions)


# =====================================================
# DENSE RETRIEVAL
# =====================================================

@traceable(name="rag.retrieve_dense", run_type="retriever")
def _retrieve_dense(
    query: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    query_filter = build_filters(filters) if filters else None
    results: list[tuple[Document, float]] = get_vector_store().similarity_search_with_score(
        query=query,
        k=top_k,
        filter=query_filter,
    )

    exercises: list[dict] = []
    for doc, score in results:
        exercises.append({
            "score": score,
            "exercise_name": doc.metadata.get("exercise_name"),
            "document": doc.page_content,
            "metadata": doc.metadata,
        })
    return exercises


# =====================================================
# HYBRID RETRIEVAL (dense + BM25 + RRF)
# =====================================================

@traceable(name="rag.retrieve_hybrid", run_type="retriever")
def _retrieve_hybrid(
    query: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    # Imported here to avoid forcing rank_bm25 as a hard dep when USE_HYBRID is off.
    from .hybrid import hybrid_search

    query_filter = build_filters(filters) if filters else None
    return hybrid_search(
        vector_store=get_vector_store(),
        query=query,
        qdrant_filter=query_filter,
        candidate_pool_size=RETRIEVAL_CANDIDATE_POOL,
        top_k=top_k,
    )


# =====================================================
# PUBLIC API
# =====================================================

@traceable(name="retrieve_exercises", run_type="retriever")
def retrieve_exercises(
    query: str,
    filters: dict | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Back-compat sync wrapper. Always dense unless USE_HYBRID is set."""
    logger.info("Retrieving exercises for query: %s", query)
    fn = _retrieve_hybrid if USE_HYBRID else _retrieve_dense
    return fn(query, filters, top_k)


@traceable(name="retrieve_one_async", run_type="retriever")
async def retrieve_one_async(
    query: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    """Async wrapper around dense (or hybrid) retrieval."""
    fn = _retrieve_hybrid if USE_HYBRID else _retrieve_dense
    return await asyncio.to_thread(fn, query, filters, top_k)


@traceable(name="retrieve_hybrid_async", run_type="retriever")
async def retrieve_hybrid_async(
    query: str,
    filters: dict | None,
    top_k: int,
) -> list[dict]:
    """Explicit hybrid path, used when callers want to force hybrid."""
    return await asyncio.to_thread(_retrieve_hybrid, query, filters, top_k)


if __name__ == "__main__":

    print("\n==============================")
    print("EXERCISE RETRIEVAL DEBUG")
    print("==============================\n")

    query = "chest exercises"
    filters = {
        "primary_muscle": ["chest"],
        "equipment": ["machine"],
    }

    print(f"Query: {query}")
    print(f"Filters: {filters}")
    print(f"USE_HYBRID: {USE_HYBRID}")

    results = retrieve_exercises(query, filters, top_k=5)
    print(f"\nTotal Results: {len(results)}")

    for idx, r in enumerate(results, start=1):
        print(f"\nRESULT #{idx}")
        print("-" * 50)
        print(f"Score: {r['score']}")
        print(f"Name : {r['exercise_name']}")
        print(f"Equipment: {r['metadata'].get('equipment')}")
