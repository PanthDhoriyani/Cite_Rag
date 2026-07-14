"""
MongoDB — document store.

Holds two collections:
  chunks    — full chunk text + metadata for every ingested piece of text
  documents — one record per uploaded file (name, status, total chunks)

Module-level connection is created once on import.
"""
from pymongo import MongoClient
from config import MONGODB_URL

# Created once at import — lazy connection (safe if Mongo isn't running yet)
_client   = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
db        = _client["citerag"]
chunks    = db["chunks"]     # one document per text chunk
documents = db["documents"]  # one document per uploaded file


# ── Chunks ────────────────────────────────────────────────────────────────────

def save_chunks(chunk_list: list):
    """Bulk-insert a list of chunk dicts into MongoDB."""
    if chunk_list:
        chunks.insert_many(chunk_list)


def get_chunks(chunk_ids: list) -> list:
    """
    Fetch full chunk records by a list of chunk_ids.
    Used in Phase 2 to hydrate retrieval results with full text.
    """
    return list(chunks.find({"chunk_id": {"$in": chunk_ids}}, {"_id": 0}))


# ── Documents ─────────────────────────────────────────────────────────────────

def save_document(doc: dict):
    """Insert a new document record (called immediately on upload)."""
    documents.insert_one(doc)


def update_status(document_id: str, status: str, total_chunks: int = 0):
    """
    Update a document's ingestion status.
    status: "processing" → "ready" or "failed"
    """
    documents.update_one(
        {"document_id": document_id},
        {"$set": {"status": status, "total_chunks": total_chunks}},
    )


def all_documents() -> list:
    """Return all document records (used by GET /api/documents)."""
    return list(documents.find({}, {"_id": 0}))


def remove_document(document_id: str):
    """Delete a document and all its chunks from MongoDB."""
    chunks.delete_many({"document_id": document_id})
    documents.delete_one({"document_id": document_id})
