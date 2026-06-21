import json
import os
from pathlib import Path
from tqdm import tqdm

from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# =====================================================
# CONFIG
# =====================================================

COLLECTION_NAME = "exercise_knowledge"
INPUT_FOLDER = "data/exercises"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# =====================================================
# LOAD EMBEDDING MODEL
# =====================================================

print("Loading embedding model...")

embeddings = HuggingFaceBgeEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)

# Probe dimension with a dummy encode
embedding_size = len(embeddings.embed_query("test"))
print(f"Embedding dimension: {embedding_size}")

# =====================================================
# CONNECT TO QDRANT & CREATE COLLECTION
# =====================================================

client = QdrantClient(url=QDRANT_URL)

existing = [c.name for c in client.get_collections().collections]

if COLLECTION_NAME not in existing:
    print(f"Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=embedding_size, distance=Distance.COSINE)
    )

# =====================================================
# LOAD & PROCESS FILES
# =====================================================

files = list(Path(INPUT_FOLDER).glob("*.json"))
print(f"Found {len(files)} retrieval documents.")

documents: list[Document] = []

for file_path in tqdm(files):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # LangChain Document: page_content = what gets embedded,
        # metadata = everything else stored as payload in Qdrant
        doc = Document(
            page_content=data["document"],
            metadata={
                "exercise_id": data["id"],
                **data["metadata"]          # flatten metadata fields directly
            }
        )
        documents.append(doc)

    except Exception as e:
        print(f"\nError processing {file_path.name}: {e}")

# =====================================================
# UPLOAD TO QDRANT VIA LANGCHAIN
# =====================================================

print(f"\nEmbedding and uploading {len(documents)} documents to Qdrant...")

QdrantVectorStore.from_documents(
    documents=documents,
    embedding=embeddings,
    url=QDRANT_URL,
    collection_name=COLLECTION_NAME,
    force_recreate=False        # won't wipe existing collection
)

print("\nUpload complete.")