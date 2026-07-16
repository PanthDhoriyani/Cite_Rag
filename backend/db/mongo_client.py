"""
db/mongo_client.py — MongoDB Client
=====================================
MongoDB is used for two things that LangChain doesn't handle:

  1. Document status tracking
     When a file is uploaded, a record is created immediately with status="processing".
     After ingestion succeeds → status="ready".
     If ingestion fails → status="failed".
     The client polls GET /api/documents to check progress.

  2. Full chunk text storage
     When building citations, we need the full text of each chunk.
     LangChain stores chunk text in Qdrant payloads too, but MongoDB is the
     dedicated source of truth for full text and metadata.

Collections:
  - documents: one record per uploaded file
  - chunks:    one record per text chunk
"""
from pymongo import MongoClient
from config import MONGODB_URL, MONGO_DB_NAME

# =============================================================================
# Connection
# =============================================================================
# Module-level connection — created once on import.
# MongoClient connects lazily (first actual operation triggers the connection).
# serverSelectionTimeoutMS=5000: fail fast if MongoDB is not reachable.
_client    = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
_db        = _client[MONGO_DB_NAME]

# These are the two collections we use
documents  = _db["documents"]   # one document per uploaded file
chunks     = _db["chunks"]      # one document per text chunk

# Ensure full-text search index is created on chunk_text for keyword matching queries
chunks.create_index([("chunk_text", "text")])


# =============================================================================
# Document Operations
# =============================================================================

def save_document(doc: dict):
    """
    Insert a new document record when a file is first uploaded.
    Called immediately on upload — before ingestion starts.

    Example doc:
    {
        "document_id": "uuid",
        "document_name": "paper.pdf",
        "file_path": "uploads/uuid.pdf",
        "file_type": "pdf",
        "domain": "research",
        "upload_timestamp": "2026-01-01T10:00:00",
        "status": "processing",
        "total_chunks": 0
    }
    """
    documents.insert_one(doc)


def update_status(document_id: str, status: str, total_chunks: int = 0):
    """
    Update a document's ingestion status.
    Called by pipeline.run() after ingestion:
      - "ready" + total chunk count if ingestion succeeded
      - "failed" + 0 chunks if anything went wrong
    """
    documents.update_one(
        {"document_id": document_id},
        {"$set": {"status": status, "total_chunks": total_chunks}}
    )


def all_documents() -> list:
    """
    Return all document records.
    Used by GET /api/documents to show the user their uploaded files.
    Excludes MongoDB's internal _id field from the response.
    """
    return list(documents.find({}, {"_id": 0}))


def remove_document(document_id: str):
    """
    Delete a document and ALL its chunks from MongoDB.
    Called by DELETE /api/documents/{id} — the route also removes from Qdrant and ES.
    """
    chunks.delete_many({"document_id": document_id})    # delete all its chunks first
    documents.delete_one({"document_id": document_id})  # then the document record


# =============================================================================
# Chunk Operations
# =============================================================================

def save_chunks(chunk_list: list):
    """
    Bulk-insert a list of chunk dicts into MongoDB.
    Each chunk has: chunk_id, chunk_text, page_number, document_id, domain, etc.
    Called during ingestion (pipeline.py) after splitting.
    """
    if chunk_list:
        chunks.insert_many(chunk_list)


def get_chunks(chunk_ids: list) -> list:
    """
    Fetch full chunk records by a list of chunk_ids.
    Used in Phase 2 to hydrate retrieval results with full text and metadata
    when building citation objects for the response.
    Returns list of chunk dicts (without MongoDB's _id field).
    """
    return list(chunks.find({"chunk_id": {"$in": chunk_ids}}, {"_id": 0}))


def get_chunk_by_id(chunk_id: str) -> dict:
    """
    Fetch a single chunk record by its chunk_id.
    Used by the PDF highlight endpoint to retrieve chunk_text and page_number.
    Returns None if not found.
    """
    return chunks.find_one({"chunk_id": chunk_id}, {"_id": 0})


def get_document_by_id(document_id: str) -> dict:
    """
    Fetch a single document record by its document_id.
    Used by the PDF highlight endpoint to retrieve the file_path on disk.
    Returns None if not found.
    """
    return documents.find_one({"document_id": document_id}, {"_id": 0})
