"""
CiteRag — Qdrant Vector Database Client
Manages connection, collection lifecycle, vector upsert, and document deletion.

Collection spec:
  - Name:      "documents"
  - Dimension: 1024  (BAAI/bge-large-en-v1.5 output size)
  - Distance:  Cosine similarity
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────
QDRANT_URL      = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "documents"
VECTOR_SIZE     = 1024


# ── Client factory ────────────────────────────────────────────────────────────

def get_client():
    """Return a connected QdrantClient instance."""
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL, timeout=30)


# ── Collection management ─────────────────────────────────────────────────────

def ensure_collection() -> None:
    """
    Create the Qdrant collection if it does not already exist.
    Called at the start of each ingestion run (idempotent).
    """
    from qdrant_client.models import Distance, VectorParams

    client   = get_client()
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info(
            f"[Qdrant] Collection '{COLLECTION_NAME}' created "
            f"(dim={VECTOR_SIZE}, distance=COSINE)."
        )
    else:
        logger.debug(f"[Qdrant] Collection '{COLLECTION_NAME}' already exists.")


# ── Write operations ──────────────────────────────────────────────────────────

def upsert_vectors(
    chunk_ids:  List[str],
    embeddings: List[List[float]],
    payloads:   List[Dict[str, Any]],
) -> None:
    """
    Upsert embedding vectors with metadata payloads into Qdrant.

    Args:
        chunk_ids:  List of unique chunk UUIDs (used as Qdrant point IDs).
        embeddings: List of 1024-dim float vectors.
        payloads:   List of metadata dicts (one per chunk).
    """
    from qdrant_client.models import PointStruct

    client = get_client()
    points = [
        PointStruct(id=cid, vector=emb, payload=payload)
        for cid, emb, payload in zip(chunk_ids, embeddings, payloads)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.info(
        f"[Qdrant] Upserted {len(points)} vectors into '{COLLECTION_NAME}'."
    )


def delete_by_document_id(document_id: str) -> None:
    """Remove all vectors whose payload contains the given document_id."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = get_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        ),
    )
    logger.info(f"[Qdrant] Deleted vectors for document_id='{document_id}'.")


# ── Read operations (used by Phase 2 retriever) ───────────────────────────────

def search_vectors(
    query_vector: List[float],
    top_k:        int                     = 20,
    filter_dict:  Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Nearest-neighbour semantic search in Qdrant.

    Args:
        query_vector: Embedded query (1024-dim).
        top_k:        Number of results to return.
        filter_dict:  Optional payload filters e.g. {"document_id": "..."}.

    Returns:
        List of dicts with keys: chunk_id, score, metadata.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client      = get_client()
    qd_filter   = None

    if filter_dict:
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filter_dict.items()
        ]
        qd_filter = Filter(must=conditions)

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        query_filter=qd_filter,
        with_payload=True,
    )
    return [
        {"chunk_id": str(r.id), "score": r.score, "metadata": r.payload}
        for r in results
    ]
