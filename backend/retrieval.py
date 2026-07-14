"""
retrieval.py — LangChain Hybrid Retrieval + Reranking
=======================================================
Phase 2: Takes a user's question and finds the best chunks of text to answer it.

Pipeline Flow:
  1. Semantic Search (Qdrant) — finds chunks by meaning using vectors
  2. Keyword Search (Elasticsearch) — finds chunks by exact keyword (BM25)
  3. Ensemble Retriever — merges the two lists (Qdrant 50% + ES 50%)
  4. Reranker — a CrossEncoder model reads the question + each chunk together
                and scores them for extreme precision, keeping the Top 10.
"""
from loguru import logger
from typing import List, Optional

# LangChain Retrievers
from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

# LangChain Vector / BM25 Stores
from langchain_qdrant import QdrantVectorStore
from langchain_elasticsearch import ElasticsearchRetriever

# Qdrant client
from qdrant_client import QdrantClient

# Config variables
from config import (
    QDRANT_URL, ELASTICSEARCH_URL,
    QDRANT_COLLECTION, ES_INDEX,
    VECTOR_TOP_K, BM25_TOP_K, RERANKER_TOP_K,
    RERANKER_MODEL
)

# Re-use the exact same embeddings singleton loaded in pipeline.py
# (Prevents downloading/loading a 1.2GB model twice into memory)
from pipeline import embeddings


# =============================================================================
# 1. Semantic Search Retriever (Qdrant)
# =============================================================================
# Finds chunks where the *meaning* matches the question.
# E.g., Question="heart attack" → Finds chunk="cardiac arrest"

qdrant_client = QdrantClient(url=QDRANT_URL, timeout=10)

qdrant_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=QDRANT_COLLECTION,
    embedding=embeddings,
)

# as_retriever automatically embeds the question and searches Qdrant
qdrant_retriever = qdrant_store.as_retriever(search_kwargs={"k": VECTOR_TOP_K})


# =============================================================================
# 2. Keyword Search Retriever (Elasticsearch BM25)
# =============================================================================
# Finds chunks where the *exact words* match the question.
# E.g., Question="FDA code 104B" → Finds chunk with exact string "104B".

def bm25_query_builder(query: str):
    """
    Builds the Elasticsearch JSON query for BM25 search.
    Looks for the query terms in the 'text' field.
    """
    return {
        "query": {
            "match": {
                "text": {
                    "query": query
                }
            }
        },
        "size": BM25_TOP_K
    }

es_retriever = ElasticsearchRetriever.from_es_params(
    index_name=ES_INDEX,
    body_func=bm25_query_builder,
    content_field="text",
    url=ELASTICSEARCH_URL,
)


# =============================================================================
# 3. Hybrid Search Retriever (Ensemble)
# =============================================================================
# Runs BOTH retrievers at the same time.
# Uses Reciprocal Rank Fusion (RRF) to merge the results.
# If a chunk ranks #1 in Qdrant and #2 in ES, it gets a massive boost.

ensemble_retriever = EnsembleRetriever(
    retrievers=[qdrant_retriever, es_retriever],
    weights=[0.5, 0.5]  # Give 50% weight to semantic, 50% to keyword
)


# =============================================================================
# 4. Reranker (Cross-Encoder)
# =============================================================================
# The EnsembleRetriever returns ~40 chunks. Some are slightly irrelevant.
# The Cross-Encoder reads both the (Question, Chunk) *together* and gives
# an ultra-precise relevance score (0.0 to 1.0).
# We keep only the Top 10.

# Load the CrossEncoder model (runs locally)
cross_encoder = HuggingFaceCrossEncoder(model_name=RERANKER_MODEL)

# Wrap it in LangChain's Reranker compressor
reranker = CrossEncoderReranker(model=cross_encoder, top_n=RERANKER_TOP_K)

# The final retriever that runs Ensemble -> then Reranker
final_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=ensemble_retriever
)


# =============================================================================
# Main Retrieval Function
# =============================================================================

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

    # 1. Runs Qdrant (top 20) + ES (top 20) in parallel
    # 2. Merges them (~40 docs)
    # 3. Reranks them and returns the top 10
    results = final_retriever.invoke(question)

    logger.info(f"Retrieved and reranked top {len(results)} chunks.")

    # Log the top score just to see it
    if results:
        best_score = results[0].metadata.get("relevance_score", 0.0)
        logger.debug(f"Top chunk score: {best_score:.4f}")

    return results
