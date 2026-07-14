"""
CiteRag — Elasticsearch Client
BM25 keyword indexing for the hybrid retrieval pipeline (Phase 2).

Index: citerag_chunks
  - chunk_text is analyzed with the 'english' analyzer for stemming/stop-word removal.
  - All metadata fields are stored for payload reconstruction without a MongoDB round-trip.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME        = "citerag_chunks"

INDEX_MAPPING: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "chunk_id":         {"type": "keyword"},
            "document_id":      {"type": "keyword"},
            "document_name":    {"type": "text"},
            "chunk_text":       {"type": "text", "analyzer": "english"},
            "page_number":      {"type": "integer"},
            "paragraph_number": {"type": "integer"},
            "domain":           {"type": "keyword"},
            "chunk_index":      {"type": "integer"},
        }
    }
}


# ── Client factory ────────────────────────────────────────────────────────────

def get_client():
    """Return a connected Elasticsearch client."""
    from elasticsearch import Elasticsearch
    return Elasticsearch(ELASTICSEARCH_URL, request_timeout=30)


# ── Index management ──────────────────────────────────────────────────────────

def ensure_index() -> None:
    """Create the Elasticsearch index if it does not already exist (idempotent)."""
    client = get_client()
    if not client.indices.exists(index=INDEX_NAME):
        client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        logger.info(f"[Elasticsearch] Index '{INDEX_NAME}' created.")
    else:
        logger.debug(f"[Elasticsearch] Index '{INDEX_NAME}' already exists.")


# ── Write operations ──────────────────────────────────────────────────────────

def index_chunks(chunks_data: List[Dict[str, Any]]) -> None:
    """
    Bulk-index a list of chunk dicts into Elasticsearch for BM25 retrieval.

    Expected chunk dict shape:
        {
            "chunk_id":         str,
            "document_id":      str,
            "document_name":    str,
            "chunk_text":       str,
            "page_number":      int,
            "paragraph_number": int,
            "domain":           str,
            "chunk_index":      int,
        }
    """
    from elasticsearch.helpers import bulk

    if not chunks_data:
        return

    client  = get_client()
    actions = [
        {
            "_index":  INDEX_NAME,
            "_id":     chunk["chunk_id"],
            "_source": chunk,
        }
        for chunk in chunks_data
    ]

    success, errors = bulk(client, actions, raise_on_error=False, stats_only=False)
    failed_count    = len(errors) if isinstance(errors, list) else 0
    logger.info(
        f"[Elasticsearch] Bulk indexed {success} chunks "
        f"({'no failures' if not failed_count else f'{failed_count} failures'})."
    )


def delete_by_document_id(document_id: str) -> None:
    """Delete all indexed chunks for a given document_id."""
    client = get_client()
    resp   = client.delete_by_query(
        index=INDEX_NAME,
        body={"query": {"term": {"document_id": document_id}}},
    )
    deleted = resp.get("deleted", 0)
    logger.info(
        f"[Elasticsearch] Deleted {deleted} docs for document_id='{document_id}'."
    )


# ── Read operations (Phase 2 BM25 retrieval) ──────────────────────────────────

def bm25_search(
    query:       str,
    top_k:       int             = 20,
    document_id: Optional[str]  = None,
    domain:      Optional[str]  = None,
) -> List[Dict[str, Any]]:
    """
    Multi-match BM25 keyword search across chunk_text and document_name.

    Args:
        query:       Natural-language user question.
        top_k:       Maximum hits to return.
        document_id: Optional filter to a specific document.
        domain:      Optional filter by domain.

    Returns:
        List of dicts: {chunk_id, score, source (chunk fields)}.
    """
    client = get_client()

    must_clauses: List[Dict] = [
        {
            "multi_match": {
                "query":  query,
                "fields": ["chunk_text", "document_name"],
            }
        }
    ]

    filter_clauses: List[Dict] = []
    if document_id:
        filter_clauses.append({"term": {"document_id": document_id}})
    if domain:
        filter_clauses.append({"term": {"domain": domain}})

    es_query: Dict[str, Any] = {"bool": {"must": must_clauses}}
    if filter_clauses:
        es_query["bool"]["filter"] = filter_clauses

    resp = client.search(
        index=INDEX_NAME,
        body={"query": es_query, "size": top_k},
    )

    hits = resp["hits"]["hits"]
    return [
        {
            "chunk_id": hit["_source"]["chunk_id"],
            "score":    hit["_score"],
            "source":   hit["_source"],
        }
        for hit in hits
    ]
