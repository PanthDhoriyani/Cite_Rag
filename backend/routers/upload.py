"""
Upload router
  POST   /api/upload            — upload a PDF / DOCX / TXT file
  GET    /api/documents         — list all uploaded documents + status
  DELETE /api/documents/{id}    — delete a document from all 3 databases
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from loguru import logger

from config import UPLOAD_DIR, MAX_FILE_MB
from schemas import Domain, UploadResponse
from pipeline import run
import db.qdrant_client  as qdrant
import db.mongo_client   as mongo
import db.elastic_client as elastic

router      = APIRouter()
ALLOWED     = {"pdf", "docx", "txt"}
UPLOAD_PATH = Path(UPLOAD_DIR)


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload(
    background_tasks: BackgroundTasks,
    file:   UploadFile = File(...),
    domain: Domain     = Form(Domain.general),
):
    """Upload a file — validation runs now, ingestion runs in the background."""
    filename = file.filename or "unknown"
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Validate file type
    if ext not in ALLOWED:
        raise HTTPException(422, f"'.{ext}' not allowed. Accepted: {sorted(ALLOWED)}")

    # Read file and check size
    data    = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise HTTPException(422, f"File is {size_mb:.1f} MB — max allowed is {MAX_FILE_MB} MB.")

    # Save with a UUID filename to avoid collisions
    doc_id    = str(uuid.uuid4())
    UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_PATH / f"{doc_id}.{ext}"
    save_path.write_bytes(data)

    now = datetime.utcnow()

    # Create a document record immediately so the client can track status
    mongo.save_document({
        "document_id":      doc_id,
        "document_name":    filename,
        "file_path":        str(save_path),
        "file_type":        ext,
        "domain":           domain.value,
        "upload_timestamp": now.isoformat(),
        "status":           "processing",
        "total_chunks":     0,
    })

    # Fire off the RAG ingestion pipeline in the background
    background_tasks.add_task(run, doc_id, str(save_path), filename, ext, domain.value, now)

    logger.info(f"Uploaded '{filename}' (domain={domain.value}) → {save_path}")
    return UploadResponse(
        document_id=doc_id,
        filename=filename,
        status="processing",
        message="File accepted. Ingestion running in background.",
    )


@router.get("/documents")
def list_documents():
    """Return all uploaded documents and their current ingestion status."""
    return {"documents": mongo.all_documents()}


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, background_tasks: BackgroundTasks):
    """Delete a document from Qdrant, Elasticsearch, and MongoDB."""
    background_tasks.add_task(_delete_everywhere, document_id)
    return {"document_id": document_id, "status": "deletion_queued"}


def _delete_everywhere(document_id: str):
    """Remove all traces of a document from all three stores."""
    for label, fn in [
        ("Qdrant",         lambda: qdrant.delete_document(document_id)),
        ("Elasticsearch",  lambda: elastic.delete_document(document_id)),
        ("MongoDB",        lambda: mongo.remove_document(document_id)),
    ]:
        try:
            fn()
        except Exception as e:
            logger.warning(f"{label} delete error for {document_id}: {e}")
