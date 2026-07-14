"""
CiteRag — MongoDB Client
Stores full chunk text + metadata (for retrieval in Phase 2) and document-level records.

Database: citerag
Collections:
  - chunks     → one document per text chunk, indexed by chunk_id and document_id
  - documents  → one document per uploaded file (status tracking, metadata)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────
MONGODB_URL          = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME              = "citerag"
CHUNKS_COLLECTION    = "chunks"
DOCUMENTS_COLLECTION = "documents"


# ── Client / DB factory ───────────────────────────────────────────────────────

def get_db():
    """Return a synchronous MongoDB database handle (pymongo)."""
    from pymongo import MongoClient
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


# ── Chunk operations ──────────────────────────────────────────────────────────

def insert_chunks(chunks_data: List[Dict[str, Any]]) -> None:
    """
    Bulk-insert chunk records into the 'chunks' collection.

    Each record shape:
        {
            "chunk_id":   str,
            "chunk_text": str,
            "metadata":   ChunkMetadata (as dict)
        }
    """
    if not chunks_data:
        return
    db = get_db()
    db[CHUNKS_COLLECTION].insert_many(chunks_data)
    logger.info(f"[MongoDB] Inserted {len(chunks_data)} chunks.")


def get_chunks_by_document(document_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chunks belonging to a document."""
    db = get_db()
    return list(
        db[CHUNKS_COLLECTION].find(
            {"metadata.document_id": document_id}, {"_id": 0}
        )
    )


def get_chunks_by_ids(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch full chunk records for a list of chunk_ids.
    Used by Phase 2 retriever to hydrate results from Qdrant/ES with chunk text.
    """
    db = get_db()
    return list(
        db[CHUNKS_COLLECTION].find(
            {"chunk_id": {"$in": chunk_ids}}, {"_id": 0}
        )
    )


# ── Document-level operations ─────────────────────────────────────────────────

def insert_document(doc_data: Dict[str, Any]) -> None:
    """Insert a document-level record (called immediately on upload)."""
    db = get_db()
    db[DOCUMENTS_COLLECTION].insert_one(doc_data)
    logger.info(
        f"[MongoDB] Document record created: '{doc_data.get('document_name')}' "
        f"(id={doc_data.get('document_id')})."
    )


def update_document_status(
    document_id: str,
    status:      str,
    total_chunks: int = 0,
) -> None:
    """Update a document's ingestion status and final chunk count."""
    db = get_db()
    db[DOCUMENTS_COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"status": status, "total_chunks": total_chunks}},
    )
    logger.info(
        f"[MongoDB] Document '{document_id}' → status='{status}', "
        f"total_chunks={total_chunks}."
    )


def list_documents() -> List[Dict[str, Any]]:
    """Return all document records (for GET /api/documents)."""
    db = get_db()
    return list(db[DOCUMENTS_COLLECTION].find({}, {"_id": 0}))


def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    """Return a single document record by ID."""
    db = get_db()
    return db[DOCUMENTS_COLLECTION].find_one(
        {"document_id": document_id}, {"_id": 0}
    )


def delete_document(document_id: str) -> None:
    """Remove the document record and all its chunks from MongoDB."""
    db = get_db()
    chunk_result = db[CHUNKS_COLLECTION].delete_many(
        {"metadata.document_id": document_id}
    )
    db[DOCUMENTS_COLLECTION].delete_one({"document_id": document_id})
    logger.info(
        f"[MongoDB] Deleted document '{document_id}' and "
        f"{chunk_result.deleted_count} chunks."
    )
