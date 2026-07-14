"""
CiteRag — Upload Router
Implements the document upload API and document management endpoints.

Endpoints:
  POST   /api/upload                    — Upload a file, trigger ingestion
  GET    /api/documents                 — List all uploaded documents
  DELETE /api/documents/{document_id}   — Delete from all three stores
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

from db import elastic_client, mongo_client, qdrant_client
from models.schemas import Domain, DocumentInfo, UploadResponse
from services.ingestion import run_ingestion

router = APIRouter()

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_DIR         = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


# ── POST /api/upload ──────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file:   UploadFile = File(..., description="PDF, DOCX, or TXT file (max 50 MB)"),
    domain: Domain     = Form(Domain.general, description="Document domain for routing"),
):
    """
    Accept an uploaded document, validate it, persist it, and trigger
    the ingestion pipeline asynchronously via BackgroundTasks.

    Returns document_id immediately — ingestion continues in the background.
    Poll GET /api/documents to check when status changes from 'processing' to 'ready'.
    """
    # ── Validate file extension ───────────────────────────────────────────────
    filename = file.filename or "unknown_file"
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type '.{ext}'. "
                f"Allowed types: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )

    # ── Read & validate file size ─────────────────────────────────────────────
    contents = await file.read()
    size_mb  = len(contents) / (1024 * 1024)

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"File too large ({size_mb:.1f} MB). "
                f"Maximum allowed size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            ),
        )

    # ── Save file to uploads/ ─────────────────────────────────────────────────
    import uuid
    document_id    = str(uuid.uuid4())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{document_id}.{ext}"
    saved_path     = UPLOAD_DIR / saved_filename

    with open(saved_path, "wb") as f:
        f.write(contents)

    upload_timestamp = datetime.utcnow()
    logger.info(
        f"[Upload] '{filename}' saved → '{saved_path}' "
        f"({size_mb:.2f} MB, id={document_id})"
    )

    # ── Create document record in MongoDB (status: processing) ────────────────
    doc_info = DocumentInfo(
        document_id=document_id,
        document_name=filename,
        file_path=str(saved_path),
        file_type=ext,
        domain=domain,
        upload_timestamp=upload_timestamp,
        status="processing",
    )
    try:
        mongo_client.insert_document(doc_info.model_dump(mode="json"))
    except Exception as exc:
        logger.error(f"[Upload] MongoDB insert failed: {exc}")
        # Don't fail the upload — ingestion pipeline will update status later

    # ── Trigger ingestion pipeline in the background ──────────────────────────
    background_tasks.add_task(
        run_ingestion,
        document_id=document_id,
        file_path=str(saved_path),
        document_name=filename,
        file_type=ext,
        domain=domain,
        upload_timestamp=upload_timestamp,
    )

    return UploadResponse(
        document_id=document_id,
        document_name=filename,
        status="processing",
        message=(
            "File accepted and queued for ingestion. "
            "Poll GET /api/documents to check status."
        ),
    )


# ── GET /api/documents ────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents():
    """
    Return all uploaded documents with their current processing status and metadata.
    Status values: 'processing' | 'ready' | 'failed'
    """
    try:
        docs = mongo_client.list_documents()
        return {"documents": docs, "total": len(docs)}
    except Exception as exc:
        logger.error(f"[Upload] list_documents failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve documents. Is MongoDB running?",
        )


# ── DELETE /api/documents/{document_id} ──────────────────────────────────────

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, background_tasks: BackgroundTasks):
    """
    Queue deletion of a document from all three storage backends:
    Qdrant (vectors), MongoDB (chunks + document record), Elasticsearch (BM25 index).
    Returns immediately; deletion runs in the background.
    """
    background_tasks.add_task(_delete_from_all_stores, document_id)
    return {
        "document_id": document_id,
        "status":      "deletion_queued",
        "message":     "Document deletion queued. It will be removed from all stores shortly.",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _delete_from_all_stores(document_id: str) -> None:
    """
    Remove all data for a document from Qdrant, Elasticsearch, and MongoDB.
    Errors in any single store are logged as warnings (not fatal) so the
    other stores are still cleaned up.
    """
    for label, fn in [
        ("Qdrant",         lambda: qdrant_client.delete_by_document_id(document_id)),
        ("Elasticsearch",  lambda: elastic_client.delete_by_document_id(document_id)),
        ("MongoDB",        lambda: mongo_client.delete_document(document_id)),
    ]:
        try:
            fn()
        except Exception as exc:
            logger.warning(f"[Upload] {label} delete failed for {document_id}: {exc}")

    logger.info(f"[Upload] Document '{document_id}' deletion complete across all stores.")
