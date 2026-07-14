"""
CiteRag — Document Ingestion Pipeline
Orchestrates the full 5-step ingestion flow for a single uploaded document:

  Step 1: Ensure DB collections/indices are ready
  Step 2: Extract text page-by-page (PyMuPDF → Tesseract fallback)
  Step 3: Semantic chunking (512-token chunks, 128-token overlap)
  Step 4: Generate 1024-dim BGE embeddings for every chunk
  Step 5: Store across all three databases:
            5a — Qdrant:        vector + metadata payload
            5b — MongoDB:       full chunk text + metadata
            5c — Elasticsearch: BM25 keyword index

Designed to be called from FastAPI BackgroundTasks so it runs asynchronously
after the upload endpoint has already returned a document_id to the client.
"""
from __future__ import annotations

from datetime import datetime

from loguru import logger

from db import elastic_client, mongo_client, qdrant_client
from models.schemas import Domain
from services.chunker import chunk_pages
from services.embedder import embed_texts
from services.extractor import extract_text


def run_ingestion(
    document_id:      str,
    file_path:        str,
    document_name:    str,
    file_type:        str,
    domain:           Domain,
    upload_timestamp: datetime,
) -> None:
    """
    Full document ingestion pipeline.

    Args:
        document_id:      UUID generated at upload time.
        file_path:        Absolute path to the saved file in uploads/.
        document_name:    Original filename (preserved for citations).
        file_type:        Extension without dot: 'pdf', 'docx', or 'txt'.
        domain:           Document domain for filtering and verification routing.
        upload_timestamp: UTC timestamp of the upload (preserved in metadata).
    """
    logger.info(
        f"[Ingestion] ▶ START  document_id={document_id}  file='{document_name}'"
    )

    try:
        # ── Step 1: Ensure storage collections/indices exist ──────────────────
        qdrant_client.ensure_collection()
        elastic_client.ensure_index()

        # ── Step 2: Text extraction ───────────────────────────────────────────
        pages = extract_text(file_path, file_type)

        total_text = " ".join(p["text"] for p in pages)
        if len(total_text.strip()) < 10:
            logger.error(
                f"[Ingestion] No usable text extracted from '{document_name}'. "
                "Marking as failed."
            )
            mongo_client.update_document_status(document_id, "failed", 0)
            return

        # ── Step 3: Semantic chunking ─────────────────────────────────────────
        chunks = chunk_pages(
            pages=pages,
            document_id=document_id,
            document_name=document_name,
            domain=domain,
            upload_timestamp=upload_timestamp,
        )

        if not chunks:
            logger.warning(
                f"[Ingestion] Chunker produced 0 chunks for '{document_name}'. "
                "Marking as failed."
            )
            mongo_client.update_document_status(document_id, "failed", 0)
            return

        # ── Step 4: Embedding generation ──────────────────────────────────────
        texts      = [c.chunk_text for c in chunks]
        embeddings = embed_texts(texts)

        # ── Step 5a: Store in Qdrant (vectors + metadata payload) ─────────────
        chunk_ids = [c.metadata.chunk_id for c in chunks]
        payloads  = [c.metadata.model_dump(mode="json") for c in chunks]
        qdrant_client.upsert_vectors(chunk_ids, embeddings, payloads)

        # ── Step 5b: Store in MongoDB (full text + metadata) ──────────────────
        mongo_docs = [
            {
                "chunk_id":   c.metadata.chunk_id,
                "chunk_text": c.chunk_text,
                "metadata":   c.metadata.model_dump(mode="json"),
            }
            for c in chunks
        ]
        mongo_client.insert_chunks(mongo_docs)
        mongo_client.update_document_status(document_id, "ready", len(chunks))

        # ── Step 5c: Index in Elasticsearch (BM25 keyword index) ──────────────
        es_docs = [
            {
                "chunk_id":         c.metadata.chunk_id,
                "document_id":      c.metadata.document_id,
                "document_name":    c.metadata.document_name,
                "chunk_text":       c.chunk_text,
                "page_number":      c.metadata.page_number,
                "paragraph_number": c.metadata.paragraph_number,
                "domain":           c.metadata.domain,
                "chunk_index":      c.metadata.chunk_index,
            }
            for c in chunks
        ]
        elastic_client.index_chunks(es_docs)

        logger.info(
            f"[Ingestion] ✔ COMPLETE  document_id={document_id}  "
            f"{len(chunks)} chunks → Qdrant ✔  MongoDB ✔  Elasticsearch ✔"
        )

    except Exception as exc:
        logger.exception(
            f"[Ingestion] ✘ FAILED  document_id={document_id}  error={exc}"
        )
        try:
            mongo_client.update_document_status(document_id, "failed", 0)
        except Exception:
            pass  # don't mask the original exception in logs
