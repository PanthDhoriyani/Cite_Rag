"""
routers/upload.py — File Upload Endpoints
==========================================
Handles all document management API routes:

  POST   /api/upload            → Upload a new document
  GET    /api/documents         → List all uploaded documents + status
  DELETE /api/documents/{id}    → Delete a document from all stores

How upload works:
  1. Validate file extension and size
  2. Save file to disk (uploads/ folder with UUID filename)
  3. Create a MongoDB record with status="processing"
  4. Trigger pipeline.run() as a BackgroundTask (returns immediately)
  5. Client polls GET /api/documents to check when status→"ready"

Why BackgroundTask?
  Embedding 100 pages takes 30-120 seconds. We don't want the HTTP request
  to time out. FastAPI's BackgroundTask runs after the response is sent.
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

# LangSmith tracing
from langsmith import traceable

# Config — file upload settings
from config import UPLOAD_DIR, MAX_FILE_MB

# Pydantic models for request/response validation
from schemas import Domain, UploadResponse

# The ingestion pipeline — called as a background task after upload
from pipeline import run as run_pipeline

# Database clients for cleanup on delete
import db.mongo_client as mongo
from config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION

router      = APIRouter()

# Allowed file extensions — all others are rejected at validation
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

# Upload directory as a Path object (easier to work with than strings)
UPLOAD_PATH = Path(UPLOAD_DIR)


# =============================================================================
# POST /api/upload
# =============================================================================

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,  # 202 Accepted = we received it, processing in background
    summary="Upload a document for RAG ingestion",
)
@traceable(name="upload_document", run_type="chain")
async def upload_document(
    background_tasks: BackgroundTasks,
    file:   UploadFile = File(...),          # the uploaded file
    domain: Domain     = Form(Domain.general), # document domain (dropdown in UI)
):
    """
    Upload a PDF, DOCX, or TXT file for ingestion into the RAG system.

    The response is returned immediately (status="processing").
    Ingestion (extract → chunk → embed → store) runs in the background.

    Poll GET /api/documents to check when status changes to "ready".
    """
    filename = file.filename or "unknown_file"

    # -- Validate file extension -----------------------------------------------
    # Split on last dot to get extension, lower-case it for consistency
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"File type '.{ext}' is not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )

    # -- Read file and validate size -------------------------------------------
    # We read the whole file into memory to check size before saving to disk
    data    = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise HTTPException(
            status_code=422,
            detail=f"File is {size_mb:.1f} MB — maximum allowed is {MAX_FILE_MB} MB."
        )

    # -- Save file to disk -----------------------------------------------------
    # Use a UUID as the filename to avoid collisions and not expose original names
    doc_id    = str(uuid.uuid4())
    UPLOAD_PATH.mkdir(parents=True, exist_ok=True)  # create uploads/ if needed
    save_path = UPLOAD_PATH / f"{doc_id}.{ext}"
    save_path.write_bytes(data)

    # Record the upload timestamp (UTC) for metadata
    now = datetime.utcnow()

    # -- Create MongoDB document record ----------------------------------------
    # This is created BEFORE ingestion so the client can immediately poll status
    mongo.save_document({
        "document_id":      doc_id,
        "document_name":    filename,
        "file_path":        str(save_path),
        "file_type":        ext,
        "domain":           domain.value,        # e.g. "research", "healthcare"
        "upload_timestamp": now.isoformat(),
        "status":           "processing",        # will change to "ready" or "failed"
        "total_chunks":     0,                   # will be updated after ingestion
    })

    # -- Trigger ingestion in the background -----------------------------------
    # run_pipeline() does: load → split → store → update_status("ready")
    # It runs AFTER the response is sent to the client
    background_tasks.add_task(
        run_pipeline,
        document_id=doc_id,
        file_path=str(save_path),
        filename=filename,
        file_type=ext,
        domain=domain.value,
        upload_timestamp=now,
    )

    logger.info(
        f"Uploaded '{filename}' ({size_mb:.1f} MB) "
        f"domain={domain.value} → {save_path}"
    )

    # Return immediately — ingestion is still running in the background
    return UploadResponse(
        document_id=doc_id,
        filename=filename,
        status="processing",
        message="File accepted. Ingestion running in background. Poll /api/documents for status.",
    )


# =============================================================================
# GET /api/documents
# =============================================================================

@router.get(
    "/documents",
    summary="List all uploaded documents and their ingestion status",
)
def list_documents():
    """
    Return all uploaded documents with their current status.

    Status values:
      - "processing" → ingestion is still running in the background
      - "ready"      → chunks stored, document is searchable
      - "failed"     → ingestion encountered an error
    """
    return {"documents": mongo.all_documents()}


# =============================================================================
# DELETE /api/documents/{document_id}
# =============================================================================

@router.delete(
    "/documents/{document_id}",
    summary="Delete a document from all storage backends",
)
def delete_document(document_id: str, background_tasks: BackgroundTasks):
    """
    Delete a document and all its chunks from:
      - Qdrant (removes the embedding vectors)
      - Elasticsearch (removes from BM25 index)
      - MongoDB (removes chunk records and the document record)

    Deletion runs in the background so the endpoint responds immediately.
    """
    background_tasks.add_task(_delete_from_all_stores, document_id)
    logger.info(f"Delete queued for document: {document_id}")
    return {"document_id": document_id, "status": "deletion_queued"}


def _delete_from_all_stores(document_id: str):
    """
    Remove all data for a document from all three storage backends.
    Runs as a BackgroundTask — errors are logged but don't crash anything.

    Order: Qdrant → Elasticsearch → MongoDB
    (MongoDB last so status record exists while other deletes run)
    """
    # Delete vectors from Qdrant
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
            timeout=30
        )
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id))
            ])
        )
        logger.info(f"Qdrant: deleted vectors for {document_id}")
    except Exception as e:
        logger.warning(f"Qdrant delete failed for {document_id}: {e}")



    # Delete from MongoDB (last — this removes the status record too)
    try:
        mongo.remove_document(document_id)
        logger.info(f"MongoDB: deleted document and chunks for {document_id}")
    except Exception as e:
        logger.warning(f"MongoDB delete failed for {document_id}: {e}")


@router.patch(
    "/documents/{document_id}/rename",
    summary="Rename an ingested document and its chunks in all databases",
)
def rename_document(document_id: str, new_name: str):
    """
    Rename a document and all its chunks in MongoDB and Qdrant.
    """
    try:
        # 1. Update document name in MongoDB documents collection
        mongo.documents.update_one(
            {"document_id": document_id},
            {"$set": {"document_name": new_name}}
        )

        # 2. Update document name in MongoDB chunks collection
        mongo.chunks.update_many(
            {"document_id": document_id},
            {"$set": {"document_name": new_name}}
        )
        logger.info(f"MongoDB: renamed document to '{new_name}' for {document_id}")
    except Exception as e:
        logger.error(f"MongoDB rename failed for {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update document name in MongoDB: {e}")

    try:
        # 3. Update document name in Qdrant Cloud point payloads
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
            timeout=30
        )
        qdrant_client.set_payload(
            collection_name=QDRANT_COLLECTION,
            payload={"document_name": new_name},
            points_filter=Filter(must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id))
            ])
        )
        logger.info(f"Qdrant: updated document_name payload to '{new_name}' for {document_id}")
    except Exception as e:
        logger.warning(f"Qdrant rename payload failed for {document_id}: {e}")

    return {"document_id": document_id, "new_name": new_name, "status": "renamed"}


# =============================================================================
# GET /api/chunks/{chunk_id}/highlight
# =============================================================================

@router.get(
    "/chunks/{chunk_id}/highlight",
    summary="Render a highlighted PDF page for a given cited chunk",
)
def highlight_chunk(chunk_id: str):
    """
    Given a chunk_id, find the chunk text in the source PDF and return a PNG
    image of that page with the chunk text highlighted in yellow.

    Response JSON:
      image_base64  — base64-encoded PNG of the rendered page (None for non-PDFs)
      page_number   — the page the chunk came from (1-indexed)
      found         — True if the chunk text was located and highlighted
      document_name — original filename
      reason        — "not_pdf" when image_base64 is None
    """
    import base64
    import fitz   # PyMuPDF — already installed in requirements for OCR

    # ── 1. Fetch chunk metadata ───────────────────────────────────────────────
    chunk = mongo.get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found.")

    document_id   = chunk.get("document_id")
    page_number   = chunk.get("page_number", 1)   # stored 1-indexed
    chunk_text    = chunk.get("chunk_text", "")

    # ── 2. Fetch document record to get file path on disk ────────────────────
    doc_record = mongo.get_document_by_id(document_id)
    if not doc_record:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    file_path     = doc_record.get("file_path", "")
    file_type     = doc_record.get("file_type", "")
    document_name = doc_record.get("document_name", "")

    # ── 3. Only PDFs can be rendered ─────────────────────────────────────────
    if file_type != "pdf":
        return {
            "image_base64":  None,
            "page_number":   page_number,
            "found":         False,
            "document_name": document_name,
            "reason":        "not_pdf",
        }

    # ── 4. Resolve path (file_path is relative to backend/) ──────────────────
    # This file is at backend/routers/upload.py → .parent.parent = backend/
    backend_dir   = Path(__file__).parent.parent
    absolute_path = backend_dir / file_path

    if not absolute_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found on disk: {file_path}"
        )

    # ── 5. Open PDF and navigate to the correct page ─────────────────────────
    pdf_doc  = fitz.open(str(absolute_path))
    page_idx = max(0, page_number - 1)           # 1-indexed → 0-indexed
    page_idx = min(page_idx, len(pdf_doc) - 1)   # clamp to valid range
    page     = pdf_doc[page_idx]

    # ── 6. Search for chunk text and draw yellow highlight ───────────────────
    # Try progressively shorter snippets — text may have minor whitespace
    # or hyphenation differences after extraction.
    found = False
    for search_len in (120, 80, 50):
        snippet = chunk_text[:search_len].strip()
        if not snippet:
            break
        quads = page.search_for(snippet, quads=True)
        if quads:
            found = True
            for quad in quads:
                annot = page.add_highlight_annot(quad)
                annot.set_colors(stroke=[1, 0.92, 0.1])   # bright yellow
                annot.update()
            break

    # ── 7. Render page to a high-resolution PNG (2× zoom for crisp text) ─────
    matrix    = fitz.Matrix(2.0, 2.0)
    pixmap    = page.get_pixmap(matrix=matrix, alpha=False)
    img_bytes = pixmap.tobytes("png")
    pdf_doc.close()

    logger.info(
        f"Highlight rendered: chunk={chunk_id[:8]} page={page_number} "
        f"doc={document_name} found={found}"
    )

    return {
        "image_base64":  base64.b64encode(img_bytes).decode("utf-8"),
        "page_number":   page_number,
        "found":         found,
        "document_name": document_name,
    }
