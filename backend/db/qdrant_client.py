"""
Qdrant — vector database client.

Stores chunk embeddings for semantic (meaning-based) search.
Module-level client is created once on import (lazy connection — safe if Qdrant isn't running yet).
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance,
    PointStruct, Filter, FieldCondition, MatchValue,
)
from config import QDRANT_URL

COLLECTION = "citerag_docs"
VECTOR_DIM  = 1024

# Created once at import — connection is lazy (first actual call triggers connect)
client = QdrantClient(url=QDRANT_URL, timeout=30)


def setup():
    """Create the Qdrant collection if it doesn't already exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


def store_batch(chunk_ids: list, vectors: list, payloads: list):
    """Store a batch of (chunk_id, vector, metadata) into the collection."""
    points = [
        PointStruct(id=cid, vector=vec, payload=pay)
        for cid, vec, pay in zip(chunk_ids, vectors, payloads)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


def search(query_vector: list, top_k: int = 20, filters: dict = None) -> list:
    """
    Find the top_k most semantically similar chunks to query_vector.
    filters: optional dict e.g. {"domain": "healthcare", "document_id": "..."}
    Returns: [{"chunk_id": str, "score": float, "metadata": dict}, ...]
    """
    qfilter = None
    if filters:
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filters.items()
        ]
        qfilter = Filter(must=conditions)

    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        query_filter=qfilter,
        with_payload=True,
    )
    return [
        {"chunk_id": str(r.id), "score": r.score, "metadata": r.payload}
        for r in results
    ]


def delete_document(document_id: str):
    """Delete all vectors that belong to a document."""
    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(must=[
            FieldCondition(key="document_id", match=MatchValue(value=document_id))
        ]),
    )
