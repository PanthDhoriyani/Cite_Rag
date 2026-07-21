"""
retrieval.py — LangChain Hybrid Retrieval + Reranking
=======================================================
Phase 2: Takes a user's question and finds the best chunks of text to answer it.

Pipeline Flow:
  1. Semantic Search (Qdrant) — finds chunks by meaning using vectors
  2. Keyword Search (MongoDB $text) — finds chunks by exact keyword (BM25-style)
  3. Ensemble Retriever — merges the two lists (Qdrant 50% + MongoDB 50%)
  4. Reranker — a CrossEncoder model reads the question + each chunk together
                and scores them for extreme precision, keeping the Top 10.
"""
from loguru import logger
from typing import List, Optional

# LangSmith tracing
from langsmith import traceable

# LangChain Retrievers
from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_cohere import CohereRerank

# LangChain Vector Store (Qdrant) + MongoDB for BM25-style keyword search
from langchain_qdrant import QdrantVectorStore

# MongoDB client access
import db.mongo_client as mongo

# Pydantic, typing & Core imports for custom retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from pydantic import Field
from typing import Any

# Qdrant client
from qdrant_client import QdrantClient

# Config variables
from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COHERE_API_KEY,
    QDRANT_COLLECTION, EMBEDDING_DIM,
    VECTOR_TOP_K, BM25_TOP_K, RERANKER_TOP_K,
    RERANKER_MODEL
)

# Re-use the exact same embeddings singleton from pipeline.py
# (Single Cohere client instance — avoids redundant API initialisation)
from pipeline import embeddings


# =============================================================================
# 1. Semantic Search Retriever (Qdrant)
# =============================================================================
# Finds chunks where the *meaning* matches the question.
# E.g., Question="heart attack" → Finds chunk="cardiac arrest"

qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
    timeout=10
)

# Ensure the collection exists in Qdrant before initializing the LangChain QdrantVectorStore
try:
    existing_collections = [c.name for c in qdrant_client.get_collections().collections]
    if QDRANT_COLLECTION not in existing_collections:
        from qdrant_client.models import VectorParams, Distance
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Qdrant: created collection '{QDRANT_COLLECTION}' on startup (dim={EMBEDDING_DIM})")
except Exception as e:
    logger.warning(f"Qdrant: failed to verify/create collection on startup: {e}")

qdrant_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=QDRANT_COLLECTION,
    embedding=embeddings,
)

# as_retriever automatically embeds the question and searches Qdrant
qdrant_retriever = qdrant_store.as_retriever(search_kwargs={"k": VECTOR_TOP_K})


# =============================================================================
# 2. Keyword Search Retriever (MongoDB native Text Search)
# =============================================================================
# Finds chunks where the *exact words* match the question.
# Uses MongoDB's full-text search index ($text operator) on the chunks collection.

class MongoDBTextRetriever(BaseRetriever):
    collection: Any = Field(exclude=True)
    top_k: int = 20

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        """
        Query MongoDB text index for full-text matches and return them as LangChain Documents.
        """
        cursor = self.collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}, "_id": 0}
        ).sort([("score", {"$meta": "textScore"})]).limit(self.top_k)
        
        results = []
        for doc in cursor:
            metadata = {
                "chunk_id": doc.get("chunk_id"),
                "chunk_index": doc.get("chunk_index"),
                "total_chunks": doc.get("total_chunks"),
                "page_number": doc.get("page_number"),
                "document_id": doc.get("document_id"),
                "document_name": doc.get("document_name"),
                "domain": doc.get("domain"),
                "upload_timestamp": doc.get("upload_timestamp"),
            }
            results.append(Document(
                page_content=doc.get("chunk_text", ""),
                metadata=metadata
            ))
        return results

mongodb_retriever = MongoDBTextRetriever(
    collection=mongo.chunks,
    top_k=BM25_TOP_K
)


# =============================================================================
# 3. Hybrid Search Retriever (Ensemble)
# =============================================================================
# Runs BOTH retrievers at the same time.
# Uses Reciprocal Rank Fusion (RRF) to merge the results.
# If a chunk ranks #1 in Qdrant and #2 in MongoDB, it gets a massive boost.

ensemble_retriever = EnsembleRetriever(
    retrievers=[qdrant_retriever, mongodb_retriever],
    weights=[0.5, 0.5]  # Give 50% weight to semantic, 50% to keyword
)


# =============================================================================
# 4. Reranker (Cohere Rerank Cloud API)
# =============================================================================
# Cohere Rerank API reads (Question, Chunk) pairs and returns a relevance_score
# in the 0.0–1.0 range for each chunk. We keep only the Top RERANKER_TOP_K.
# No local model, no GPU, no disk space — pure API call.

reranker = CohereRerank(
    model=RERANKER_MODEL,           # "rerank-v3.5"
    cohere_api_key=COHERE_API_KEY if COHERE_API_KEY else "dummy_key_set_cohere_api_key_in_env",
    top_n=RERANKER_TOP_K,
)


# The final retriever that runs Ensemble —> then Cohere Reranker
final_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=ensemble_retriever
)


# =============================================================================
# Main Retrieval Function
# =============================================================================

@traceable(name="retrieve_documents", run_type="retriever")
def retrieve_documents(question: str, document_ids: Optional[List[str]] = None):
    """
    Executes the full hybrid retrieval + reranking pipeline.

    Args:
        question: The user's question.
        document_ids: Optional. If provided, restrict search to only these docs.
                      (Note: Filtering logic to be added if needed, currently
                       searches all docs as per Phase 2 scope).

    Returns:
        List of LangChain Document objects (Top 10 most relevant chunks).
        Each Document has `page_content` and `metadata` (including relevance_score).
    """
    logger.info(f"Retrieving chunks for question: '{question}'")

    # If the user selected specific documents, we would apply a metadata filter here.
    # For Phase 2, we execute global retrieval across all docs.
    # (LangChain's ContextualCompressionRetriever doesn't seamlessly pass filters down
    # to all child retrievers out-of-the-box, so we keep it simple for now).

    # 1. Runs Qdrant (top 20) + MongoDB text search (top 20) in parallel
    # 2. Merges them (~40 docs) via Reciprocal Rank Fusion
    # 3. Reranks them and returns the top 10
    results = final_retriever.invoke(question)

    logger.info(f"Retrieved and reranked top {len(results)} chunks.")

    # Log the top score just to see it
    if results:
        best_score = results[0].metadata.get("relevance_score", 0.0)
        logger.debug(f"Top chunk score: {best_score:.4f}")

    return results
