"""
CiteRag — RAG Ingestion Pipeline

This file is the heart of the ingestion side of the RAG system.
It has exactly 4 steps that run in order for every uploaded document:

  Step 1  extract()  — read text from the file (PDF / DOCX / TXT)
  Step 2  chunk()    — split text into overlapping pieces
  Step 3  embed()    — turn each piece into a 1024-number vector
  Step 4  store()    — save to all 3 databases

  run()  — calls all 4 steps. This is what the upload endpoint triggers.
"""
import io
import uuid
from datetime import datetime
from pathlib import Path

from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL
import db.qdrant_client  as qdrant
import db.mongo_client   as mongo
import db.elastic_client as elastic


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Extract
# ─────────────────────────────────────────────────────────────────────────────

def extract(file_path: str, file_type: str) -> list:
    """
    Read text from an uploaded file.
    Returns: [{"page_number": int, "text": str}, ...]

    Why page-by-page? Because page_number metadata cannot be recovered
    after text is merged — so we capture it here at the source.
    """
    path = Path(file_path)

    if file_type == "pdf":
        pages = _pdf_digital(path)
        total_chars = sum(len(p["text"].strip()) for p in pages)
        # Less than 100 chars usually means a scanned (image) PDF — use OCR
        if total_chars < 100:
            logger.info(f"Only {total_chars} chars extracted — switching to Tesseract OCR")
            pages = _pdf_ocr(path)
        return pages

    elif file_type == "docx":
        from docx import Document
        doc  = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [{"page_number": 1, "text": text}]

    elif file_type == "txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        return [{"page_number": 1, "text": text}]

    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _pdf_digital(path: Path) -> list:
    """Fast text extraction using PyMuPDF — works on normal digital PDFs."""
    import fitz
    doc   = fitz.open(str(path))
    pages = [
        {"page_number": i + 1, "text": page.get_text("text") or ""}
        for i, page in enumerate(doc)
    ]
    doc.close()
    return pages


def _pdf_ocr(path: Path) -> list:
    """
    Tesseract OCR fallback for scanned PDFs.
    Renders each page as a 300 DPI PNG image, then reads text from the image.
    """
    import fitz, pytesseract
    from PIL import Image

    doc    = fitz.open(str(path))
    matrix = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
    pages  = []
    for i, page in enumerate(doc):
        pix  = page.get_pixmap(matrix=matrix)
        img  = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img) or ""
        pages.append({"page_number": i + 1, "text": text})
    doc.close()
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Chunk
# ─────────────────────────────────────────────────────────────────────────────

def chunk(pages: list, doc_meta: dict) -> list:
    """
    Split each page's text into overlapping chunks and attach metadata.

    Each chunk gets: chunk_id, chunk_text, page_number, paragraph_number,
    chunk_index, document_id, document_name, domain, total_chunks.

    Returns: list of chunk dicts ready for embedding and storage.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],  # prefer paragraph splits first
    )

    all_chunks   = []
    global_index = 0

    for page in pages:
        text = page["text"].strip()
        if not text:
            continue
        for para_num, piece in enumerate(splitter.split_text(text), start=1):
            all_chunks.append({
                "chunk_id":         str(uuid.uuid4()),
                "chunk_text":       piece,
                "chunk_index":      global_index,
                "total_chunks":     0,          # backfilled below
                "page_number":      page["page_number"],
                "paragraph_number": para_num,
                "document_id":      doc_meta["document_id"],
                "document_name":    doc_meta["document_name"],
                "domain":           doc_meta["domain"],
                "upload_timestamp": doc_meta["upload_timestamp"],
            })
            global_index += 1

    # Now we know the total — fill it in on every chunk
    total = len(all_chunks)
    for c in all_chunks:
        c["total_chunks"] = total

    logger.info(
        f"Chunked '{doc_meta['document_name']}' → {total} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )
    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Embed
# ─────────────────────────────────────────────────────────────────────────────

_embed_model = None  # singleton — loaded once, reused for every request


def embed(texts: list) -> list:
    """
    Convert a list of text strings into 1024-dim embedding vectors.
    Uses BAAI/bge-large-en-v1.5 — loaded once the first time this is called.

    normalize_embeddings=True ensures correct cosine similarity with Qdrant.
    Returns: list of lists (one 1024-float list per input text).
    """
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)

    vectors = _embed_model.encode(texts, batch_size=32, normalize_embeddings=True)
    return vectors.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Store
# ─────────────────────────────────────────────────────────────────────────────

def store(chunks: list, vectors: list):
    """
    Save chunks to all three databases simultaneously:

      Qdrant        → embedding vectors + metadata  (for semantic search)
      MongoDB       → full chunk text + metadata    (source of truth)
      Elasticsearch → indexed text                  (for BM25 keyword search)
    """
    chunk_ids = [c["chunk_id"] for c in chunks]

    # Qdrant payload = everything except chunk_text (text lives in MongoDB)
    payloads = [{k: v for k, v in c.items() if k != "chunk_text"} for c in chunks]

    qdrant.store_batch(chunk_ids, vectors, payloads)
    mongo.save_chunks(chunks)
    elastic.index_chunks(chunks)

    logger.info(f"Stored {len(chunks)} chunks → Qdrant + MongoDB + Elasticsearch")


# ─────────────────────────────────────────────────────────────────────────────
# Full Pipeline — called by the upload endpoint
# ─────────────────────────────────────────────────────────────────────────────

def run(document_id: str, file_path: str, filename: str,
        file_type: str, domain: str, upload_timestamp: datetime):
    """
    Run the complete RAG ingestion pipeline for one uploaded document.

    Called as a FastAPI BackgroundTask — the upload endpoint returns
    immediately to the user while this runs in the background.

    Flow:  extract → chunk → embed → store
    """
    logger.info(f"[Pipeline] START  file='{filename}'  id={document_id}")
    try:
        # Make sure DB collections / indexes exist before writing anything
        qdrant.setup()
        elastic.setup()

        # Step 1 — Extract text (page by page)
        pages = extract(file_path, file_type)
        if not any(p["text"].strip() for p in pages):
            raise ValueError("No text could be extracted from the file.")

        # Step 2 — Chunk into overlapping pieces with full metadata
        chunks = chunk(pages, {
            "document_id":      document_id,
            "document_name":    filename,
            "domain":           domain,
            "upload_timestamp": upload_timestamp.isoformat(),
        })
        if not chunks:
            raise ValueError("Chunker produced 0 chunks.")

        # Step 3 — Embed (BAAI/bge-large-en-v1.5, 1024-dim, normalised)
        vectors = embed([c["chunk_text"] for c in chunks])

        # Step 4 — Store in all 3 databases
        store(chunks, vectors)

        # Mark document as ready
        mongo.update_status(document_id, "ready", len(chunks))
        logger.info(f"[Pipeline] DONE  file='{filename}'  chunks={len(chunks)}")

    except Exception as e:
        logger.error(f"[Pipeline] FAILED  file='{filename}'  error={e}")
        mongo.update_status(document_id, "failed")
