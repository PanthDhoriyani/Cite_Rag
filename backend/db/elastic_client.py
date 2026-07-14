"""
Elasticsearch — BM25 keyword search index.

Indexes chunk text so keyword queries can find relevant chunks fast.
Uses the English analyzer (handles stemming + stop-words automatically).
Module-level client is created once on import.
"""
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from config import ELASTICSEARCH_URL

INDEX = "citerag_chunks"

# Created once at import — lazy connection (safe if ES isn't running yet)
client = Elasticsearch(ELASTICSEARCH_URL, request_timeout=30)


def setup():
    """Create the Elasticsearch index with field mappings if it doesn't exist."""
    if not client.indices.exists(index=INDEX):
        client.indices.create(index=INDEX, body={
            "mappings": {
                "properties": {
                    "chunk_id":      {"type": "keyword"},
                    "document_id":   {"type": "keyword"},
                    "document_name": {"type": "text"},
                    "chunk_text":    {"type": "text", "analyzer": "english"},
                    "domain":        {"type": "keyword"},
                    "page_number":   {"type": "integer"},
                }
            }
        })


def index_chunks(chunk_list: list):
    """Bulk-index a list of chunk dicts for BM25 keyword search."""
    actions = [
        {"_index": INDEX, "_id": c["chunk_id"], "_source": c}
        for c in chunk_list
    ]
    if actions:
        bulk(client, actions, raise_on_error=False)


def search(query: str, top_k: int = 20,
           document_id: str = None, domain: str = None) -> list:
    """
    BM25 keyword search across chunk_text and document_name.
    Returns: [{"chunk_id": str, "score": float}, ...]
    """
    must    = [{"multi_match": {"query": query, "fields": ["chunk_text", "document_name"]}}]
    filter_ = []
    if document_id:
        filter_.append({"term": {"document_id": document_id}})
    if domain:
        filter_.append({"term": {"domain": domain}})

    body = {"query": {"bool": {"must": must}}}
    if filter_:
        body["query"]["bool"]["filter"] = filter_

    hits = client.search(index=INDEX, body={**body, "size": top_k})["hits"]["hits"]
    return [{"chunk_id": h["_source"]["chunk_id"], "score": h["_score"]} for h in hits]


def delete_document(document_id: str):
    """Remove all indexed chunks for a document."""
    client.delete_by_query(
        index=INDEX,
        body={"query": {"term": {"document_id": document_id}}},
    )
